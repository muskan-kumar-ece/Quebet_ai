import logging
import re
from typing import Any
import chromadb
from chromadb.api import ClientAPI
from pydantic import BaseModel, Field
from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreConfig(BaseModel):
    """Configuration for ChromaDB vector store connector."""

    host: str = Field(default_factory=lambda: settings.CHROMA_HOST)
    port: int = Field(default_factory=lambda: settings.CHROMA_PORT)
    ssl: bool = False
    persist_directory: str | None = "./chroma_data"
    default_collection: str = "electronics_kb"


class VectorStoreClient:
    """
    Vector store boundary establishing multi-tenant collection isolation,
    connection lifecycle management, and connectivity verification for ChromaDB.
    """

    def __init__(self, config: VectorStoreConfig | None = None) -> None:
        self.config = config or VectorStoreConfig()
        self._client: ClientAPI | None = None

    def _initialize_client(self) -> ClientAPI:
        """
        Attempts to connect to ChromaDB HTTP Server; falls back gracefully
        to a local PersistentClient if HTTP is unavailable.
        """
        if self._client is not None:
            return self._client

        # 1. Attempt HTTP connection
        try:
            client = chromadb.HttpClient(
                host=self.config.host,
                port=self.config.port,
                ssl=self.config.ssl,
            )
            # Quick heartbeat check
            client.heartbeat()
            self._client = client
            logger.info("Connected to remote ChromaDB at %s:%s", self.config.host, self.config.port)
            return self._client
        except Exception as e:
            logger.warning(
                "Remote ChromaDB HTTP service unavailable (%s:%s): %s. Initializing local persistent store at %s",
                self.config.host,
                self.config.port,
                str(e),
                self.config.persist_directory,
            )

        # 2. Fallback to embedded PersistentClient
        try:
            self._client = chromadb.PersistentClient(path=self.config.persist_directory or "./chroma_data")
            logger.info("ChromaDB PersistentClient initialized at %s", self.config.persist_directory)
            return self._client
        except Exception as e:
            logger.error("Failed to initialize ChromaDB PersistentClient: %s", str(e))
            raise

    async def verify_connectivity(self) -> bool:
        """
        Verifies vector store health by querying heartbeat.
        Returns True if operational, False otherwise.
        """
        try:
            client = self._initialize_client()
            heartbeat = client.heartbeat()
            return heartbeat is not None and heartbeat > 0
        except Exception as e:
            logger.warning("ChromaDB connectivity check failed: %s", str(e))
            return False

    def sanitize_collection_name(self, name: str) -> str:
        """
        Enforces ChromaDB collection name rules:
        - 3-63 characters
        - Alphanumeric, underscores, hyphens
        - Starts and ends with alphanumeric
        """
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        if len(cleaned) < 3:
            cleaned = f"col_{cleaned}"
        elif len(cleaned) > 63:
            cleaned = cleaned[:63]
        return cleaned

    def get_tenant_collection_name(self, tenant_id: str | None, base_name: str = "components") -> str:
        """
        Derives an isolated collection name compliant with tenant scoping rules.
        """
        if not tenant_id:
            return self.sanitize_collection_name(f"global_{base_name}")
        return self.sanitize_collection_name(f"t_{tenant_id}_{base_name}")

    async def get_or_create_collection(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Retrieves or creates a named collection."""
        client = self._initialize_client()
        sanitized = self.sanitize_collection_name(name)
        return client.get_or_create_collection(name=sanitized, metadata=metadata)

    async def close(self) -> None:
        """Clean shutdown of the vector store client."""
        self._client = None
        logger.info("Vector store client connection closed.")


# Global vector store instance
vector_store_client = VectorStoreClient()


async def get_vector_store() -> VectorStoreClient:
    """FastAPI dependency for accessing vector store client."""
    return vector_store_client


async def close_vector_store() -> None:
    """Lifespan shutdown handler."""
    await vector_store_client.close()
