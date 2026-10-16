"""Phase 3 Wave 2: Datasheet & Component Intelligence

Revision ID: 020_phase_3_wave_2_component_intelligence
Revises: 019_phase_3_wave_1_knowledge_intelligence
Create Date: 2026-10-06 23:29:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "020_phase_3_wave_2_component_intelligence"
down_revision: Union[str, None] = "019_phase_3_wave_1_knowledge_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("engineering_knowledge_records") as batch_op:
        batch_op.add_column(
            sa.Column("parameter_category", sa.String(64), nullable=True)
        )
        batch_op.create_index(
            "ix_engineering_knowledge_records_parameter_category",
            ["parameter_category"],
        )


def downgrade() -> None:
    with op.batch_alter_table("engineering_knowledge_records") as batch_op:
        batch_op.drop_index("ix_engineering_knowledge_records_parameter_category")
        batch_op.drop_column("parameter_category")
