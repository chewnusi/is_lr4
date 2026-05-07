"""add auth fields to user

Revision ID: 20260507_0003
Revises: 20260507_0002
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0003"
down_revision = "20260507_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("password_hash", sa.String(), nullable=True))
    op.add_column("user", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("user", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.create_index("ix_user_last_login_at", "user", ["last_login_at"])


def downgrade() -> None:
    op.drop_index("ix_user_last_login_at", table_name="user")
    op.drop_column("user", "last_login_at")
    op.drop_column("user", "is_active")
    op.drop_column("user", "password_hash")

