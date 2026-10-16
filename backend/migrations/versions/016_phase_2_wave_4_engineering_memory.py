"""Phase 2 Wave 4: Engineering Memory, Decision History & Contextual Learning

Revision ID: 016_phase_2_wave_4_engineering_memory
Revises: 015_phase_2_wave_3_decision_brief
Create Date: 2026-10-06 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "016_phase_2_wave_4_engineering_memory"
down_revision: Union[str, None] = "015_phase_2_wave_3_decision_brief"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_memory_records
    op.create_table(
        "engineering_memory_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("source_entity_type", sa.String(64), nullable=False),
        sa.Column("source_entity_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("engineering_domain", sa.String(64), server_default="general", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("applicability_conditions", sa.JSON(), nullable=False),
        sa.Column("revision_context", sa.JSON(), nullable=False),
        sa.Column("historical_outcome", sa.String(32), server_default="UNRESOLVED", nullable=False),
        sa.Column("is_conflicting", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("conflict_details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_memory_tenant_id", "engineering_memory_records", ["tenant_id"])
    op.create_index("ix_eng_memory_project_id", "engineering_memory_records", ["project_id"])
    op.create_index("ix_eng_memory_memory_type", "engineering_memory_records", ["memory_type"])
    op.create_index("ix_eng_memory_domain", "engineering_memory_records", ["engineering_domain"])
    op.create_index("ix_eng_memory_source_entity_id", "engineering_memory_records", ["source_entity_id"])

    # 2. engineering_memory_feedback
    op.create_table(
        "engineering_memory_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "memory_id",
            sa.String(36),
            sa.ForeignKey("engineering_memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engineer_identity", sa.String(128), nullable=False),
        sa.Column("feedback_type", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_mem_fb_tenant_id", "engineering_memory_feedback", ["tenant_id"])
    op.create_index("ix_eng_mem_fb_memory_id", "engineering_memory_feedback", ["memory_id"])


def downgrade() -> None:
    op.drop_index("ix_eng_mem_fb_memory_id", table_name="engineering_memory_feedback")
    op.drop_index("ix_eng_mem_fb_tenant_id", table_name="engineering_memory_feedback")
    op.drop_table("engineering_memory_feedback")

    op.drop_index("ix_eng_memory_source_entity_id", table_name="engineering_memory_records")
    op.drop_index("ix_eng_memory_domain", table_name="engineering_memory_records")
    op.drop_index("ix_eng_memory_memory_type", table_name="engineering_memory_records")
    op.drop_index("ix_eng_memory_project_id", table_name="engineering_memory_records")
    op.drop_index("ix_eng_memory_tenant_id", table_name="engineering_memory_records")
    op.drop_table("engineering_memory_records")
