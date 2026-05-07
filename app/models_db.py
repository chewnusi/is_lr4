"""SQLModel database models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class BookingStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    cancelled = "cancelled"


class UserRole(str, Enum):
    employee = "employee"
    admin = "admin"


class BookingPurposeCategory(str, Enum):
    meeting = "meeting"
    workshop = "workshop"
    presentation = "presentation"
    training = "training"
    interview = "interview"
    client_meeting = "client_meeting"
    planning = "planning"
    support = "support"
    maintenance = "maintenance"
    inspection = "inspection"
    repair = "repair"
    event = "event"
    other = "other"


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    role: UserRole = Field(default=UserRole.employee)
    password_hash: str | None = None
    is_active: bool = True
    last_login_at: datetime | None = Field(default=None, index=True)


class Resource(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    location: str
    building: str | None = None
    floor: str | None = None
    description: str | None = None
    features: str | None = None
    capacity: int
    is_active: bool = True


class Booking(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resource_id: str = Field(index=True, foreign_key="resource.id")
    user_id: str = Field(index=True, foreign_key="user.id")
    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)
    purpose: str
    purpose_category: BookingPurposeCategory | None = Field(default=None, index=True)
    attendees_count: int | None = Field(default=None, ge=1)
    status: BookingStatus = Field(default=BookingStatus.pending, index=True)
    created_at: datetime = Field(index=True)
    updated_at: datetime | None = Field(default=None, index=True)
    cancelled_at: datetime | None = Field(default=None, index=True)
    completed_at: datetime | None = Field(default=None, index=True)


class BookingStatusHistory(SQLModel, table=True):
    id: str = Field(primary_key=True)
    booking_id: str = Field(index=True, foreign_key="booking.id")
    old_status: BookingStatus | None = None
    new_status: BookingStatus
    changed_at: datetime = Field(index=True)
    changed_by_user_id: str | None = Field(default=None, foreign_key="user.id")
