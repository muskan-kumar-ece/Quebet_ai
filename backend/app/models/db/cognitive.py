from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, UUIDMixin, TimestampMixin


class IntentType(str, Enum):
    ANALYZE_CIRCUIT = "ANALYZE_CIRCUIT"
    ANALYZE_SYSTEM = "ANALYZE_SYSTEM"
    EXPLAIN_ENGINEERING_RESULT = "EXPLAIN_ENGINEERING_RESULT"
    INVESTIGATE_FINDING = "INVESTIGATE_FINDING"
    INVESTIGATE_FAILURE = "INVESTIGATE_FAILURE"
    EXPLORE_DESIGN_ALTERNATIVES = "EXPLORE_DESIGN_ALTERNATIVES"
    EXPLORE_SYSTEM_ALTERNATIVES = "EXPLORE_SYSTEM_ALTERNATIVES"
    CHECK_REQUIREMENTS = "CHECK_REQUIREMENTS"
    CHECK_CONSTRAINTS = "CHECK_CONSTRAINTS"
    PLAN_VERIFICATION = "PLAN_VERIFICATION"
    REVIEW_DESIGN = "REVIEW_DESIGN"
    TRACE_ENGINEERING_FACT = "TRACE_ENGINEERING_FACT"
    COMPARE_ALTERNATIVES = "COMPARE_ALTERNATIVES"
    UNDERSTAND_COMPONENT = "UNDERSTAND_COMPONENT"
    UNDERSTAND_SYSTEM = "UNDERSTAND_SYSTEM"
    CREATE_PROPOSAL = "CREATE_PROPOSAL"
    REVIEW_PROPOSAL = "REVIEW_PROPOSAL"
    UNKNOWN = "UNKNOWN"


class IntentStatus(str, Enum):
    INTERPRETED = "INTERPRETED"
    CONFIRMED = "CONFIRMED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    PLANNING_BLOCKED = "PLANNING_BLOCKED"
    REJECTED = "REJECTED"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    RESOLUTION_REQUIRED = "RESOLUTION_REQUIRED"
    READY_FOR_VALIDATION = "READY_FOR_VALIDATION"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATED = "VALIDATED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ReflectionStatus(str, Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    COMPLETE = "COMPLETE"
    ADDITIONAL_WORK_REQUIRED = "ADDITIONAL_WORK_REQUIRED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    FAILED = "FAILED"


class ReasoningFindingType(str, Enum):
    MISSING_INFORMATION = "MISSING_INFORMATION"
    UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN"
    CONTRADICTORY_RESULT = "CONTRADICTORY_RESULT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REQUIREMENT_GAP = "REQUIREMENT_GAP"
    VERIFICATION_GAP = "VERIFICATION_GAP"
    ASSUMPTION_CONFLICT = "ASSUMPTION_CONFLICT"
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"
    STALE_CONTEXT = "STALE_CONTEXT"
    INCOMPLETE_ANALYSIS = "INCOMPLETE_ANALYSIS"
    CONSTRAINT_GAP = "CONSTRAINT_GAP"
    TRACEABILITY_GAP = "TRACEABILITY_GAP"


class ReasoningFindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DecisionBriefStatus(str, Enum):
    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    DECIDED = "DECIDED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"


class HumanDecisionType(str, Enum):
    ACCEPT_ALTERNATIVE = "ACCEPT_ALTERNATIVE"
    ADOPT_ALTERNATIVE = "ADOPT_ALTERNATIVE"
    REJECT_ALTERNATIVES = "REJECT_ALTERNATIVES"
    REJECT_ALL = "REJECT_ALL"
    REQUEST_MORE_ANALYSIS = "REQUEST_MORE_ANALYSIS"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    DEFER_DECISION = "DEFER_DECISION"
    CHANGE_REQUIREMENT = "CHANGE_REQUIREMENT"
    CHANGE_CONSTRAINT = "CHANGE_CONSTRAINT"


class EngineeringCognitiveContextSnapshot(Base, UUIDMixin, TimestampMixin):
    """
    Immutable snapshot of the authoritative engineering context used to synthesize
    a cognitive engineering task plan.
    Integrity is protected by a canonical SHA-256 digest over ordered references.
    """
    __tablename__ = "engineering_cognitive_context_snapshots"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    system_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    system_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    circuit_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    analysis_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    requirement_baseline_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    knowledge_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    assumption_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    scenario_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    engine_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)

    context_digest: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    context_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EngineeringIntentPacket(Base, UUIDMixin, TimestampMixin):
    """
    First-class structured representation of the engineer's intent.
    Never acts as authoritative engineering truth.
    """
    __tablename__ = "engineering_intent_packets"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    system_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    raw_request: Mapped[str] = mapped_column(Text, nullable=False)
    intent_type: Mapped[str] = mapped_column(String(64), default=IntentType.UNKNOWN.value, nullable=False)
    intent_subtype: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    goal: Mapped[str] = mapped_column(Text, nullable=False)
    requested_action: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    entities: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    requirements: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    constraints: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    assumptions: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    scenarios: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    affected_objects: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    urgency: Mapped[str] = mapped_column(String(32), default="NORMAL", nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="CIRCUIT", nullable=False)

    context_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    ambiguities: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    missing_information: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    source: Mapped[str] = mapped_column(String(64), default="USER_PROMPT", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=IntentStatus.INTERPRETED.value, nullable=False)


class EngineeringTaskPlan(Base, UUIDMixin, TimestampMixin):
    """
    Structured, revision-bound engineering task plan formed from intent and context.
    """
    __tablename__ = "engineering_task_plans"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    intent_packet_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_intent_packets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    system_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    context_snapshot_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("engineering_cognitive_context_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    execution_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default=PlanStatus.DRAFT.value, nullable=False)
    blocking_reasons: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tasks = relationship("EngineeringTask", backref="plan", lazy="selectin", cascade="all, delete-orphan")


class EngineeringTask(Base, UUIDMixin, TimestampMixin):
    """
    Individual engineering task node within a directed acyclic task graph.
    """
    __tablename__ = "engineering_tasks"

    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_task_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    intent_packet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    target_objects: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    dependencies: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    required_capabilities: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    required_inputs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    expected_outputs: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.PENDING.value, nullable=False)
    blocking_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EngineeringTaskDependency(Base, UUIDMixin, TimestampMixin):
    """
    Dependency relationship between tasks in the task plan.
    """
    __tablename__ = "engineering_task_dependencies"

    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    depends_on_task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String(32), default="FINISH_TO_START", nullable=False)


class EngineeringCognitiveExecution(Base, UUIDMixin, TimestampMixin):
    """
    Records deterministic capability execution results, findings, and explanations.
    """
    __tablename__ = "engineering_cognitive_executions"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_task_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    intent_packet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    execution_status: Mapped[str] = mapped_column(String(32), default=ExecutionStatus.SUCCESS.value, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    findings: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    requirements_affected: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    constraints_affected: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    verification_impacts: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    traceability: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    human_actions_required: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    blocking_reasons: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EngineeringCognitiveProvenance(Base, UUIDMixin, TimestampMixin):
    """
    Auditable provenance record for cognitive plan generation and execution.
    """
    __tablename__ = "engineering_cognitive_provenance"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cognitive_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_cognitive_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    intent_packet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    system_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    model_provider: Mapped[str] = mapped_column(String(64), default="QUEBET_COGNITIVE_ROUTER", nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(128), default="deterministic-rule-engine-v1", nullable=False)

    prompt_id: Mapped[str] = mapped_column(String(64), default="intent_resolver", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)

    capability_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    deterministic_engine_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)

    knowledge_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class EngineeringReflection(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative record of cognitive reflection on deterministic execution results.
    Identifies contradictions, unresolved unknowns, evidence gaps, requirement gaps,
    and verification gaps. Bounded by revision and reflection cycle limits.
    """
    __tablename__ = "engineering_reflections"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_cognitive_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_task_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=ReflectionStatus.PENDING.value, nullable=False)
    reflection_cycle: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    has_contradictions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_unresolved_unknowns: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_evidence_gaps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_requirement_gaps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_verification_gaps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    additional_work_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proposed_follow_up_tasks: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    follow_up_plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    findings = relationship("EngineeringReasoningFinding", backref="reflection", lazy="selectin", cascade="all, delete-orphan")


class EngineeringReasoningFinding(Base, UUIDMixin, TimestampMixin):
    """
    Discrete engineering reasoning finding identified during reflection.
    Tied deterministically to engineering facts, requirements, or evidence.
    """
    __tablename__ = "engineering_reasoning_findings"

    reflection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_reflections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default=ReasoningFindingSeverity.WARNING.value, nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    affected_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    evidence_references: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    deterministic_facts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    recommended_remedy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_capability: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class EngineeringReflectionProvenance(Base, UUIDMixin, TimestampMixin):
    """
    Auditable provenance record for engineering reflection and reasoning cycles.
    """
    __tablename__ = "engineering_reflection_provenance"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    reflection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_reflections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    prompt_id: Mapped[str] = mapped_column(String(64), default="engineering_reflection", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    engine_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EngineeringDecisionBrief(Base, UUIDMixin, TimestampMixin):
    """
    Structured engineering decision brief synthesized from verified engineering facts,
    cognitive reflection findings, and deterministic alternative evaluations.
    Strictly advisory: final authority rests exclusively with the human engineer.
    """
    __tablename__ = "engineering_decision_briefs"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reflection_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=DecisionBriefStatus.DRAFT.value, nullable=False)

    alternative_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    alternatives_data: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    requirement_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    constraint_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tradeoff_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    risk_findings: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    evidence_gaps: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    verification_gaps: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    consequences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    decision_questions: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    human_decision_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    decision_record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class EngineeringDecisionBriefProvenance(Base, UUIDMixin, TimestampMixin):
    """
    Auditable cryptographic provenance record for decision brief synthesis.
    """
    __tablename__ = "engineering_decision_brief_provenance"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    decision_brief_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_briefs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reflection_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    prompt_id: Mapped[str] = mapped_column(String(64), default="decision_brief", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    engine_versions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MemoryType(str, Enum):
    DECISION_HISTORY = "DECISION_HISTORY"
    DESIGN_FINDING = "DESIGN_FINDING"
    VERIFICATION_LESSON = "VERIFICATION_LESSON"
    FAILURE_LESSON = "FAILURE_LESSON"
    ASSUMPTION_HISTORY = "ASSUMPTION_HISTORY"
    REQUIREMENT_HISTORY = "REQUIREMENT_HISTORY"
    TRADEOFF_HISTORY = "TRADEOFF_HISTORY"
    ENGINEERING_PATTERN = "ENGINEERING_PATTERN"


class HistoricalOutcome(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    UNRESOLVED = "UNRESOLVED"
    SUPERSEDED = "SUPERSEDED"


class MemoryApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    POTENTIALLY_APPLICABLE = "POTENTIALLY_APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class MemoryFeedbackType(str, Enum):
    USEFUL = "USEFUL"
    NOT_RELEVANT = "NOT_RELEVANT"
    INCORRECT_HISTORY = "INCORRECT_HISTORY"
    OUTDATED = "OUTDATED"
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EngineeringMemoryRecord(Base, UUIDMixin, TimestampMixin):
    """
    Controlled historical engineering memory record referencing authoritative entities.
    HISTORICAL MEMORY != ENGINEERING TRUTH.
    CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY.
    """
    __tablename__ = "engineering_memory_records"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    engineering_domain: Mapped[str] = mapped_column(String(64), index=True, default="general", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    applicability_conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    revision_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    historical_outcome: Mapped[str] = mapped_column(String(32), default=HistoricalOutcome.UNRESOLVED.value, nullable=False)

    is_conflicting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conflict_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EngineeringMemoryFeedback(Base, UUIDMixin, TimestampMixin):
    """
    Human engineer feedback on surfaced historical engineering memories.
    Feedback informs retrieval preferences without mutating authoritative knowledge.
    """
    __tablename__ = "engineering_memory_feedback"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    memory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_memory_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    engineer_identity: Mapped[str] = mapped_column(String(128), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ContextSnapshotStatus(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"


class ContextConflictCategory(str, Enum):
    SPECIFICATION_CONFLICT = "SPECIFICATION_CONFLICT"
    ANALYSIS_CONFLICT = "ANALYSIS_CONFLICT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    DECISION_CONFLICT = "DECISION_CONFLICT"
    ASSUMPTION_CONFLICT = "ASSUMPTION_CONFLICT"
    MEMORY_CONFLICT = "MEMORY_CONFLICT"
    REVISION_CONFLICT = "REVISION_CONFLICT"


class EngineeringContextSnapshot(Base, UUIDMixin, TimestampMixin):
    """
    Revision-bound, provenance-aware engineering context snapshot.
    Synthesizes the complete current engineering situation into a single, authoritative context.
    
    INVARIANTS:
    - STRUCTURED CONTEXT > AI EXPLANATION
    - CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
    - CALCULATED != PHYSICALLY VERIFIED
    - HISTORICAL VERIFICATION != CURRENT VERIFICATION
    - UNKNOWN != SATISFIED
    - CONTEXT SNAPSHOT = REVISION-BOUND
    """
    __tablename__ = "engineering_context_snapshots"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)

    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ContextSnapshotStatus.CURRENT.value, index=True, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    current_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    authoritative_facts: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    deterministic_results: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    requirements: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    constraints: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    assumptions: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    findings: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    evidence_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    verification_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    decision_history: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    historical_memory: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    traceability_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reflection_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    conflicts: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)


class CognitiveWorkflowStatus(str, Enum):
    RECEIVED = "RECEIVED"
    INTENT_RESOLVED = "INTENT_RESOLVED"
    CONTEXT_RESOLVED = "CONTEXT_RESOLVED"
    PLAN_READY = "PLAN_READY"
    EXECUTING = "EXECUTING"
    REFLECTING = "REFLECTING"
    ADDITIONAL_WORK_REQUIRED = "ADDITIONAL_WORK_REQUIRED"
    DECISION_PREPARATION = "DECISION_PREPARATION"
    CONTEXT_SYNTHESIS = "CONTEXT_SYNTHESIS"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    FAILED = "FAILED"


class EngineeringCognitiveWorkflow(Base, UUIDMixin, TimestampMixin):
    """
    Controlled orchestration lifecycle tracking for an end-to-end cognitive engineering workflow.
    Coordinates existing Phase 2 cognitive subsystems into one unified pipeline without duplicating truth.
    
    INVARIANTS:
    - AI ENGINEERING AUTHORITY = NONE
    - AI DECISION AUTHORITY = NONE
    - AUTONOMOUS MUTATION = DISABLED
    - REVISION-BOUND & CANONICAL INTEGRITY PROTECTED
    - ZERO SYNTHETIC SCORING
    """
    __tablename__ = "engineering_cognitive_workflows"

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    circuit_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)

    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=CognitiveWorkflowStatus.RECEIVED.value, index=True, nullable=False)
    current_step: Mapped[str] = mapped_column(String(64), default="INTENT_RESOLUTION", nullable=False)

    user_request: Mapped[str] = mapped_column(Text, nullable=False)

    intent_packet_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    context_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reflection_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decision_brief_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    synthesized_context_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    reflection_cycles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocking_reasons: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    timeline: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)
    integrity_digest: Mapped[str] = mapped_column(String(64), default="", nullable=False)



