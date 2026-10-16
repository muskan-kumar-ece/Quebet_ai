from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class Component(Base, UUIDMixin, TimestampMixin):
    """
    Normalized physical/electrical component representation within a Circuit.
    Examples: R1 (10k, 1%, 0603), U1 (LM7805, TO-220).
    """

    __tablename__ = "components"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    ref_des: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # R1, C1, U1
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)  # resistor, capacitor, ic, regulator, mcu
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    part_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    value: Mapped[str] = mapped_column(String(64), nullable=False)  # "10k", "100nF", "LM7805"
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "ohm", "F", "V"
    tolerance: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "1%", "5%"
    rating: Mapped[str | None] = mapped_column(String(64), nullable=True)  # "0.25W", "16V", "1.5A"
    package: Mapped[str | None] = mapped_column(String(64), nullable=True)  # "0603", "TO-220", "SOT-223"
    pins: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)  # [{"pin_number": "1", "pin_name": "VI", "pin_type": "power_in"}, ...]
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)
    created_source: Mapped[str] = mapped_column(String(32), default="USER", nullable=False)  # USER | AI | KB

    # Relationships
    circuit = relationship("Circuit", back_populates="components")
    connections = relationship("Connection", back_populates="component", cascade="all, delete-orphan")
