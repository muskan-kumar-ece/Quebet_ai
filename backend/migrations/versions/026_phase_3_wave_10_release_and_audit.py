"""Phase 3 Wave 10A: Engineering Audit Ledger Foundation

Revision ID: 026_phase_3_wave_10_release_and_audit
Revises: 025_phase_3_wave_8_cross_domain
Create Date: 2026-10-11 22:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "026_phase_3_wave_10_release_and_audit"
down_revision: Union[str, None] = "025_phase_3_wave_8_cross_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("entity_revision", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("prev_event_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "sequence_number", name="uq_audit_project_sequence"),
    )
    op.create_index("ix_engineering_audit_events_project_id", "engineering_audit_events", ["project_id"])
    op.create_index("ix_engineering_audit_events_tenant_id", "engineering_audit_events", ["tenant_id"])
    op.create_index("ix_engineering_audit_events_event_type", "engineering_audit_events", ["event_type"])
    op.create_index("ix_engineering_audit_events_entity_id", "engineering_audit_events", ["entity_id"])
    op.create_index("ix_engineering_audit_events_event_hash", "engineering_audit_events", ["event_hash"])


def downgrade() -> None:
    op.drop_index("ix_engineering_audit_events_event_hash", table_name="engineering_audit_events")
    op.drop_index("ix_engineering_audit_events_entity_id", table_name="engineering_audit_events")
    op.drop_index("ix_engineering_audit_events_event_type", table_name="engineering_audit_events")
    op.drop_index("ix_engineering_audit_events_tenant_id", table_name="engineering_audit_events")
    op.drop_index("ix_engineering_audit_events_project_id", table_name="engineering_audit_events")
    op.drop_table("engineering_audit_events")
