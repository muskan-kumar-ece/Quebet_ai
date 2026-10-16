"""Phase 3 Wave 5: PCB & Schematic Intelligence

Revision ID: 022_phase_3_wave_5_pcb
Revises: 021_phase_3_wave_4_simulation
Create Date: 2026-10-07 23:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "022_phase_3_wave_5_pcb"
down_revision: Union[str, None] = "021_phase_3_wave_4_simulation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Engineering Boards
    op.create_table(
        "engineering_boards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("units", sa.String(length=16), nullable=False),
        sa.Column("board_outline", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("integrity_digest", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_boards_tenant_id", "engineering_boards", ["tenant_id"])
    op.create_index("ix_engineering_boards_project_id", "engineering_boards", ["project_id"])
    op.create_index("ix_engineering_boards_circuit_id", "engineering_boards", ["circuit_id"])
    op.create_index("ix_engineering_boards_status", "engineering_boards", ["status"])

    # 2. Board Layers
    op.create_table(
        "board_layers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("layer_type", sa.String(length=32), nullable=False),
        sa.Column("layer_order", sa.Integer(), nullable=False),
        sa.Column("is_copper", sa.Boolean(), nullable=False),
        sa.Column("thickness_um", sa.Float(), nullable=True),
        sa.Column("dielectric_constant", sa.Float(), nullable=True),
        sa.Column("copper_weight_oz", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_layers_board_id", "board_layers", ["board_id"])

    # 3. Board Footprints
    op.create_table(
        "board_footprints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=True),
        sa.Column("ref_des", sa.String(length=64), nullable=False),
        sa.Column("footprint_name", sa.String(length=128), nullable=False),
        sa.Column("pos_x", sa.Float(), nullable=False),
        sa.Column("pos_y", sa.Float(), nullable=False),
        sa.Column("rotation", sa.Float(), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("package_metadata", sa.JSON(), nullable=True),
        sa.Column("source_provenance", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["component_id"], ["components.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_footprints_board_id", "board_footprints", ["board_id"])
    op.create_index("ix_board_footprints_component_id", "board_footprints", ["component_id"])
    op.create_index("ix_board_footprints_ref_des", "board_footprints", ["ref_des"])

    # 4. Board Pads
    op.create_table(
        "board_pads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("footprint_id", sa.String(length=36), nullable=False),
        sa.Column("pad_number", sa.String(length=32), nullable=False),
        sa.Column("pad_type", sa.String(length=32), nullable=False),
        sa.Column("pos_x", sa.Float(), nullable=False),
        sa.Column("pos_y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("drill", sa.Float(), nullable=True),
        sa.Column("shape", sa.String(length=32), nullable=False),
        sa.Column("layer", sa.String(length=64), nullable=False),
        sa.Column("net_id", sa.String(length=36), nullable=True),
        sa.Column("net_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["footprint_id"], ["board_footprints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["net_id"], ["nets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_pads_board_id", "board_pads", ["board_id"])
    op.create_index("ix_board_pads_footprint_id", "board_pads", ["footprint_id"])
    op.create_index("ix_board_pads_net_id", "board_pads", ["net_id"])

    # 5. Board Trace Segments
    op.create_table(
        "board_trace_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("start_x", sa.Float(), nullable=False),
        sa.Column("start_y", sa.Float(), nullable=False),
        sa.Column("end_x", sa.Float(), nullable=False),
        sa.Column("end_y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("layer", sa.String(length=64), nullable=False),
        sa.Column("net_id", sa.String(length=36), nullable=True),
        sa.Column("net_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["net_id"], ["nets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_trace_segments_board_id", "board_trace_segments", ["board_id"])
    op.create_index("ix_board_trace_segments_net_id", "board_trace_segments", ["net_id"])

    # 6. Board Vias
    op.create_table(
        "board_vias",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("pos_x", sa.Float(), nullable=False),
        sa.Column("pos_y", sa.Float(), nullable=False),
        sa.Column("drill", sa.Float(), nullable=False),
        sa.Column("diameter", sa.Float(), nullable=False),
        sa.Column("start_layer", sa.String(length=64), nullable=False),
        sa.Column("end_layer", sa.String(length=64), nullable=False),
        sa.Column("via_type", sa.String(length=32), nullable=False),
        sa.Column("net_id", sa.String(length=36), nullable=True),
        sa.Column("net_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["net_id"], ["nets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_vias_board_id", "board_vias", ["board_id"])
    op.create_index("ix_board_vias_net_id", "board_vias", ["net_id"])

    # 7. PCB Analyses
    op.create_table(
        "pcb_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("board_version", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ruleset_version", sa.String(length=32), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pcb_analyses_board_id", "pcb_analyses", ["board_id"])
    op.create_index("ix_pcb_analyses_circuit_id", "pcb_analyses", ["circuit_id"])
    op.create_index("ix_pcb_analyses_tenant_id", "pcb_analyses", ["tenant_id"])

    # 8. PCB Proposals
    op.create_table(
        "pcb_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("board_id", sa.String(length=36), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pcb_proposals_board_id", "pcb_proposals", ["board_id"])
    op.create_index("ix_pcb_proposals_status", "pcb_proposals", ["status"])
    op.create_index("ix_pcb_proposals_tenant_id", "pcb_proposals", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("pcb_proposals")
    op.drop_table("pcb_analyses")
    op.drop_table("board_vias")
    op.drop_table("board_trace_segments")
    op.drop_table("board_pads")
    op.drop_table("board_footprints")
    op.drop_table("board_layers")
    op.drop_table("engineering_boards")
