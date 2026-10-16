"""Phase 2 Wave 2: Cognitive Reflection & Engineering Reasoning

Revision ID: 014_phase_2_wave_2_cognitive_reflection
Revises: 013_phase_2_wave_1_1_cognitive_hardening
Create Date: 2026-10-05 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "014_phase_2_wave_2_cognitive_reflection"
down_revision: Union[str, None] = "013_phase_2_wave_1_1_cognitive_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_reflections
    op.create_table(
        "engineering_reflections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("base_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "execution_id",
            sa.String(36),
            sa.ForeignKey("engineering_cognitive_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("engineering_task_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context_snapshot_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("reflection_cycle", sa.Integer(), server_default="1", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("has_contradictions", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("has_unresolved_unknowns", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("has_evidence_gaps", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("has_requirement_gaps", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("has_verification_gaps", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("additional_work_required", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("proposed_follow_up_tasks", sa.JSON(), nullable=False),
        sa.Column("follow_up_plan_id", sa.String(36), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_reflections_tenant_id", "engineering_reflections", ["tenant_id"])
    op.create_index("ix_eng_reflections_project_id", "engineering_reflections", ["project_id"])
    op.create_index("ix_eng_reflections_execution_id", "engineering_reflections", ["execution_id"])
    op.create_index("ix_eng_reflections_plan_id", "engineering_reflections", ["plan_id"])

    # 2. engineering_reasoning_findings
    op.create_table(
        "engineering_reasoning_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "reflection_id",
            sa.String(36),
            sa.ForeignKey("engineering_reflections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), server_default="WARNING", nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_entity_type", sa.String(64), nullable=False),
        sa.Column("affected_entity_id", sa.String(36), nullable=True),
        sa.Column("evidence_references", sa.JSON(), nullable=False),
        sa.Column("deterministic_facts", sa.JSON(), nullable=False),
        sa.Column("recommended_remedy", sa.Text(), nullable=True),
        sa.Column("follow_up_capability", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_reasoning_findings_reflection_id", "engineering_reasoning_findings", ["reflection_id"])

    # 3. engineering_reflection_provenance
    op.create_table(
        "engineering_reflection_provenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "reflection_id",
            sa.String(36),
            sa.ForeignKey("engineering_reflections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("context_snapshot_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=False),
        sa.Column("prompt_id", sa.String(64), server_default="engineering_reflection", nullable=False),
        sa.Column("prompt_version", sa.String(32), server_default="v1.0.0", nullable=False),
        sa.Column("rule_set_version", sa.String(32), server_default="v1.0.0", nullable=False),
        sa.Column("engine_versions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_refl_prov_tenant_id", "engineering_reflection_provenance", ["tenant_id"])
    op.create_index("ix_eng_refl_prov_reflection_id", "engineering_reflection_provenance", ["reflection_id"])
    op.create_index("ix_eng_refl_prov_project_id", "engineering_reflection_provenance", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_eng_refl_prov_project_id", table_name="engineering_reflection_provenance")
    op.drop_index("ix_eng_refl_prov_reflection_id", table_name="engineering_reflection_provenance")
    op.drop_index("ix_eng_refl_prov_tenant_id", table_name="engineering_reflection_provenance")
    op.drop_table("engineering_reflection_provenance")

    op.drop_index("ix_eng_reasoning_findings_reflection_id", table_name="engineering_reasoning_findings")
    op.drop_table("engineering_reasoning_findings")

    op.drop_index("ix_eng_reflections_plan_id", table_name="engineering_reflections")
    op.drop_index("ix_eng_reflections_execution_id", table_name="engineering_reflections")
    op.drop_index("ix_eng_reflections_project_id", table_name="engineering_reflections")
    op.drop_index("ix_eng_reflections_tenant_id", table_name="engineering_reflections")
    op.drop_table("engineering_reflections")
