"""Phase 1 Wave 8: System Design Synthesis & Scenario Intelligence

Revision ID: 010_phase_1_wave_8_system_design_synthesis
Revises: 009_phase_1_wave_7_system
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010_phase_1_wave_8_system_design_synthesis"
down_revision: Union[str, None] = "009_phase_1_wave_7_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_system_design_objectives
    op.create_table(
        "engineering_system_design_objectives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective_type", sa.String(64), nullable=False),
        sa.Column("priority", sa.String(32), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("affected_subsystems", sa.JSON(), nullable=False),
        sa.Column("relevant_modes", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_sys_objectives_system_id", "engineering_system_design_objectives", ["system_id"])
    op.create_index("ix_eng_sys_objectives_tenant_id", "engineering_system_design_objectives", ["tenant_id"])

    # 2. engineering_system_design_constraints
    op.create_table(
        "engineering_system_design_constraints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("objective_id", sa.String(36), sa.ForeignKey("engineering_system_design_objectives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("constraint_type", sa.String(16), nullable=False),
        sa.Column("parameter", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(16), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=True),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_sys_constraints_objective_id", "engineering_system_design_constraints", ["objective_id"])
    op.create_index("ix_eng_sys_constraints_system_id", "engineering_system_design_constraints", ["system_id"])
    op.create_index("ix_eng_sys_constraints_tenant_id", "engineering_system_design_constraints", ["tenant_id"])

    # 3. engineering_scenarios
    op.create_table(
        "engineering_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scenario_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("system_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_scenarios_system_id", "engineering_scenarios", ["system_id"])
    op.create_index("ix_eng_scenarios_tenant_id", "engineering_scenarios", ["tenant_id"])

    # 4. engineering_scenario_conditions
    op.create_table(
        "engineering_scenario_conditions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("engineering_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("condition_type", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("parameter", sa.String(64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_scenario_conditions_scenario_id", "engineering_scenario_conditions", ["scenario_id"])
    op.create_index("ix_eng_scenario_conditions_tenant_id", "engineering_scenario_conditions", ["tenant_id"])

    # 5. engineering_scenario_snapshots
    op.create_table(
        "engineering_scenario_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("engineering_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("system_snapshot_id", sa.String(36), nullable=True),
        sa.Column("scenario_conditions", sa.JSON(), nullable=False),
        sa.Column("engine_versions", sa.JSON(), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("knowledge_snapshot_id", sa.String(36), nullable=True),
        sa.Column("inputs_digest", sa.String(64), nullable=False),
        sa.Column("execution_timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_scenario_snapshots_scenario_id", "engineering_scenario_snapshots", ["scenario_id"])
    op.create_index("ix_eng_scenario_snapshots_system_id", "engineering_scenario_snapshots", ["system_id"])
    op.create_index("ix_eng_scenario_snapshots_tenant_id", "engineering_scenario_snapshots", ["tenant_id"])

    # 6. engineering_scenario_results
    op.create_table(
        "engineering_scenario_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("engineering_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), server_default="COMPLETE", nullable=False),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("precondition_status", sa.String(32), server_default="SATISFIED", nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("requirement_results", sa.JSON(), nullable=False),
        sa.Column("power_results", sa.JSON(), nullable=False),
        sa.Column("interface_results", sa.JSON(), nullable=False),
        sa.Column("failure_results", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_scenario_results_scenario_id", "engineering_scenario_results", ["scenario_id"])
    op.create_index("ix_eng_scenario_results_execution_id", "engineering_scenario_results", ["execution_id"])
    op.create_index("ix_eng_scenario_results_system_id", "engineering_scenario_results", ["system_id"])
    op.create_index("ix_eng_scenario_results_tenant_id", "engineering_scenario_results", ["tenant_id"])

    # 7. engineering_system_candidates
    op.create_table(
        "engineering_system_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("objective_id", sa.String(36), sa.ForeignKey("engineering_system_design_objectives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("candidate_name", sa.String(255), nullable=False),
        sa.Column("generation_strategy", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="GENERATED", nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("hard_constraints_result", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("soft_constraints_result", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("constraints_evaluation", sa.JSON(), nullable=False),
        sa.Column("requirement_effects", sa.JSON(), nullable=False),
        sa.Column("verification_effects", sa.JSON(), nullable=False),
        sa.Column("failure_effects", sa.JSON(), nullable=False),
        sa.Column("power_effects", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_sys_candidates_objective_id", "engineering_system_candidates", ["objective_id"])
    op.create_index("ix_eng_sys_candidates_system_id", "engineering_system_candidates", ["system_id"])
    op.create_index("ix_eng_sys_candidates_tenant_id", "engineering_system_candidates", ["tenant_id"])

    # 8. engineering_system_proposals
    op.create_table(
        "engineering_system_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("engineering_system_candidates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", sa.String(36), sa.ForeignKey("engineering_system_design_objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="PROPOSED", nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("system_analysis_id", sa.String(36), nullable=True),
        sa.Column("scenario_ids", sa.JSON(), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("generation_strategy", sa.String(64), server_default="MANUAL", nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("engineering_effects", sa.JSON(), nullable=False),
        sa.Column("requirement_effects", sa.JSON(), nullable=False),
        sa.Column("verification_effects", sa.JSON(), nullable=False),
        sa.Column("failure_effects", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eng_sys_proposals_system_id", "engineering_system_proposals", ["system_id"])
    op.create_index("ix_eng_sys_proposals_status", "engineering_system_proposals", ["status"])
    op.create_index("ix_eng_sys_proposals_tenant_id", "engineering_system_proposals", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("engineering_system_proposals")
    op.drop_table("engineering_system_candidates")
    op.drop_table("engineering_scenario_results")
    op.drop_table("engineering_scenario_snapshots")
    op.drop_table("engineering_scenario_conditions")
    op.drop_table("engineering_scenarios")
    op.drop_table("engineering_system_design_constraints")
    op.drop_table("engineering_system_design_objectives")
