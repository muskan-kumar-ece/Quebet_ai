from enum import Enum
from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, AuditTimestampMixin, UUIDMixin


class SystemStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    ARCHIVED = "ARCHIVED"


class SubsystemType(str, Enum):
    POWER = "POWER"
    PROTECTION = "PROTECTION"
    REGULATION = "REGULATION"
    PROCESSING = "PROCESSING"
    SENSING = "SENSING"
    COMMUNICATION = "COMMUNICATION"
    STORAGE = "STORAGE"
    ACTUATION = "ACTUATION"
    USER_INTERFACE = "USER_INTERFACE"
    CLOCK = "CLOCK"
    ANALOG = "ANALOG"
    DIGITAL = "DIGITAL"
    RF = "RF"
    SAFETY = "SAFETY"
    OTHER = "OTHER"


class InterfaceType(str, Enum):
    POWER = "POWER"
    GROUND = "GROUND"
    ANALOG_SIGNAL = "ANALOG_SIGNAL"
    DIGITAL_SIGNAL = "DIGITAL_SIGNAL"
    CLOCK = "CLOCK"
    DATA = "DATA"
    CONTROL = "CONTROL"
    COMMUNICATION = "COMMUNICATION"
    RF = "RF"
    MECHANICAL = "MECHANICAL"
    THERMAL = "THERMAL"
    OTHER = "OTHER"


class DependencyType(str, Enum):
    POWER_DEPENDS_ON = "POWER_DEPENDS_ON"
    SIGNAL_DEPENDS_ON = "SIGNAL_DEPENDS_ON"
    DATA_DEPENDS_ON = "DATA_DEPENDS_ON"
    CONTROL_DEPENDS_ON = "CONTROL_DEPENDS_ON"
    CLOCK_DEPENDS_ON = "CLOCK_DEPENDS_ON"
    THERMALLY_DEPENDS_ON = "THERMALLY_DEPENDS_ON"
    COMMUNICATION_DEPENDS_ON = "COMMUNICATION_DEPENDS_ON"


class SystemRequirementType(str, Enum):
    ELECTRICAL = "ELECTRICAL"
    THERMAL = "THERMAL"
    FUNCTIONAL = "FUNCTIONAL"
    PHYSICAL = "PHYSICAL"
    RELIABILITY = "RELIABILITY"
    REGULATORY = "REGULATORY"


class SystemRequirementStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    SUPPORTED = "SUPPORTED"
    VIOLATED = "VIOLATED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


class EngineeringSystem(Base, UUIDMixin, AuditTimestampMixin):
    """
    Root engineering system model representing complete system decomposition.
    Tenant-isolated and project-bound.
    """
    __tablename__ = "engineering_systems"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=SystemStatus.DRAFT.value, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="systems")
    subsystems = relationship("EngineeringSubsystem", back_populates="system", cascade="all, delete-orphan")
    interfaces = relationship("EngineeringSystemInterface", back_populates="system", cascade="all, delete-orphan")
    power_domains = relationship("EngineeringPowerDomain", back_populates="system", cascade="all, delete-orphan")
    dependencies = relationship("EngineeringSystemDependency", back_populates="system", cascade="all, delete-orphan")
    operating_modes = relationship("EngineeringOperatingMode", back_populates="system", cascade="all, delete-orphan")
    mode_transitions = relationship("EngineeringModeTransition", back_populates="system", cascade="all, delete-orphan")
    requirements = relationship("EngineeringSystemRequirement", back_populates="system", cascade="all, delete-orphan")
    analyses = relationship("EngineeringSystemAnalysis", back_populates="system", cascade="all, delete-orphan")
    snapshots = relationship("EngineeringSystemSnapshot", back_populates="system", cascade="all, delete-orphan")


class EngineeringSubsystem(Base, UUIDMixin, AuditTimestampMixin):
    """
    Subsystem unit within an EngineeringSystem.
    Supports arbitrary hierarchy depth (parent_subsystem_id) and optional circuit binding.
    """
    __tablename__ = "engineering_subsystems"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_subsystem_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subsystem_type: Mapped[str] = mapped_column(String(64), default=SubsystemType.OTHER.value, nullable=False)
    circuit_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="subsystems")
    parent = relationship("EngineeringSubsystem", remote_side="EngineeringSubsystem.id", back_populates="children")
    children = relationship("EngineeringSubsystem", back_populates="parent", cascade="all, delete-orphan")
    circuit = relationship("Circuit")


class EngineeringSystemInterface(Base, UUIDMixin, AuditTimestampMixin):
    """
    First-class engineering boundary between two subsystems with a typed contract.
    """
    __tablename__ = "engineering_system_interfaces"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    source_subsystem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    destination_subsystem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    interface_type: Mapped[str] = mapped_column(String(64), default=InterfaceType.OTHER.value, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    contract: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="interfaces")
    source_subsystem = relationship("EngineeringSubsystem", foreign_keys=[source_subsystem_id])
    destination_subsystem = relationship("EngineeringSubsystem", foreign_keys=[destination_subsystem_id])


class EngineeringPowerDomain(Base, UUIDMixin, AuditTimestampMixin):
    """
    Electrically meaningful supply region with nominal and boundary voltage limits.
    """
    __tablename__ = "engineering_power_domains"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nominal_voltage: Mapped[float] = mapped_column(Float, nullable=False)
    min_voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_subsystem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    regulator_subsystem_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    current_capacity_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="power_domains")
    source_subsystem = relationship("EngineeringSubsystem", foreign_keys=[source_subsystem_id])
    regulator_subsystem = relationship("EngineeringSubsystem", foreign_keys=[regulator_subsystem_id])


class EngineeringSystemDependency(Base, UUIDMixin, AuditTimestampMixin):
    """
    Explicit system relationship between subsystems (Power, Signal, Data, Control, etc.).
    """
    __tablename__ = "engineering_system_dependencies"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    source_subsystem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_subsystem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_subsystems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="dependencies")
    source_subsystem = relationship("EngineeringSubsystem", foreign_keys=[source_subsystem_id])
    target_subsystem = relationship("EngineeringSubsystem", foreign_keys=[target_subsystem_id])


class EngineeringOperatingMode(Base, UUIDMixin, AuditTimestampMixin):
    """
    System operating mode defining active/inactive subsystems and expected domains.
    """
    __tablename__ = "engineering_operating_modes"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_subsystem_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    inactive_subsystem_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expected_power_domain_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    relevant_interface_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    operating_conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="operating_modes")


class EngineeringModeTransition(Base, UUIDMixin, AuditTimestampMixin):
    """
    Deterministic transition rules between operating modes.
    """
    __tablename__ = "engineering_mode_transitions"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    source_mode_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_operating_modes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    destination_mode_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_operating_modes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    trigger: Mapped[str] = mapped_column(String(255), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    required_subsystems: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    forbidden_conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="mode_transitions")
    source_mode = relationship("EngineeringOperatingMode", foreign_keys=[source_mode_id])
    destination_mode = relationship("EngineeringOperatingMode", foreign_keys=[destination_mode_id])


class EngineeringSystemRequirement(Base, UUIDMixin, AuditTimestampMixin):
    """
    System-level engineering requirement linked to Wave 6 sources.
    """
    __tablename__ = "engineering_system_requirements"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(64), default=SystemRequirementType.FUNCTIONAL.value, nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=SystemRequirementStatus.UNKNOWN.value, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="requirements")


class EngineeringSystemAnalysis(Base, UUIDMixin, AuditTimestampMixin):
    """
    Immutable, revision-bound system analysis record.
    """
    __tablename__ = "engineering_system_analyses"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    subsystem_revisions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    circuit_revisions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    engine_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    inputs_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ANALYSIS_COMPLETE", nullable=False)
    is_stale: Mapped[bool] = mapped_column(default=False, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="analyses")
    findings = relationship("EngineeringSystemFinding", back_populates="analysis", cascade="all, delete-orphan", lazy="selectin")


class EngineeringSystemFinding(Base, UUIDMixin, AuditTimestampMixin):
    """
    Deterministic system-level finding without arbitrary risk scores.
    """
    __tablename__ = "engineering_system_findings"

    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_system_analyses.id", ondelete="CASCADE"),
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
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)  # INFO, WARNING, CRITICAL
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_subsystems: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    affected_interfaces: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    affected_power_domains: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    calculation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    analysis = relationship("EngineeringSystemAnalysis", back_populates="findings")
    system = relationship("EngineeringSystem")


class EngineeringSystemSnapshot(Base, UUIDMixin, AuditTimestampMixin):
    """
    Immutable architecture snapshot capturing full subsystem hierarchy and contracts.
    """
    __tablename__ = "engineering_system_snapshots"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    system = relationship("EngineeringSystem", back_populates="snapshots")
