"""Phase 1 Wave 3: Circuit Analyses

Revision ID: 005_phase_1_wave_3_analysis
Revises: 004_phase_1_wave_2_proposals
Create Date: 2026-10-02 21:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_phase_1_wave_3_analysis"
down_revision: Union[str, None] = "004_phase_1_wave_2_proposals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "circuit_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("circuit_version", sa.Integer(), default=1, nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), default="COMPLETE", nullable=False),
        sa.Column("confidence", sa.String(32), default="HIGH", nullable=False),
        sa.Column("graph_summary", sa.JSON(), nullable=False),
        sa.Column("calculations", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("execution_time_ms", sa.Float(), default=0.0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_circuit_analyses_circuit_id", "circuit_analyses", ["circuit_id"])
    op.create_index("idx_circuit_analyses_tenant_id", "circuit_analyses", ["tenant_id"])
    op.create_index("idx_circuit_analyses_status", "circuit_analyses", ["status"])


def downgrade() -> None:
    op.drop_table("circuit_analyses")
