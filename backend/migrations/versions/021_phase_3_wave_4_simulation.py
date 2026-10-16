"""Phase 3 Wave 4: SPICE & Simulation Integration

Revision ID: 021_phase_3_wave_4_simulation
Revises: 020_phase_3_wave_2_component_intelligence
Create Date: 2026-10-07 22:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "021_phase_3_wave_4_simulation"
down_revision: Union[str, None] = "020_phase_3_wave_2_component_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("simulation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("operating_mode", sa.String(length=64), nullable=True),
        sa.Column("simulator", sa.String(length=64), nullable=False),
        sa.Column("simulator_version", sa.String(length=64), nullable=True),
        sa.Column("execution_mode", sa.String(length=32), nullable=False),
        sa.Column("netlist_digest", sa.String(length=64), nullable=True),
        sa.Column("model_digest", sa.String(length=64), nullable=True),
        sa.Column("netlist_content", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulation_jobs_tenant_id", "simulation_jobs", ["tenant_id"])
    op.create_index("ix_simulation_jobs_project_id", "simulation_jobs", ["project_id"])
    op.create_index("ix_simulation_jobs_circuit_id", "simulation_jobs", ["circuit_id"])
    op.create_index("ix_simulation_jobs_simulation_type", "simulation_jobs", ["simulation_type"])
    op.create_index("ix_simulation_jobs_status", "simulation_jobs", ["status"])

    op.create_table(
        "simulation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("simulation_job_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_id", sa.String(length=36), nullable=False),
        sa.Column("circuit_version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("convergence_status", sa.String(length=32), nullable=False),
        sa.Column("node_voltages", sa.JSON(), nullable=False),
        sa.Column("branch_currents", sa.JSON(), nullable=False),
        sa.Column("waveforms", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("discrepancies", sa.JSON(), nullable=False),
        sa.Column("constraint_evaluations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["circuit_id"], ["circuits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["simulation_job_id"], ["simulation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulation_results_simulation_job_id", "simulation_results", ["simulation_job_id"], unique=True)
    op.create_index("ix_simulation_results_circuit_id", "simulation_results", ["circuit_id"])
    op.create_index("ix_simulation_results_tenant_id", "simulation_results", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("simulation_results")
    op.drop_table("simulation_jobs")
