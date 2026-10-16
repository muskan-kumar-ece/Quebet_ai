"""Phase 1 Wave 7: System-Level Engineering Intelligence & Subsystem Architecture

Revision ID: 009_phase_1_wave_7_system
Revises: 008_phase_1_wave_6_provenance
Create Date: 2026-10-03 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009_phase_1_wave_7_system"
down_revision: Union[str, None] = "008_phase_1_wave_6_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_systems
    op.create_table(
        "engineering_systems",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_systems_project_id", "engineering_systems", ["project_id"])
    op.create_index("ix_engineering_systems_tenant_id", "engineering_systems", ["tenant_id"])

    # 2. engineering_subsystems
    op.create_table(
        "engineering_subsystems",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subsystem_type", sa.String(64), server_default="OTHER", nullable=False),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_subsystems_system_id", "engineering_subsystems", ["system_id"])
    op.create_index("ix_engineering_subsystems_parent_subsystem_id", "engineering_subsystems", ["parent_subsystem_id"])
    op.create_index("ix_engineering_subsystems_circuit_id", "engineering_subsystems", ["circuit_id"])
    op.create_index("ix_engineering_subsystems_tenant_id", "engineering_subsystems", ["tenant_id"])

    # 3. engineering_system_interfaces
    op.create_table(
        "engineering_system_interfaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("source_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("interface_type", sa.String(64), server_default="OTHER", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("contract", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_system_interfaces_system_id", "engineering_system_interfaces", ["system_id"])
    op.create_index("ix_engineering_system_interfaces_tenant_id", "engineering_system_interfaces", ["tenant_id"])
    op.create_index("ix_engineering_system_interfaces_source_id", "engineering_system_interfaces", ["source_subsystem_id"])
    op.create_index("ix_engineering_system_interfaces_dest_id", "engineering_system_interfaces", ["destination_subsystem_id"])

    # 4. engineering_power_domains
    op.create_table(
        "engineering_power_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("nominal_voltage", sa.Float(), nullable=False),
        sa.Column("min_voltage", sa.Float(), nullable=True),
        sa.Column("max_voltage", sa.Float(), nullable=True),
        sa.Column("source_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regulator_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="SET NULL"), nullable=True),
        sa.Column("current_capacity_a", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_power_domains_system_id", "engineering_power_domains", ["system_id"])
    op.create_index("ix_engineering_power_domains_tenant_id", "engineering_power_domains", ["tenant_id"])
    op.create_index("ix_engineering_power_domains_source_id", "engineering_power_domains", ["source_subsystem_id"])

    # 5. engineering_system_dependencies
    op.create_table(
        "engineering_system_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("source_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_subsystem_id", sa.String(36), sa.ForeignKey("engineering_subsystems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dependency_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_system_dependencies_system_id", "engineering_system_dependencies", ["system_id"])
    op.create_index("ix_engineering_system_dependencies_tenant_id", "engineering_system_dependencies", ["tenant_id"])
    op.create_index("ix_engineering_system_dependencies_source_id", "engineering_system_dependencies", ["source_subsystem_id"])
    op.create_index("ix_engineering_system_dependencies_target_id", "engineering_system_dependencies", ["target_subsystem_id"])

    # 6. engineering_operating_modes
    op.create_table(
        "engineering_operating_modes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active_subsystem_ids", sa.JSON(), nullable=False),
        sa.Column("inactive_subsystem_ids", sa.JSON(), nullable=False),
        sa.Column("expected_power_domain_ids", sa.JSON(), nullable=False),
        sa.Column("relevant_interface_ids", sa.JSON(), nullable=False),
        sa.Column("operating_conditions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_operating_modes_system_id", "engineering_operating_modes", ["system_id"])
    op.create_index("ix_engineering_operating_modes_tenant_id", "engineering_operating_modes", ["tenant_id"])

    # 7. engineering_mode_transitions
    op.create_table(
        "engineering_mode_transitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("source_mode_id", sa.String(36), sa.ForeignKey("engineering_operating_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_mode_id", sa.String(36), sa.ForeignKey("engineering_operating_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(255), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("required_subsystems", sa.JSON(), nullable=False),
        sa.Column("forbidden_conditions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_mode_transitions_system_id", "engineering_mode_transitions", ["system_id"])
    op.create_index("ix_engineering_mode_transitions_tenant_id", "engineering_mode_transitions", ["tenant_id"])

    # 8. engineering_system_requirements
    op.create_table(
        "engineering_system_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirement_type", sa.String(64), server_default="FUNCTIONAL", nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), server_default="UNKNOWN", nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_system_requirements_system_id", "engineering_system_requirements", ["system_id"])
    op.create_index("ix_engineering_system_requirements_tenant_id", "engineering_system_requirements", ["tenant_id"])

    # 9. engineering_system_analyses
    op.create_table(
        "engineering_system_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("subsystem_revisions", sa.JSON(), nullable=False),
        sa.Column("circuit_revisions", sa.JSON(), nullable=False),
        sa.Column("engine_versions", sa.JSON(), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("knowledge_snapshot_id", sa.String(36), nullable=True),
        sa.Column("inputs_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="ANALYSIS_COMPLETE", nullable=False),
        sa.Column("is_stale", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_system_analyses_system_id", "engineering_system_analyses", ["system_id"])
    op.create_index("ix_engineering_system_analyses_tenant_id", "engineering_system_analyses", ["tenant_id"])

    # 10. engineering_system_findings
    op.create_table(
        "engineering_system_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36), sa.ForeignKey("engineering_system_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_subsystems", sa.JSON(), nullable=False),
        sa.Column("affected_interfaces", sa.JSON(), nullable=False),
        sa.Column("affected_power_domains", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("calculation", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_system_findings_analysis_id", "engineering_system_findings", ["analysis_id"])
    op.create_index("ix_engineering_system_findings_system_id", "engineering_system_findings", ["system_id"])
    op.create_index("ix_engineering_system_findings_tenant_id", "engineering_system_findings", ["tenant_id"])

    # 11. engineering_system_snapshots
    op.create_table(
        "engineering_system_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("system_id", sa.String(36), sa.ForeignKey("engineering_systems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("system_revision", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_system_snapshots_system_id", "engineering_system_snapshots", ["system_id"])
    op.create_index("ix_engineering_system_snapshots_tenant_id", "engineering_system_snapshots", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("engineering_system_snapshots")
    op.drop_table("engineering_system_findings")
    op.drop_table("engineering_system_analyses")
    op.drop_table("engineering_system_requirements")
    op.drop_table("engineering_mode_transitions")
    op.drop_table("engineering_operating_modes")
    op.drop_table("engineering_system_dependencies")
    op.drop_table("engineering_power_domains")
    op.drop_table("engineering_system_interfaces")
    op.drop_table("engineering_subsystems")
    op.drop_table("engineering_systems")
