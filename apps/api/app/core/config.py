from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "QUEBET AI API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Security & Tokens
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

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
        "https://quebet.ai",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
