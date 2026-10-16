from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class Connection(Base, UUIDMixin, TimestampMixin):
    """
    Component Pin to Net electrical binding.
    Establishes the topological edge: Component[pin_number] <-> Net.
    """

    __tablename__ = "connections"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    component_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("components.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pin_number: Mapped[str] = mapped_column(String(32), nullable=False)
    pin_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    net_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("nets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Relationships
    circuit = relationship("Circuit", back_populates="connections")
    component = relationship("Component", back_populates="connections")
    net = relationship("Net", back_populates="connections")
