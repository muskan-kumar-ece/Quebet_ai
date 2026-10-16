"""Phase 1 Wave 2: Engineering Proposals

Revision ID: 004_phase_1_wave_2_proposals
Revises: 003_phase_1_circuit_foundation
Create Date: 2026-10-02 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_phase_1_wave_2_proposals"
down_revision: Union[str, None] = "003_phase_1_circuit_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("source", sa.String(32), default="AI", nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), default="PROPOSED", nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_proposals_circuit_id", "engineering_proposals", ["circuit_id"])
    op.create_index("idx_proposals_tenant_id", "engineering_proposals", ["tenant_id"])
    op.create_index("idx_proposals_status", "engineering_proposals", ["status"])


def downgrade() -> None:
    op.drop_table("engineering_proposals")
