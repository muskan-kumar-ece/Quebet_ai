from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class Net(Base, UUIDMixin, TimestampMixin):
    """
    Electrical net representing equipotential connected nodes (e.g. VCC, GND, SIGNAL_1).
    """

    __tablename__ = "nets"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)  # "VCC", "GND", "SIGNAL_1"
    net_type: Mapped[str] = mapped_column(String(32), default="signal", nullable=False)  # "power", "ground", "signal", "clock"
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    circuit = relationship("Circuit", back_populates="nets")
    connections = relationship("Connection", back_populates="net", cascade="all, delete-orphan")
