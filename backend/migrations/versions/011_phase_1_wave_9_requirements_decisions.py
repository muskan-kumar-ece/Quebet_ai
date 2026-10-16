"""Phase 1 Wave 9: Engineering Requirements, Decision Intelligence & Design Review Orchestration

Revision ID: 011_phase_1_wave_9_requirements_decisions
Revises: 010_phase_1_wave_8_system_design_synthesis
Create Date: 2026-10-04 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011_phase_1_wave_9_requirements_decisions"
down_revision: Union[str, None] = "010_phase_1_wave_8_system_design_synthesis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_requirements
    op.create_table(
        "engineering_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_requirement_id", sa.String(36), sa.ForeignKey("engineering_requirements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("requirement_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), server_default="FUNCTIONAL", nullable=False),
        sa.Column("priority", sa.String(32), server_default="MEDIUM", nullable=False),
        sa.Column("source_type", sa.String(64), server_default="INTERNAL_SPEC", nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expression", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_req_project_id", "engineering_requirements", ["project_id"])
    op.create_index("ix_eng_req_system_id", "engineering_requirements", ["system_id"])
    op.create_index("ix_eng_req_parent_id", "engineering_requirements", ["parent_requirement_id"])
    op.create_index("ix_eng_req_tenant_id", "engineering_requirements", ["tenant_id"])
    op.create_index("ix_eng_req_key", "engineering_requirements", ["requirement_key"])

    # 2. engineering_requirement_baselines
    op.create_table(
        "engineering_requirement_baselines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("baseline_hash", sa.String(64), nullable=False),
        sa.Column("requirement_ids", sa.JSON(), nullable=False),
        sa.Column("requirement_revisions", sa.JSON(), nullable=False),
        sa.Column("knowledge_snapshot_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_req_base_system_id", "engineering_requirement_baselines", ["system_id"])
    op.create_index("ix_eng_req_base_tenant_id", "engineering_requirement_baselines", ["tenant_id"])
    op.create_index("ix_eng_req_base_hash", "engineering_requirement_baselines", ["baseline_hash"])

    # 3. engineering_assumptions
    op.create_table(
        "engineering_assumptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("requirement_id", sa.String(36), sa.ForeignKey("engineering_requirements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("impact", sa.String(32), server_default="REVIEW_REQUIRED", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_assump_system_id", "engineering_assumptions", ["system_id"])
    op.create_index("ix_eng_assump_tenant_id", "engineering_assumptions", ["tenant_id"])
    op.create_index("ix_eng_assump_req_id", "engineering_assumptions", ["requirement_id"])

    # 4. engineering_decision_records
    op.create_table(
        "engineering_decision_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("decision_key", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("decision_type", sa.String(64), server_default="ARCHITECTURE", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("requirement_baseline_id", sa.String(36), sa.ForeignKey("engineering_requirement_baselines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analysis_id", sa.String(36), nullable=True),
        sa.Column("selected_alternative_id", sa.String(36), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", sa.String(36), sa.ForeignKey("engineering_decision_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision_context", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_dec_system_id", "engineering_decision_records", ["system_id"])
    op.create_index("ix_eng_dec_project_id", "engineering_decision_records", ["project_id"])
    op.create_index("ix_eng_dec_tenant_id", "engineering_decision_records", ["tenant_id"])
    op.create_index("ix_eng_dec_key", "engineering_decision_records", ["decision_key"])

    # 5. engineering_decision_alternatives
    op.create_table(
        "engineering_decision_alternatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("engineering_decision_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("engineering_system_candidates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), server_default="CONSIDERED", nullable=False),
        sa.Column("elimination_reason", sa.String(64), nullable=True),
        sa.Column("engineering_effects", sa.JSON(), nullable=False),
        sa.Column("requirement_effects", sa.JSON(), nullable=False),
        sa.Column("verification_effects", sa.JSON(), nullable=False),
        sa.Column("failure_effects", sa.JSON(), nullable=False),
        sa.Column("tradeoffs", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_dec_alt_decision_id", "engineering_decision_alternatives", ["decision_id"])

    # 6. engineering_tradeoffs
    op.create_table(
        "engineering_tradeoffs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("engineering_decision_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension", sa.String(64), nullable=False),
        sa.Column("alternative_a_id", sa.String(36), nullable=False),
        sa.Column("alternative_b_id", sa.String(36), nullable=False),
        sa.Column("advantage_a", sa.Text(), nullable=False),
        sa.Column("disadvantage_a", sa.Text(), nullable=False),
        sa.Column("advantage_b", sa.Text(), nullable=False),
        sa.Column("disadvantage_b", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_tradeoff_decision_id", "engineering_tradeoffs", ["decision_id"])

    # 7. engineering_design_review_sessions
    op.create_table(
        "engineering_design_review_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("engineering_decision_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("requirement_baseline_id", sa.String(36), sa.ForeignKey("engineering_requirement_baselines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("chairperson", sa.String(36), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_rev_sess_system_id", "engineering_design_review_sessions", ["system_id"])
    op.create_index("ix_eng_rev_sess_tenant_id", "engineering_design_review_sessions", ["tenant_id"])

    # 8. engineering_review_participants
    op.create_table(
        "engineering_review_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("role", sa.String(64), server_default="ENGINEER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_rev_part_review_id", "engineering_review_participants", ["review_id"])

    # 9. engineering_review_checkpoints
    op.create_table(
        "engineering_review_checkpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("verified_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_rev_chk_review_id", "engineering_review_checkpoints", ["review_id"])

    # 10. engineering_review_findings
    op.create_table(
        "engineering_review_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", sa.String(36), nullable=True),
        sa.Column("source_analysis", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_requirement_id", sa.String(36), nullable=True),
        sa.Column("affected_subsystem_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("waiver_rationale", sa.Text(), nullable=True),
        sa.Column("waived_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_rev_find_review_id", "engineering_review_findings", ["review_id"])

    # 11. engineering_review_actions
    op.create_table(
        "engineering_review_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("priority", sa.String(32), server_default="MEDIUM", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("linked_requirement_id", sa.String(36), nullable=True),
        sa.Column("linked_finding_id", sa.String(36), nullable=True),
        sa.Column("linked_verification_requirement_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_rev_act_review_id", "engineering_review_actions", ["review_id"])

    # 12. engineering_decision_questions
    op.create_table(
        "engineering_decision_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("engineering_decision_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_id", sa.String(36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("affected_object", sa.String(128), nullable=True),
        sa.Column("affected_requirement_id", sa.String(36), nullable=True),
        sa.Column("affected_analysis_id", sa.String(36), nullable=True),
        sa.Column("blocking", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_by", sa.String(36), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_dec_q_decision_id", "engineering_decision_questions", ["decision_id"])

    # 13. engineering_unknown_dispositions
    op.create_table(
        "engineering_unknown_dispositions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("engineering_decision_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unknown_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACCEPTED", nullable=False),
        sa.Column("actor", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("affected_requirement_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_unk_disp_decision_id", "engineering_unknown_dispositions", ["decision_id"])


def downgrade() -> None:
    op.drop_table("engineering_unknown_dispositions")
    op.drop_table("engineering_decision_questions")
    op.drop_table("engineering_review_actions")
    op.drop_table("engineering_review_findings")
    op.drop_table("engineering_review_checkpoints")
    op.drop_table("engineering_review_participants")
    op.drop_table("engineering_design_review_sessions")
    op.drop_table("engineering_tradeoffs")
    op.drop_table("engineering_decision_alternatives")
    op.drop_table("engineering_decision_records")
    op.drop_table("engineering_assumptions")
    op.drop_table("engineering_requirement_baselines")
    op.drop_table("engineering_requirements")
