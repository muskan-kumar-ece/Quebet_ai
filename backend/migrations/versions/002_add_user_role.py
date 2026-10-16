"""Add role column to users table

Revision ID: 002_add_user_role
Revises: 001_initial_schema
Create Date: 2026-10-02 19:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_user_role"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(32), server_default="user", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "role")
