from enum import Enum
from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class ProjectType(str, Enum):
    CIRCUIT = "circuit"
    PCB = "pcb"
    EMBEDDED = "embedded"
    POWER = "power"
    RF = "rf"
    THERMAL = "thermal"
    BATTERY = "battery"
    GENERAL = "general"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"
    COMPLETED = "completed"


class Project(Base, UUIDMixin, TimestampMixin):
    """
    Core engineering workspace project boundary.
    Scoped by tenant_id and owned by owner_id.
    """

    __tablename__ = "projects"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    owner_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[str] = mapped_column(String(32), default=ProjectType.CIRCUIT.value, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.ACTIVE.value, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    circuits = relationship("Circuit", back_populates="project", cascade="all, delete-orphan")
    systems = relationship("EngineeringSystem", back_populates="project", cascade="all, delete-orphan")
