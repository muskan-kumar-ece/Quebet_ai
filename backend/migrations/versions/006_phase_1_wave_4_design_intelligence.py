"""Phase 1 Wave 4: Engineering Design Intelligence & Proposals

Revision ID: 006_phase_1_wave_4_design_intelligence
Revises: 005_phase_1_wave_3_analysis
Create Date: 2026-10-02 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006_phase_1_wave_4_design_intelligence"
down_revision: Union[str, None] = "005_phase_1_wave_3_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create engineering_design_objectives table
    op.create_table(
        "engineering_design_objectives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("objective_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("affected_components", sa.JSON(), nullable=False),
        sa.Column("affected_nets", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(32), default="USER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_design_objectives_circuit_id", "engineering_design_objectives", ["circuit_id"])
    op.create_index("idx_design_objectives_tenant_id", "engineering_design_objectives", ["tenant_id"])
    op.create_index("idx_design_objectives_type", "engineering_design_objectives", ["objective_type"])

    # 2. Add Wave 4 fields to engineering_proposals table with batch_alter_table for SQLite compatibility
    with op.batch_alter_table("engineering_proposals") as batch_op:
        batch_op.add_column(sa.Column("base_revision", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("analysis_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("objective_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("findings_resolved", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("findings_introduced", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("constraints_evaluated", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("engineering_effects", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("unknowns", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("confidence", sa.String(32), nullable=False, server_default="HIGH"))


def downgrade() -> None:
    with op.batch_alter_table("engineering_proposals") as batch_op:
        batch_op.drop_column("confidence")
        batch_op.drop_column("unknowns")
        batch_op.drop_column("engineering_effects")
        batch_op.drop_column("constraints_evaluated")
        batch_op.drop_column("findings_introduced")
        batch_op.drop_column("findings_resolved")
        batch_op.drop_column("objective_id")
        batch_op.drop_column("analysis_id")
        batch_op.drop_column("base_revision")

    op.drop_table("engineering_design_objectives")
