"""init tables

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
    )
    op.create_table(
        "resource",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.create_table(
        "booking",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("resource_id", sa.String(), sa.ForeignKey("resource.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
    )
    op.create_index("ix_booking_resource_id", "booking", ["resource_id"])
    op.create_index("ix_booking_user_id", "booking", ["user_id"])
    op.create_index("ix_booking_start_time", "booking", ["start_time"])
    op.create_index("ix_booking_end_time", "booking", ["end_time"])
    op.create_index("ix_booking_status", "booking", ["status"])


def downgrade() -> None:
    op.drop_index("ix_booking_status", table_name="booking")
    op.drop_index("ix_booking_end_time", table_name="booking")
    op.drop_index("ix_booking_start_time", table_name="booking")
    op.drop_index("ix_booking_user_id", table_name="booking")
    op.drop_index("ix_booking_resource_id", table_name="booking")
    op.drop_table("booking")
    op.drop_table("resource")
    op.drop_table("user")
