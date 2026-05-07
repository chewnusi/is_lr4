"""add ml feature columns and status history

Revision ID: 20260507_0002
Revises: 20260507_0001
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0002"
down_revision = "20260507_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resource", sa.Column("building", sa.String(), nullable=True))
    op.add_column("resource", sa.Column("floor", sa.String(), nullable=True))
    op.add_column("resource", sa.Column("description", sa.String(), nullable=True))
    op.add_column("resource", sa.Column("features", sa.String(), nullable=True))

    op.add_column("booking", sa.Column("purpose_category", sa.String(), nullable=True))
    op.add_column("booking", sa.Column("attendees_count", sa.Integer(), nullable=True))
    op.add_column("booking", sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.add_column("booking", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("booking", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("booking", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_booking_purpose_category", "booking", ["purpose_category"])
    op.create_index("ix_booking_created_at", "booking", ["created_at"])
    op.create_index("ix_booking_updated_at", "booking", ["updated_at"])
    op.create_index("ix_booking_cancelled_at", "booking", ["cancelled_at"])
    op.create_index("ix_booking_completed_at", "booking", ["completed_at"])

    op.create_table(
        "bookingstatushistory",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("booking_id", sa.String(), sa.ForeignKey("booking.id"), nullable=False),
        sa.Column("old_status", sa.String(), nullable=True),
        sa.Column("new_status", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("changed_by_user_id", sa.String(), sa.ForeignKey("user.id"), nullable=True),
    )
    op.create_index("ix_bookingstatushistory_booking_id", "bookingstatushistory", ["booking_id"])
    op.create_index("ix_bookingstatushistory_changed_at", "bookingstatushistory", ["changed_at"])


def downgrade() -> None:
    op.drop_index("ix_bookingstatushistory_changed_at", table_name="bookingstatushistory")
    op.drop_index("ix_bookingstatushistory_booking_id", table_name="bookingstatushistory")
    op.drop_table("bookingstatushistory")

    op.drop_index("ix_booking_completed_at", table_name="booking")
    op.drop_index("ix_booking_cancelled_at", table_name="booking")
    op.drop_index("ix_booking_updated_at", table_name="booking")
    op.drop_index("ix_booking_created_at", table_name="booking")
    op.drop_index("ix_booking_purpose_category", table_name="booking")
    op.drop_column("booking", "completed_at")
    op.drop_column("booking", "cancelled_at")
    op.drop_column("booking", "updated_at")
    op.drop_column("booking", "created_at")
    op.drop_column("booking", "attendees_count")
    op.drop_column("booking", "purpose_category")

    op.drop_column("resource", "features")
    op.drop_column("resource", "description")
    op.drop_column("resource", "floor")
    op.drop_column("resource", "building")
