"""Phase 3 Wave 6: BOM & Supply-Chain Intelligence

Revision ID: 023_phase_3_wave_6_bom
Revises: 022_phase_3_wave_5_pcb
Create Date: 2026-10-08 18:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "023_phase_3_wave_6_bom"
down_revision: Union[str, None] = "022_phase_3_wave_5_pcb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Engineering BOMs
    op.create_table(
        "engineering_boms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=True),
        sa.Column("board_version", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_lines", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("integrity_digest", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_boms_tenant_id", "engineering_boms", ["tenant_id"])
    op.create_index("ix_engineering_boms_project_id", "engineering_boms", ["project_id"])
    op.create_index("ix_engineering_boms_circuit_id", "engineering_boms", ["circuit_id"])
    op.create_index("ix_engineering_boms_board_id", "engineering_boms", ["board_id"])
    op.create_index("ix_engineering_boms_status", "engineering_boms", ["status"])

    # 2. Engineering BOM Lines
    op.create_table(
        "engineering_bom_lines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bom_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=True),
        sa.Column("reference_designator", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("component_type", sa.String(length=64), nullable=False),
        sa.Column("design_value", sa.String(length=64), nullable=False),
        sa.Column("design_package", sa.String(length=64), nullable=True),
        sa.Column("design_tolerance", sa.String(length=32), nullable=True),
        sa.Column("design_rating", sa.String(length=64), nullable=True),
        sa.Column("footprint_name", sa.String(length=128), nullable=True),
        sa.Column("engineering_requirements", sa.JSON(), nullable=False),
        sa.Column("manufacturer", sa.String(length=128), nullable=True),
        sa.Column("manufacturer_part_number", sa.String(length=128), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bom_id"], ["engineering_boms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["component_id"], ["components.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_bom_lines_bom_id", "engineering_bom_lines", ["bom_id"])
    op.create_index("ix_engineering_bom_lines_component_id", "engineering_bom_lines", ["component_id"])
    op.create_index("ix_engineering_bom_lines_ref_des", "engineering_bom_lines", ["reference_designator"])

    # 3. Component Part Candidates
    op.create_table(
        "component_part_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bom_line_id", sa.String(length=36), nullable=False),
        sa.Column("manufacturer", sa.String(length=128), nullable=False),
        sa.Column("mpn", sa.String(length=128), nullable=False),
        sa.Column("package", sa.String(length=128), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("datasheet_url", sa.String(length=512), nullable=True),
        sa.Column("compatibility_status", sa.String(length=32), nullable=False),
        sa.Column("compatibility_evaluations", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("availability_status", sa.String(length=32), nullable=False),
        sa.Column("lead_time_weeks", sa.Integer(), nullable=True),
        sa.Column("supply_sources", sa.JSON(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bom_line_id"], ["engineering_bom_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_component_part_candidates_bom_line_id", "component_part_candidates", ["bom_line_id"])
    op.create_index("ix_component_part_candidates_mpn", "component_part_candidates", ["mpn"])

    # 4. BOM Substitution Proposals
    op.create_table(
        "bom_substitution_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bom_id", sa.String(length=36), nullable=False),
        sa.Column("bom_line_id", sa.String(length=36), nullable=False),
        sa.Column("base_bom_revision", sa.Integer(), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("proposed_mpn", sa.String(length=128), nullable=False),
        sa.Column("proposed_manufacturer", sa.String(length=128), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("diff_preview", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bom_id"], ["engineering_boms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bom_line_id"], ["engineering_bom_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bom_substitution_proposals_bom_id", "bom_substitution_proposals", ["bom_id"])
    op.create_index("ix_bom_substitution_proposals_bom_line_id", "bom_substitution_proposals", ["bom_line_id"])
    op.create_index("ix_bom_substitution_proposals_tenant_id", "bom_substitution_proposals", ["tenant_id"])
    op.create_index("ix_bom_substitution_proposals_status", "bom_substitution_proposals", ["status"])


def downgrade() -> None:
    op.drop_table("bom_substitution_proposals")
    op.drop_table("component_part_candidates")
    op.drop_table("engineering_bom_lines")
    op.drop_table("engineering_boms")
