"""Phase 3 Wave 8: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification

Revision ID: 025_phase_3_wave_8_cross_domain
Revises: 024_phase_3_wave_7_dfm
Create Date: 2026-10-08 23:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "025_phase_3_wave_8_cross_domain"
down_revision: Union[str, None] = "024_phase_3_wave_7_dfm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cross_domain_validation_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=True),
        sa.Column("board_id", sa.String(length=36), nullable=True),
        sa.Column("bom_id", sa.String(length=36), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("domain_snapshots", sa.JSON(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("staleness_reasons", sa.JSON(), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["board_id"], ["engineering_boards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bom_id"], ["engineering_boms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cross_domain_validation_records_tenant_id", "cross_domain_validation_records", ["tenant_id"])
    op.create_index("ix_cross_domain_validation_records_project_id", "cross_domain_validation_records", ["project_id"])
    op.create_index("ix_cross_domain_validation_records_circuit_id", "cross_domain_validation_records", ["circuit_id"])
    op.create_index("ix_cross_domain_validation_records_board_id", "cross_domain_validation_records", ["board_id"])
    op.create_index("ix_cross_domain_validation_records_bom_id", "cross_domain_validation_records", ["bom_id"])
    op.create_index("ix_cross_domain_validation_records_snapshot_digest", "cross_domain_validation_records", ["snapshot_digest"])


def downgrade() -> None:
    op.drop_index("ix_cross_domain_validation_records_snapshot_digest", table_name="cross_domain_validation_records")
    op.drop_index("ix_cross_domain_validation_records_bom_id", table_name="cross_domain_validation_records")
    op.drop_index("ix_cross_domain_validation_records_board_id", table_name="cross_domain_validation_records")
    op.drop_index("ix_cross_domain_validation_records_circuit_id", table_name="cross_domain_validation_records")
    op.drop_index("ix_cross_domain_validation_records_project_id", table_name="cross_domain_validation_records")
    op.drop_index("ix_cross_domain_validation_records_tenant_id", table_name="cross_domain_validation_records")
    op.drop_table("cross_domain_validation_records")
