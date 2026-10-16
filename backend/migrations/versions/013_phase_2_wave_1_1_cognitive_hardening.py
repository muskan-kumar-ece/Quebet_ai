"""Phase 2 Wave 1.1: Cognitive Foundation Hardening & Contract Reconciliation

Revision ID: 013_phase_2_wave_1_1_cognitive_hardening
Revises: 012_phase_2_wave_1_cognitive_intent_planning
Create Date: 2026-10-05 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "013_phase_2_wave_1_1_cognitive_hardening"
down_revision: Union[str, None] = "012_phase_2_wave_1_cognitive_intent_planning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_cognitive_context_snapshots
    op.create_table(
        "engineering_cognitive_context_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("system_revision", sa.Integer(), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("circuit_revision", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.String(36), nullable=True),
        sa.Column("requirement_baseline_id", sa.String(36), nullable=True),
        sa.Column("knowledge_snapshot_id", sa.String(36), nullable=True),
        sa.Column("assumption_ids", sa.JSON(), nullable=False),
        sa.Column("scenario_ids", sa.JSON(), nullable=False),
        sa.Column("engine_versions", sa.JSON(), nullable=False),
        sa.Column("rule_set_version", sa.String(32), server_default="v1.0.0", nullable=False),
        sa.Column("context_digest", sa.String(64), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_cog_ctx_snap_tenant_id", "engineering_cognitive_context_snapshots", ["tenant_id"])
    op.create_index("ix_eng_cog_ctx_snap_project_id", "engineering_cognitive_context_snapshots", ["project_id"])
    op.create_index("ix_eng_cog_ctx_snap_digest", "engineering_cognitive_context_snapshots", ["context_digest"])

    # 2. Add context_snapshot_id to engineering_task_plans
    op.add_column("engineering_task_plans", sa.Column("context_snapshot_id", sa.String(36), nullable=True))

    # 3. Add context_snapshot_id, prompt_id, rule_set_version to engineering_cognitive_provenance
    op.add_column("engineering_cognitive_provenance", sa.Column("context_snapshot_id", sa.String(36), nullable=True))
    op.add_column(
        "engineering_cognitive_provenance",
        sa.Column("prompt_id", sa.String(64), server_default="intent_resolver", nullable=False),
    )
    op.add_column(
        "engineering_cognitive_provenance",
        sa.Column("rule_set_version", sa.String(32), server_default="v1.0.0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("engineering_cognitive_provenance", "rule_set_version")
    op.drop_column("engineering_cognitive_provenance", "prompt_id")
    op.drop_column("engineering_cognitive_provenance", "context_snapshot_id")
    op.drop_column("engineering_task_plans", "context_snapshot_id")
    op.drop_index("ix_eng_cog_ctx_snap_digest", table_name="engineering_cognitive_context_snapshots")
    op.drop_index("ix_eng_cog_ctx_snap_project_id", table_name="engineering_cognitive_context_snapshots")
    op.drop_index("ix_eng_cog_ctx_snap_tenant_id", table_name="engineering_cognitive_context_snapshots")
    op.drop_table("engineering_cognitive_context_snapshots")
