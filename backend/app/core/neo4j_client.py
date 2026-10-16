import logging
from typing import Any
from neo4j import AsyncDriver, AsyncGraphDatabase
from pydantic import BaseModel, Field
from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jConfig(BaseModel):
    """Typed configuration for Neo4j Graph Database connector."""

    uri: str = Field(default_factory=lambda: settings.NEO4J_URI)
    user: str = Field(default_factory=lambda: settings.NEO4J_USER)
    password: str = Field(default_factory=lambda: settings.NEO4J_PASSWORD)
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout_seconds: float = 5.0


class Neo4jClient:
    """
    Asynchronous Neo4j connector providing connection lifecycle management,
    healthcheck verification, and safe Cypher execution for electronics knowledge graphs.
    """

    def __init__(self, config: Neo4jConfig | None = None) -> None:
        self.config = config or Neo4jConfig()
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Initializes the Async Neo4j Driver pool."""
        if self._driver is None:
            try:
                self._driver = AsyncGraphDatabase.driver(
                    self.config.uri,
                    auth=(self.config.user, self.config.password),
                    max_connection_pool_size=self.config.max_connection_pool_size,
                    connection_timeout=self.config.connection_timeout_seconds,
                )
                logger.info("Neo4j driver initialized for %s", self.config.uri)
            except Exception as e:
                logger.error("Failed to initialize Neo4j driver: %s", str(e))
                self._driver = None

    async def close(self) -> None:
        """Closes the Neo4j driver pool cleanly."""
        if self._driver is not None:
            try:
                await self._driver.close()
                logger.info("Neo4j driver connection closed.")
            except Exception as e:
                logger.warning("Error closing Neo4j driver: %s", str(e))
            finally:
                self._driver = None

    async def verify_connectivity(self) -> bool:
        """
        Verifies active connectivity to the Neo4j cluster without logging credentials.
        Returns True if reachable and authenticated, False otherwise.
        """
        if self._driver is None:
            await self.connect()

        if self._driver is None:
            return False

        try:
            await self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning("Neo4j connectivity check failed: %s", str(e))
            return False

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Safely executes a read/write Cypher query with automatic session management.
        """
        if self._driver is None:
            await self.connect()

        if self._driver is None:
            raise ConnectionError("Neo4j driver is not connected.")

        target_db = database or self.config.database
        async with self._driver.session(database=target_db) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records


# Global client instance
neo4j_client = Neo4jClient()


async def get_neo4j_client() -> Neo4jClient:
    """Dependency provider for FastAPI route handlers and services."""
    return neo4j_client


async def close_neo4j_client() -> None:
    """Lifespan shutdown handler."""
    await neo4j_client.close()
