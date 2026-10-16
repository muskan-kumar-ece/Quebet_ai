"""Phase 1: Engineering Projects, Circuits, Components, Nets, Connections, Schematic Objects, and Assumptions

Revision ID: 003_phase_1_circuit_foundation
Revises: 002_add_user_role
Create Date: 2026-10-02 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_phase_1_circuit_foundation"
down_revision: Union[str, None] = "002_add_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_type", sa.String(32), default="circuit", nullable=False),
        sa.Column("status", sa.String(32), default="active", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("idx_projects_owner_id", "projects", ["owner_id"])

    # 2. Circuits
    op.create_table(
        "circuits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("validation_status", sa.String(32), default="DRAFT", nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_source", sa.String(32), default="USER", nullable=False),
        sa.Column("source_request_id", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_circuits_project_id", "circuits", ["project_id"])
    op.create_index("idx_circuits_tenant_id", "circuits", ["tenant_id"])

    # 3. Components
    op.create_table(
        "components",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ref_des", sa.String(32), nullable=False),
        sa.Column("component_type", sa.String(64), nullable=False),
        sa.Column("manufacturer", sa.String(128), nullable=True),
        sa.Column("part_number", sa.String(128), nullable=True),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("tolerance", sa.String(32), nullable=True),
        sa.Column("rating", sa.String(64), nullable=True),
        sa.Column("package", sa.String(64), nullable=True),
        sa.Column("pins", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_source", sa.String(32), default="USER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("circuit_id", "ref_des", name="uq_circuit_component_ref_des"),
    )
    op.create_index("idx_components_circuit_id", "components", ["circuit_id"])
    op.create_index("idx_components_ref_des", "components", ["ref_des"])

    # 4. Nets
    op.create_table(
        "nets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("net_type", sa.String(32), default="signal", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("circuit_id", "name", name="uq_circuit_net_name"),
    )
    op.create_index("idx_nets_circuit_id", "nets", ["circuit_id"])
    op.create_index("idx_nets_name", "nets", ["name"])

    # 5. Connections
    op.create_table(
        "connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_id", sa.String(36), sa.ForeignKey("components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pin_number", sa.String(32), nullable=False),
        sa.Column("pin_name", sa.String(64), nullable=True),
        sa.Column("net_id", sa.String(36), sa.ForeignKey("nets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_connections_circuit_id", "connections", ["circuit_id"])
    op.create_index("idx_connections_component_id", "connections", ["component_id"])
    op.create_index("idx_connections_net_id", "connections", ["net_id"])

    # 6. Schematic Objects
    op.create_table(
        "schematic_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("component_id", sa.String(36), sa.ForeignKey("components.id", ondelete="SET NULL"), nullable=True),
        sa.Column("net_id", sa.String(36), sa.ForeignKey("nets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pos_x", sa.Float(), default=0.0, nullable=False),
        sa.Column("pos_y", sa.Float(), default=0.0, nullable=False),
        sa.Column("rotation", sa.Float(), default=0.0, nullable=False),
        sa.Column("graphics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_schematic_objects_circuit_id", "schematic_objects", ["circuit_id"])

    # 7. Assumptions
    op.create_table(
        "assumptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.String(128), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), default="ai_inference", nullable=False),
        sa.Column("confidence", sa.Float(), default=0.8, nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), default=False, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_assumptions_circuit_id", "assumptions", ["circuit_id"])


def downgrade() -> None:
    op.drop_table("assumptions")
    op.drop_table("schematic_objects")
    op.drop_table("connections")
    op.drop_table("nets")
    op.drop_table("components")
    op.drop_table("circuits")
    op.drop_table("projects")
