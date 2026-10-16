from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class SchematicObject(Base, UUIDMixin, TimestampMixin):
    """
    Visual schematic presentation model strictly separated from electrical truth.
    Stores symbols, wire geometries, junction dots, labels, and graphical annotations.
    """

    __tablename__ = "schematic_objects"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)  # symbol | wire | junction | label | text
    component_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("components.id", ondelete="SET NULL"),
        nullable=True,
    )
    net_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("nets.id", ondelete="SET NULL"),
        nullable=True,
    )
    pos_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rotation: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    graphics: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)

    # Relationships
    circuit = relationship("Circuit", back_populates="schematic_objects")
