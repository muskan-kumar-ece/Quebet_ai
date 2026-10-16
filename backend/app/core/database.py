from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

# Engine configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    # SQLite compatibility for thread pool / PostgreSQL pooler compatibility for asyncpg:
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
    },
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
