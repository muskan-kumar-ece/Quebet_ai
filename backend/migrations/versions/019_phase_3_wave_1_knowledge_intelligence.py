"""Phase 3 Wave 1: Engineering Knowledge & Source Intelligence

Revision ID: 019_phase_3_wave_1_knowledge_intelligence
Revises: 018_phase_2_wave_6_workflow_orchestration
Create Date: 2026-10-06 22:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "019_phase_3_wave_1_knowledge_intelligence"
down_revision: Union[str, None] = "018_phase_2_wave_6_workflow_orchestration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("engineering_knowledge_records") as batch_op:
        batch_op.add_column(
            sa.Column("classification", sa.String(64), server_default="AUTHORITATIVE_SOURCE", nullable=False)
        )
        batch_op.add_column(
            sa.Column("raw_value", sa.String(255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("normalized_value", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("source_location", sa.JSON(), server_default="{}", nullable=False)
        )
        batch_op.add_column(
            sa.Column("is_conflicting", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("conflict_details", sa.JSON(), server_default="{}", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("engineering_knowledge_records") as batch_op:
        batch_op.drop_column("conflict_details")
        batch_op.drop_column("is_conflicting")
        batch_op.drop_column("source_location")
        batch_op.drop_column("normalized_value")
        batch_op.drop_column("raw_value")
        batch_op.drop_column("classification")
