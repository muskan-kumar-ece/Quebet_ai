"""Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence

Revision ID: 024_phase_3_wave_7_dfm
Revises: 023_phase_3_wave_6_bom
Create Date: 2026-10-08 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "024_phase_3_wave_7_dfm"
down_revision: Union[str, None] = "023_phase_3_wave_6_bom"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Manufacturing Rule Sets
    op.create_table(
        "manufacturing_rule_sets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_revision", sa.String(length=64), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manufacturing_rule_sets_tenant_id", "manufacturing_rule_sets", ["tenant_id"])

    # 2. Manufacturing Analyses
    op.create_table(
        "manufacturing_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("board_revision", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("rule_set_id", sa.String(length=36), nullable=False),
        sa.Column("rule_set_revision", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("provenance_digest", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_set_id"], ["manufacturing_rule_sets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manufacturing_analyses_board_id", "manufacturing_analyses", ["board_id"])
    op.create_index("ix_manufacturing_analyses_circuit_id", "manufacturing_analyses", ["circuit_id"])
    op.create_index("ix_manufacturing_analyses_tenant_id", "manufacturing_analyses", ["tenant_id"])
    op.create_index("ix_manufacturing_analyses_rule_set_id", "manufacturing_analyses", ["rule_set_id"])
    op.create_index("ix_manufacturing_analyses_status", "manufacturing_analyses", ["status"])

    # 3. Manufacturing Proposals
    op.create_table(
        "manufacturing_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("board_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mutation_type", sa.String(length=64), nullable=False),
        sa.Column("proposed_mutations", sa.JSON(), nullable=False),
        sa.Column("diff_preview", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["manufacturing_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manufacturing_proposals_board_id", "manufacturing_proposals", ["board_id"])
    op.create_index("ix_manufacturing_proposals_tenant_id", "manufacturing_proposals", ["tenant_id"])
    op.create_index("ix_manufacturing_proposals_analysis_id", "manufacturing_proposals", ["analysis_id"])
    op.create_index("ix_manufacturing_proposals_status", "manufacturing_proposals", ["status"])


def downgrade() -> None:
    op.drop_table("manufacturing_proposals")
    op.drop_table("manufacturing_analyses")
    op.drop_table("manufacturing_rule_sets")
