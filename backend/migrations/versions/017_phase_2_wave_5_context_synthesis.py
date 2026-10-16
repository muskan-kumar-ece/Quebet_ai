"""Phase 2 Wave 5: Engineering Context Synthesis & Cognitive State

Revision ID: 017_phase_2_wave_5_context_synthesis
Revises: 016_phase_2_wave_4_engineering_memory
Create Date: 2026-10-06 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "017_phase_2_wave_5_context_synthesis"
down_revision: Union[str, None] = "016_phase_2_wave_4_engineering_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_context_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("base_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("context_snapshot_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), server_default="CURRENT", nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("current_state", sa.JSON(), nullable=False),
        sa.Column("authoritative_facts", sa.JSON(), nullable=False),
        sa.Column("deterministic_results", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("evidence_state", sa.JSON(), nullable=False),
        sa.Column("verification_state", sa.JSON(), nullable=False),
        sa.Column("decision_history", sa.JSON(), nullable=False),
        sa.Column("historical_memory", sa.JSON(), nullable=False),
        sa.Column("traceability_state", sa.JSON(), nullable=False),
        sa.Column("reflection_state", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_ctx_snap_tenant_id", "engineering_context_snapshots", ["tenant_id"])
    op.create_index("ix_eng_ctx_snap_project_id", "engineering_context_snapshots", ["project_id"])
    op.create_index("ix_eng_ctx_snap_status", "engineering_context_snapshots", ["status"])
    op.create_index("ix_eng_ctx_snap_digest", "engineering_context_snapshots", ["canonical_digest"])


def downgrade() -> None:
    op.drop_index("ix_eng_ctx_snap_digest", table_name="engineering_context_snapshots")
    op.drop_index("ix_eng_ctx_snap_status", table_name="engineering_context_snapshots")
    op.drop_index("ix_eng_ctx_snap_project_id", table_name="engineering_context_snapshots")
    op.drop_index("ix_eng_ctx_snap_tenant_id", table_name="engineering_context_snapshots")
    op.drop_table("engineering_context_snapshots")
