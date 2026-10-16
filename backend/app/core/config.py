from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "QUEBET AI API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Environment
    ENVIRONMENT: str = "development"

    # Security & Tokens
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Default 1 hour
    ALLOW_DEV_MOCK_AUTH: bool = False

    # AI Gateway (OpenRouter)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_FREE_MODEL: str = "deepseek/deepseek-chat-v3-0324"
    DEFAULT_PLUS_MODEL: str = "google/gemini-2.0-flash"
    DEFAULT_PRO_MODEL: str = "anthropic/claude-sonnet-4"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./quebet_ai.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Knowledge Graph (Neo4j)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "quebet_password"

    # Vector DB (ChromaDB)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://quebet.ai",
    ]

    # RFC 3161 External Timestamping & Audit Anchoring
    TSA_SERVER_URL: Optional[str] = None
    TSA_CA_CERT_PATH: Optional[str] = None
    TSA_TIMEOUT_SECONDS: float = 10.0
    TSA_POLICY_OID: Optional[str] = None
    TSA_REQUIRE_CERT_REQ: bool = True
    TSA_MIRROR_S3_BUCKET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def validate_security(cls, settings_obj: "Settings") -> "Settings":
        if settings_obj.ENVIRONMENT.lower() == "production":
            dev_default = "dev-secret-key-change-in-production-min-32-chars-long"
            if settings_obj.SECRET_KEY == dev_default or len(settings_obj.SECRET_KEY) < 32:
                raise ValueError(
                    "FATAL: Insecure SECRET_KEY configured for production environment. "
                    "Must be distinct from dev default and at least 32 characters."
                )
        return settings_obj


settings = Settings()
Settings.validate_security(settings)
