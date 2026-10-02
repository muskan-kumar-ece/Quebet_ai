from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    """Enterprise organizational tenant."""
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="enterprise", nullable=False)
    max_seats: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    neo4j_namespace: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    chroma_collection_prefix: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
