from enum import Enum
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class ObjectiveType(str, Enum):
    REDUCE_POWER = "REDUCE_POWER"
    REDUCE_COMPONENT_STRESS = "REDUCE_COMPONENT_STRESS"
    IMPROVE_MARGIN = "IMPROVE_MARGIN"
    REDUCE_COMPONENT_COUNT = "REDUCE_COMPONENT_COUNT"
    REDUCE_COST = "REDUCE_COST"
    IMPROVE_EFFICIENCY = "IMPROVE_EFFICIENCY"
    FIX_RULE_VIOLATION = "FIX_RULE_VIOLATION"
    FIX_FLOATING_PIN = "FIX_FLOATING_PIN"
    FIX_VOLTAGE_DOMAIN = "FIX_VOLTAGE_DOMAIN"
    FIX_REGULATOR_OVERLOAD = "FIX_REGULATOR_OVERLOAD"
    FIX_THERMAL_PROBLEM = "FIX_THERMAL_PROBLEM"
    SELECT_ALTERNATIVE_COMPONENT = "SELECT_ALTERNATIVE_COMPONENT"
    ADJUST_COMPONENT_VALUE = "ADJUST_COMPONENT_VALUE"
    ADD_REQUIRED_COMPONENT = "ADD_REQUIRED_COMPONENT"
    REMOVE_UNNECESSARY_COMPONENT = "REMOVE_UNNECESSARY_COMPONENT"
    COMPARE_DESIGNS = "COMPARE_DESIGNS"


class EngineeringDesignObjective(Base, UUIDMixin, TimestampMixin):
    """
    Normalized representation of an engineering design goal.
    Coordinates candidate generation, what-if re-analysis, and proposal synthesis.
    """

    __tablename__ = "engineering_design_objectives"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    objective_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    constraints: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    affected_components: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    affected_nets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="USER", nullable=False)  # USER | AI | FINDING

    # Relationships
    circuit = relationship("Circuit", back_populates="design_objectives")
