"""Phase 4D: External Audit Anchoring & Ledger Notarization

Revision ID: 028_phase_4d_external_audit_anchors
Revises: 027_phase_3_wave_10c_release_gates_and_baselines
Create Date: 2026-10-16 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "028_phase_4d_external_audit_anchors"
down_revision: Union[str, None] = "027_phase_3_wave_10c_release_gates_and_baselines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_audit_anchors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("checkpoint_sequence", sa.BigInteger(), nullable=False),
        sa.Column("from_sequence", sa.BigInteger(), nullable=False),
        sa.Column("to_sequence", sa.BigInteger(), nullable=False),
        sa.Column("chain_head_hash", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_manifest", sa.JSON(), nullable=False),
        sa.Column("checkpoint_digest", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("tsa_url", sa.String(length=255), nullable=False),
        sa.Column("tsa_policy_id", sa.String(length=128), nullable=True),
        sa.Column("tsa_serial_number", sa.String(length=128), nullable=True),
        sa.Column("tsa_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_der", sa.LargeBinary(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mirrored_to_external_store", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("external_store_uri", sa.String(length=512), nullable=True),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verification_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkpoint_digest", name="uq_anchor_checkpoint_digest"),
        sa.UniqueConstraint("project_id", "checkpoint_sequence", name="uq_anchor_project_sequence"),
        sa.UniqueConstraint("project_id", "to_sequence", name="uq_anchor_project_to_seq"),
    )
    op.create_index("ix_engineering_audit_anchors_project_id", "engineering_audit_anchors", ["project_id"])
    op.create_index("ix_engineering_audit_anchors_tenant_id", "engineering_audit_anchors", ["tenant_id"])
    op.create_index("ix_engineering_audit_anchors_status", "engineering_audit_anchors", ["status"])
    op.create_index("ix_engineering_audit_anchors_checkpoint_digest", "engineering_audit_anchors", ["checkpoint_digest"])


def downgrade() -> None:
    op.drop_index("ix_engineering_audit_anchors_checkpoint_digest", table_name="engineering_audit_anchors")
    op.drop_index("ix_engineering_audit_anchors_status", table_name="engineering_audit_anchors")
    op.drop_index("ix_engineering_audit_anchors_tenant_id", table_name="engineering_audit_anchors")
    op.drop_index("ix_engineering_audit_anchors_project_id", table_name="engineering_audit_anchors")
    op.drop_table("engineering_audit_anchors")
