from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class SystemObjectiveType(str, Enum):
    POWER_OPTIMIZATION = "POWER_OPTIMIZATION"
    THERMAL_IMPROVEMENT = "THERMAL_IMPROVEMENT"
    RELIABILITY_IMPROVEMENT = "RELIABILITY_IMPROVEMENT"
    INTERFACE_COMPATIBILITY = "INTERFACE_COMPATIBILITY"
    COST_REDUCTION = "COST_REDUCTION"
    SIZE_REDUCTION = "SIZE_REDUCTION"
    WEIGHT_REDUCTION = "WEIGHT_REDUCTION"
    PERFORMANCE_IMPROVEMENT = "PERFORMANCE_IMPROVEMENT"
    EFFICIENCY_IMPROVEMENT = "EFFICIENCY_IMPROVEMENT"
    POWER_DOMAIN_CHANGE = "POWER_DOMAIN_CHANGE"
    SUBSYSTEM_REPLACEMENT = "SUBSYSTEM_REPLACEMENT"
    FAILURE_CONTAINMENT = "FAILURE_CONTAINMENT"
    OPERATING_RANGE_EXTENSION = "OPERATING_RANGE_EXTENSION"
    REQUIREMENT_COMPLIANCE = "REQUIREMENT_COMPLIANCE"
    CUSTOM = "CUSTOM"


class SystemObjectiveStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class ConstraintType(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class ConstraintOperator(str, Enum):
    LTE = "LTE"
    GTE = "GTE"
    EQ = "EQ"
    IN = "IN"
    CONTAINS = "CONTAINS"
    RANGE = "RANGE"


class ScenarioType(str, Enum):
    NORMAL_OPERATION = "NORMAL_OPERATION"
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"
    LOW_POWER = "LOW_POWER"
    MAXIMUM_LOAD = "MAXIMUM_LOAD"
    MINIMUM_LOAD = "MINIMUM_LOAD"
    THERMAL_EXTREME = "THERMAL_EXTREME"
    VOLTAGE_EXTREME = "VOLTAGE_EXTREME"
    COMMUNICATION_LOSS = "COMMUNICATION_LOSS"
    POWER_SOURCE_LOSS = "POWER_SOURCE_LOSS"
    SUBSYSTEM_FAILURE = "SUBSYSTEM_FAILURE"
    INTERFACE_FAILURE = "INTERFACE_FAILURE"
    SENSOR_FAILURE = "SENSOR_FAILURE"
    REGULATOR_FAILURE = "REGULATOR_FAILURE"
    USER_DEFINED = "USER_DEFINED"


class ScenarioConditionType(str, Enum):
    PRECONDITION = "PRECONDITION"
    OPERATING_CONDITION = "OPERATING_CONDITION"
    FAULT_INJECTION = "FAULT_INJECTION"


class ScenarioResultStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"
    STALE = "STALE"


class CandidateStrategy(str, Enum):
    POWER_DOMAIN_RESTRUCTURE = "POWER_DOMAIN_RESTRUCTURE"
    REGULATOR_REPLACEMENT = "REGULATOR_REPLACEMENT"
    SUBSYSTEM_ISOLATION = "SUBSYSTEM_ISOLATION"
    INTERFACE_ADAPTER = "INTERFACE_ADAPTER"
    REDUNDANCY_ADDITION = "REDUNDANCY_ADDITION"
    PROTECTION_ADDITION = "PROTECTION_ADDITION"
    LOAD_REBALANCING = "LOAD_REBALANCING"
    SUBSYSTEM_DECOMPOSITION = "SUBSYSTEM_DECOMPOSITION"
    SUBSYSTEM_CONSOLIDATION = "SUBSYSTEM_CONSOLIDATION"
    THERMAL_PATH_IMPROVEMENT = "THERMAL_PATH_IMPROVEMENT"
    COMMUNICATION_PATH_CHANGE = "COMMUNICATION_PATH_CHANGE"
    FAILURE_CONTAINMENT = "FAILURE_CONTAINMENT"
    OPERATING_MODE_RESTRUCTURE = "OPERATING_MODE_RESTRUCTURE"
    CUSTOM = "CUSTOM"


class CandidateStatus(str, Enum):
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    PROMOTED = "PROMOTED"


class SystemProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"


class EngineeringSystemDesignObjective(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative representation of a system design goal.
    Coordinates candidate generation, scenario testing, and proposal synthesis.
    """
    __tablename__ = "engineering_system_design_objectives"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective_type: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(32), default=SystemObjectiveStatus.ACTIVE.value, nullable=False)
    target: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    affected_subsystems: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    relevant_modes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    constraints = relationship("EngineeringSystemDesignConstraint", back_populates="objective", cascade="all, delete-orphan", lazy="selectin")
    candidates = relationship("EngineeringSystemCandidate", back_populates="objective", cascade="all, delete-orphan", lazy="selectin")


class EngineeringSystemDesignConstraint(Base, UUIDMixin, TimestampMixin):
    """
    Hard or soft boundary constraints associated with a system design objective.
    Evaluation produces PASS/FAIL/UNKNOWN (Hard) or SATISFIED/NOT_SATISFIED/UNKNOWN (Soft).
    """
    __tablename__ = "engineering_system_design_constraints"

    objective_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_system_design_objectives.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    constraint_type: Mapped[str] = mapped_column(String(16), nullable=False)  # HARD, SOFT
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False)  # LTE, GTE, EQ, IN, CONTAINS, RANGE
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, default=1.0, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    objective = relationship("EngineeringSystemDesignObjective", back_populates="constraints")


class EngineeringScenario(Base, UUIDMixin, TimestampMixin):
    """
    Operating or failure scenario under which the system architecture is evaluated.
    """
    __tablename__ = "engineering_scenarios"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    system_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    conditions = relationship("EngineeringScenarioCondition", back_populates="scenario", cascade="all, delete-orphan", lazy="selectin")
    results = relationship("EngineeringScenarioResult", back_populates="scenario", cascade="all, delete-orphan", lazy="selectin")


class EngineeringScenarioCondition(Base, UUIDMixin, TimestampMixin):
    """
    Structured precondition, operational state, or fault injected for a scenario.
    """
    __tablename__ = "engineering_scenario_conditions"

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_scenarios.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    condition_type: Mapped[str] = mapped_column(String(32), nullable=False)  # PRECONDITION, OPERATING_CONDITION, FAULT_INJECTION
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SYSTEM, SUBSYSTEM, INTERFACE, POWER_DOMAIN
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    scenario = relationship("EngineeringScenario", back_populates="conditions")


class EngineeringScenarioSnapshot(Base, UUIDMixin, TimestampMixin):
    """
    Immutable cryptographic snapshot of system state during a specific scenario run.
    """
    __tablename__ = "engineering_scenario_snapshots"

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_scenarios.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    system_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scenario_conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    engine_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    inputs_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)


class EngineeringScenarioResult(Base, UUIDMixin, TimestampMixin):
    """
    Outcome of executing a scenario against system architecture.
    Never assigns an arbitrary numerical health or risk score.
    """
    __tablename__ = "engineering_scenario_results"

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_scenarios.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    execution_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ScenarioResultStatus.COMPLETE.value, nullable=False)
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    precondition_status: Mapped[str] = mapped_column(String(32), default="SATISFIED", nullable=False)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    requirement_results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    power_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    interface_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    failure_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    scenario = relationship("EngineeringScenario", back_populates="results")


class EngineeringSystemCandidate(Base, UUIDMixin, TimestampMixin):
    """
    Sandboxed what-if candidate architecture with validated consequences.
    """
    __tablename__ = "engineering_system_candidates"

    objective_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_system_design_objectives.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    generation_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=CandidateStatus.GENERATED.value, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    operations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    hard_constraints_result: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    soft_constraints_result: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    constraints_evaluation: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    requirement_effects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    verification_effects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    failure_effects: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    power_effects: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    objective = relationship("EngineeringSystemDesignObjective", back_populates="candidates")


class EngineeringSystemProposal(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative revision-bound system architecture change proposal.
    Requires human approval and applies atomically.
    """
    __tablename__ = "engineering_system_proposals"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    candidate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_system_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    objective_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_system_design_objectives.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=SystemProposalStatus.PROPOSED.value, index=True, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    system_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scenario_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    operations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    generation_strategy: Mapped[str] = mapped_column(String(64), default="MANUAL", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    engineering_effects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    requirement_effects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    verification_effects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    failure_effects: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)
