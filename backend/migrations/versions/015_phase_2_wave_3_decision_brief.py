"""Phase 2 Wave 3: Controlled Engineering Decision Preparation

Revision ID: 015_phase_2_wave_3_decision_brief
Revises: 014_phase_2_wave_2_cognitive_reflection
Create Date: 2026-10-05 23:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "015_phase_2_wave_3_decision_brief"
down_revision: Union[str, None] = "014_phase_2_wave_2_cognitive_reflection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_decision_briefs
    op.create_table(
        "engineering_decision_briefs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), nullable=True),
        sa.Column("circuit_id", sa.String(36), nullable=True),
        sa.Column("base_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("context_snapshot_id", sa.String(36), nullable=True),
        sa.Column("reflection_id", sa.String(36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(64), server_default="SYSTEM", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("alternative_ids", sa.JSON(), nullable=False),
        sa.Column("alternatives_data", sa.JSON(), nullable=False),
        sa.Column("requirement_summary", sa.JSON(), nullable=False),
        sa.Column("constraint_summary", sa.JSON(), nullable=False),
        sa.Column("tradeoff_summary", sa.JSON(), nullable=False),
        sa.Column("risk_findings", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("evidence_gaps", sa.JSON(), nullable=False),
        sa.Column("verification_gaps", sa.JSON(), nullable=False),
        sa.Column("consequences", sa.JSON(), nullable=False),
        sa.Column("decision_questions", sa.JSON(), nullable=False),
        sa.Column("human_decision_required", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("decision_record_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_dec_briefs_tenant_id", "engineering_decision_briefs", ["tenant_id"])
    op.create_index("ix_eng_dec_briefs_project_id", "engineering_decision_briefs", ["project_id"])

    # 2. engineering_decision_brief_provenance
    op.create_table(
        "engineering_decision_brief_provenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "decision_brief_id",
            sa.String(36),
            sa.ForeignKey("engineering_decision_briefs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context_snapshot_id", sa.String(36), nullable=True),
        sa.Column("reflection_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=False),
        sa.Column("prompt_id", sa.String(64), server_default="decision_brief", nullable=False),
        sa.Column("prompt_version", sa.String(32), server_default="v1", nullable=False),
        sa.Column("rule_set_version", sa.String(32), server_default="v1.0.0", nullable=False),
        sa.Column("engine_versions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eng_dec_brief_prov_tenant_id", "engineering_decision_brief_provenance", ["tenant_id"])
    op.create_index("ix_eng_dec_brief_prov_brief_id", "engineering_decision_brief_provenance", ["decision_brief_id"])
    op.create_index("ix_eng_dec_brief_prov_project_id", "engineering_decision_brief_provenance", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_eng_dec_brief_prov_project_id", table_name="engineering_decision_brief_provenance")
    op.drop_index("ix_eng_dec_brief_prov_brief_id", table_name="engineering_decision_brief_provenance")
    op.drop_index("ix_eng_dec_brief_prov_tenant_id", table_name="engineering_decision_brief_provenance")
    op.drop_table("engineering_decision_brief_provenance")

    op.drop_index("ix_eng_dec_briefs_project_id", table_name="engineering_decision_briefs")
    op.drop_index("ix_eng_dec_briefs_tenant_id", table_name="engineering_decision_briefs")
    op.drop_table("engineering_decision_briefs")
