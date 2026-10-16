"""Phase 3 Wave 10C: Deterministic Release Gate Engine and Frozen Release Baselines

Revision ID: 027_phase_3_wave_10c_release_gates_and_baselines
Revises: 026_phase_3_wave_10_release_and_audit
Create Date: 2026-10-13 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "027_phase_3_wave_10c_release_gates_and_baselines"
down_revision: Union[str, None] = "026_phase_3_wave_10_release_and_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_release_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("evaluator_version", sa.String(length=32), nullable=False),
        sa.Column("project_revision", sa.Integer(), nullable=False),
        sa.Column("overall_readiness", sa.String(length=32), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("gate_results", sa.JSON(), nullable=False),
        sa.Column("blocking_findings", sa.JSON(), nullable=False),
        sa.Column("missing_evidence", sa.JSON(), nullable=False),
        sa.Column("stale_evidence", sa.JSON(), nullable=False),
        sa.Column("audit_chain_verified", sa.Boolean(), nullable=False),
        sa.Column("audit_chain_head_hash", sa.String(length=64), nullable=True),
        sa.Column("audit_chain_sequence", sa.BigInteger(), nullable=True),
        sa.Column("audit_chain_trusted_anchor_checked", sa.Boolean(), nullable=False),
        sa.Column("evaluated_by_id", sa.String(length=36), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_release_evaluations_project_id", "engineering_release_evaluations", ["project_id"])
    op.create_index("ix_engineering_release_evaluations_tenant_id", "engineering_release_evaluations", ["tenant_id"])
    op.create_index("ix_engineering_release_evaluations_overall_readiness", "engineering_release_evaluations", ["overall_readiness"])

    op.create_table(
        "engineering_release_baselines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("release_tag", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("evaluation_id", sa.String(length=36), nullable=False),
        sa.Column("project_revision", sa.Integer(), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=True),
        sa.Column("circuit_version", sa.Integer(), nullable=True),
        sa.Column("circuit_digest", sa.String(length=64), nullable=True),
        sa.Column("board_id", sa.String(length=36), nullable=True),
        sa.Column("board_version", sa.Integer(), nullable=True),
        sa.Column("board_digest", sa.String(length=64), nullable=True),
        sa.Column("bom_id", sa.String(length=36), nullable=True),
        sa.Column("bom_version", sa.Integer(), nullable=True),
        sa.Column("bom_digest", sa.String(length=64), nullable=True),
        sa.Column("audit_chain_head_hash", sa.String(length=64), nullable=False),
        sa.Column("audit_chain_sequence", sa.BigInteger(), nullable=False),
        sa.Column("audit_chain_trusted_anchor_checked", sa.Boolean(), nullable=False),
        sa.Column("evaluation_snapshot", sa.JSON(), nullable=False),
        sa.Column("canonical_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("authorized_by_id", sa.String(length=36), nullable=False),
        sa.Column("authorized_by_role", sa.String(length=64), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("release_rationale", sa.Text(), nullable=False),
        sa.Column("exceptions_approved", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["engineering_release_evaluations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "release_tag", name="uq_release_project_tag"),
    )
    op.create_index("ix_engineering_release_baselines_release_tag", "engineering_release_baselines", ["release_tag"])
    op.create_index("ix_engineering_release_baselines_project_id", "engineering_release_baselines", ["project_id"])
    op.create_index("ix_engineering_release_baselines_tenant_id", "engineering_release_baselines", ["tenant_id"])
    op.create_index("ix_engineering_release_baselines_evaluation_id", "engineering_release_baselines", ["evaluation_id"])
    op.create_index("ix_engineering_release_baselines_canonical_snapshot_digest", "engineering_release_baselines", ["canonical_snapshot_digest"])


def downgrade() -> None:
    op.drop_index("ix_engineering_release_baselines_canonical_snapshot_digest", table_name="engineering_release_baselines")
    op.drop_index("ix_engineering_release_baselines_evaluation_id", table_name="engineering_release_baselines")
    op.drop_index("ix_engineering_release_baselines_tenant_id", table_name="engineering_release_baselines")
    op.drop_index("ix_engineering_release_baselines_project_id", table_name="engineering_release_baselines")
    op.drop_index("ix_engineering_release_baselines_release_tag", table_name="engineering_release_baselines")
    op.drop_table("engineering_release_baselines")

    op.drop_index("ix_engineering_release_evaluations_overall_readiness", table_name="engineering_release_evaluations")
    op.drop_index("ix_engineering_release_evaluations_tenant_id", table_name="engineering_release_evaluations")
    op.drop_index("ix_engineering_release_evaluations_project_id", table_name="engineering_release_evaluations")
    op.drop_table("engineering_release_evaluations")
