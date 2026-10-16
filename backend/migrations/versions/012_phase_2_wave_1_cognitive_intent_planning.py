"""Phase 2 Wave 1: Cognitive Engineering Intent & Planning Foundation

Revision ID: 012_phase_2_wave_1_cognitive_intent_planning
Revises: 011_phase_1_wave_9_requirements_decisions
Create Date: 2026-10-04 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "012_phase_2_wave_1_cognitive_intent_planning"
down_revision: Union[str, None] = "011_phase_1_wave_9_requirements_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_intent_packets
    op.create_table(
        "engineering_intent_packets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("raw_request", sa.Text(), nullable=False),
        sa.Column("intent_type", sa.String(64), server_default="UNKNOWN", nullable=False),
        sa.Column("intent_subtype", sa.String(64), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("requested_action", sa.String(128), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("scenarios", sa.JSON(), nullable=False),
        sa.Column("affected_objects", sa.JSON(), nullable=False),
        sa.Column("urgency", sa.String(32), server_default="NORMAL", nullable=False),
        sa.Column("scope", sa.String(32), server_default="CIRCUIT", nullable=False),
        sa.Column("context_confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("ambiguities", sa.JSON(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(64), server_default="USER_PROMPT", nullable=False),
        sa.Column("status", sa.String(32), server_default="INTERPRETED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_intent_tenant_id", "engineering_intent_packets", ["tenant_id"])
    op.create_index("ix_eng_intent_project_id", "engineering_intent_packets", ["project_id"])

    # 2. engineering_task_plans
    op.create_table(
        "engineering_task_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("intent_packet_id", sa.String(36), sa.ForeignKey("engineering_intent_packets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("base_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("execution_policy", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("blocking_reasons", sa.JSON(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_plan_tenant_id", "engineering_task_plans", ["tenant_id"])
    op.create_index("ix_eng_plan_intent_id", "engineering_task_plans", ["intent_packet_id"])
    op.create_index("ix_eng_plan_project_id", "engineering_task_plans", ["project_id"])

    # 3. engineering_tasks
    op.create_table(
        "engineering_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("engineering_task_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent_packet_id", sa.String(36), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_objects", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("required_capabilities", sa.JSON(), nullable=False),
        sa.Column("required_inputs", sa.JSON(), nullable=False),
        sa.Column("expected_outputs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_task_plan_id", "engineering_tasks", ["plan_id"])
    op.create_index("ix_eng_task_intent_id", "engineering_tasks", ["intent_packet_id"])

    # 4. engineering_task_dependencies
    op.create_table(
        "engineering_task_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("engineering_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depends_on_task_id", sa.String(36), sa.ForeignKey("engineering_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dependency_type", sa.String(32), server_default="FINISH_TO_START", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_dep_task_id", "engineering_task_dependencies", ["task_id"])
    op.create_index("ix_eng_dep_depends_on", "engineering_task_dependencies", ["depends_on_task_id"])

    # 5. engineering_cognitive_executions
    op.create_table(
        "engineering_cognitive_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("engineering_task_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent_packet_id", sa.String(36), nullable=False),
        sa.Column("execution_status", sa.String(32), server_default="SUCCESS", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("requirements_affected", sa.JSON(), nullable=False),
        sa.Column("constraints_affected", sa.JSON(), nullable=False),
        sa.Column("verification_impacts", sa.JSON(), nullable=False),
        sa.Column("traceability", sa.JSON(), nullable=False),
        sa.Column("human_actions_required", sa.JSON(), nullable=False),
        sa.Column("blocking_reasons", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_exec_tenant_id", "engineering_cognitive_executions", ["tenant_id"])
    op.create_index("ix_eng_exec_plan_id", "engineering_cognitive_executions", ["plan_id"])

    # 6. engineering_cognitive_provenance
    op.create_table(
        "engineering_cognitive_provenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("cognitive_execution_id", sa.String(36), sa.ForeignKey("engineering_cognitive_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent_packet_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("model_provider", sa.String(64), server_default="QUEBET_COGNITIVE_ROUTER", nullable=False),
        sa.Column("model_identifier", sa.String(128), server_default="deterministic-rule-engine-v1", nullable=False),
        sa.Column("prompt_version", sa.String(32), server_default="v1.0.0", nullable=False),
        sa.Column("schema_version", sa.String(32), server_default="v1.0.0", nullable=False),
        sa.Column("capability_versions", sa.JSON(), nullable=False),
        sa.Column("deterministic_engine_versions", sa.JSON(), nullable=False),
        sa.Column("knowledge_snapshot_id", sa.String(36), nullable=True),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_prov_tenant_id", "engineering_cognitive_provenance", ["tenant_id"])
    op.create_index("ix_eng_prov_exec_id", "engineering_cognitive_provenance", ["cognitive_execution_id"])


def downgrade() -> None:
    op.drop_table("engineering_cognitive_provenance")
    op.drop_table("engineering_cognitive_executions")
    op.drop_table("engineering_task_dependencies")
    op.drop_table("engineering_tasks")
    op.drop_table("engineering_task_plans")
    op.drop_table("engineering_intent_packets")
