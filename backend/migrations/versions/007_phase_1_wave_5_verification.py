"""Phase 1 Wave 5: Engineering Verification, Design Review & Failure Analysis

Revision ID: 007_phase_1_wave_5_verification
Revises: 006_phase_1_wave_4_design_intelligence
Create Date: 2026-10-02 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_phase_1_wave_5_verification"
down_revision: Union[str, None] = "006_phase_1_wave_4_design_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_design_reviews
    op.create_table(
        "engineering_design_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("circuit_revision", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), default="DRAFT", nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_design_reviews_circuit_id", "engineering_design_reviews", ["circuit_id"])
    op.create_index("idx_design_reviews_project_id", "engineering_design_reviews", ["project_id"])
    op.create_index("idx_design_reviews_tenant_id", "engineering_design_reviews", ["tenant_id"])
    op.create_index("idx_design_reviews_status", "engineering_design_reviews", ["status"])

    # 2. engineering_failure_modes
    op.create_table(
        "engineering_failure_modes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("trigger", sa.String(255), nullable=False),
        sa.Column("mechanism", sa.Text(), nullable=False),
        sa.Column("consequence", sa.Text(), nullable=False),
        sa.Column("likelihood", sa.String(32), default="MEDIUM", nullable=False),
        sa.Column("severity", sa.String(32), default="WARNING", nullable=False),
        sa.Column("affected_components", sa.JSON(), nullable=False),
        sa.Column("affected_nets", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("related_findings", sa.JSON(), nullable=False),
        sa.Column("related_rules", sa.JSON(), nullable=False),
        sa.Column("verification_requirement_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_failure_modes_review_id", "engineering_failure_modes", ["review_id"])
    op.create_index("idx_failure_modes_tenant_id", "engineering_failure_modes", ["tenant_id"])
    op.create_index("idx_failure_modes_category", "engineering_failure_modes", ["category"])

    # 3. engineering_verification_requirements
    op.create_table(
        "engineering_verification_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("trigger", sa.String(255), nullable=True),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("operating_condition", sa.String(64), default="NOMINAL", nullable=False),
        sa.Column("required_evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), default="NOT_STARTED", nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), default=True, nullable=False),
        sa.Column("not_applicable_reason", sa.Text(), nullable=True),
        sa.Column("affected_components", sa.JSON(), nullable=False),
        sa.Column("affected_nets", sa.JSON(), nullable=False),
        sa.Column("related_rule_id", sa.String(32), nullable=True),
        sa.Column("related_finding_id", sa.String(36), nullable=True),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_verif_reqs_review_id", "engineering_verification_requirements", ["review_id"])
    op.create_index("idx_verif_reqs_tenant_id", "engineering_verification_requirements", ["tenant_id"])
    op.create_index("idx_verif_reqs_code", "engineering_verification_requirements", ["code"])
    op.create_index("idx_verif_reqs_status", "engineering_verification_requirements", ["status"])

    # 4. engineering_evidence
    op.create_table(
        "engineering_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("verification_requirement_id", sa.String(36), sa.ForeignKey("engineering_verification_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), default="VALID", nullable=False),
        sa.Column("confidence", sa.String(32), default="HIGH", nullable=False),
        sa.Column("provided_by", sa.String(36), nullable=False),
        sa.Column("provided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("idx_evidence_req_id", "engineering_evidence", ["verification_requirement_id"])
    op.create_index("idx_evidence_review_id", "engineering_evidence", ["review_id"])
    op.create_index("idx_evidence_tenant_id", "engineering_evidence", ["tenant_id"])

    # 5. engineering_test_points
    op.create_table(
        "engineering_test_points",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("target_net", sa.String(128), nullable=True),
        sa.Column("target_component", sa.String(128), nullable=True),
        sa.Column("measurement", sa.String(255), nullable=False),
        sa.Column("expected_basis", sa.Text(), nullable=False),
        sa.Column("instrumentation", sa.String(128), nullable=False),
        sa.Column("operating_condition", sa.String(64), default="NOMINAL", nullable=False),
        sa.Column("related_requirement_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_test_points_review_id", "engineering_test_points", ["review_id"])
    op.create_index("idx_test_points_tenant_id", "engineering_test_points", ["tenant_id"])

    # 6. engineering_review_audit_events
    op.create_table(
        "engineering_review_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("previous_state", sa.String(64), nullable=True),
        sa.Column("new_state", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_review_id", "engineering_review_audit_events", ["review_id"])
    op.create_index("idx_audit_tenant_id", "engineering_review_audit_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("engineering_review_audit_events")
    op.drop_table("engineering_test_points")
    op.drop_table("engineering_evidence")
    op.drop_table("engineering_verification_requirements")
    op.drop_table("engineering_failure_modes")
    op.drop_table("engineering_design_reviews")
