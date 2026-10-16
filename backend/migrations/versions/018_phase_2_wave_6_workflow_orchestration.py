"""Phase 2 Wave 6: Cognitive Engineering Workflow Orchestration

Revision ID: 018_phase_2_wave_6_workflow_orchestration
Revises: 017_phase_2_wave_5_context_synthesis
Create Date: 2026-10-06 19:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "018_phase_2_wave_6_workflow_orchestration"
down_revision: Union[str, None] = "017_phase_2_wave_5_context_synthesis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_cognitive_workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("base_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="RECEIVED", nullable=False),
        sa.Column("current_step", sa.String(64), server_default="INTENT_RESOLUTION", nullable=False),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("intent_packet_id", sa.String(36), nullable=True),
        sa.Column("context_snapshot_id", sa.String(36), nullable=True),
        sa.Column("plan_id", sa.String(36), nullable=True),
        sa.Column("execution_id", sa.String(36), nullable=True),
        sa.Column("reflection_id", sa.String(36), nullable=True),
        sa.Column("decision_brief_id", sa.String(36), nullable=True),
        sa.Column("synthesized_context_id", sa.String(36), nullable=True),
        sa.Column("reflection_cycles", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocking_reasons", sa.JSON(), nullable=False),
        sa.Column("timeline", sa.JSON(), nullable=False),
        sa.Column("integrity_digest", sa.String(64), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_cog_wf_tenant_id", "engineering_cognitive_workflows", ["tenant_id"])
    op.create_index("ix_eng_cog_wf_project_id", "engineering_cognitive_workflows", ["project_id"])
    op.create_index("ix_eng_cog_wf_status", "engineering_cognitive_workflows", ["status"])


def downgrade() -> None:
    op.drop_index("ix_eng_cog_wf_status", table_name="engineering_cognitive_workflows")
    op.drop_index("ix_eng_cog_wf_project_id", table_name="engineering_cognitive_workflows")
    op.drop_index("ix_eng_cog_wf_tenant_id", table_name="engineering_cognitive_workflows")
    op.drop_table("engineering_cognitive_workflows")
