"""Initial schema for users, tenants, and model configurations

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-02 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("plan", sa.String(32), default="free", nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("skill_level", sa.String(32), default="beginner", nullable=False),
        sa.Column("preferred_model", sa.String(128), nullable=True),
        sa.Column("daily_generation_count", sa.Integer(), default=0, nullable=False),
        sa.Column("daily_count_reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])

    # 2. Tenants
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(32), default="enterprise", nullable=False),
        sa.Column("max_seats", sa.Integer(), default=10, nullable=False),
        sa.Column("neo4j_namespace", sa.String(64), unique=True, nullable=True),
        sa.Column("chroma_collection_prefix", sa.String(64), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Model Configs
    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(128), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("is_vision_capable", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("cost_per_1k_input", sa.Float(), nullable=True),
        sa.Column("cost_per_1k_output", sa.Float(), nullable=True),
        sa.Column("max_context_tokens", sa.Integer(), nullable=True),
        sa.Column("supports_json_mode", sa.Boolean(), default=True, nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), default=True, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 4. Plan Model Access
    op.create_table(
        "plan_model_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("priority", sa.Integer(), default=0, nullable=False),
        sa.Column("is_user_selectable", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_default", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("plan", "task_type", "model_id", name="uq_plan_task_model"),
    )

    # 5. Plan Rate Limits
    op.create_table(
        "plan_rate_limits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan", sa.String(32), unique=True, nullable=False),
        sa.Column("daily_generations", sa.Integer(), nullable=False),
        sa.Column("daily_vision_calls", sa.Integer(), nullable=True),
        sa.Column("max_concurrent_jobs", sa.Integer(), default=1, nullable=False),
        sa.Column("bff_requests_per_minute", sa.Integer(), default=30, nullable=False),
        sa.Column("api_calls_per_day", sa.Integer(), nullable=True),
        sa.Column("max_simulation_components", sa.Integer(), default=10, nullable=False),
        sa.Column("max_projects", sa.Integer(), nullable=True),
        sa.Column("project_retention_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("plan_rate_limits")
    op.drop_table("plan_model_access")
    op.drop_table("model_configs")
    op.drop_table("tenants")
    op.drop_table("users")
