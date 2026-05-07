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


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    role: UserRole = Field(default=UserRole.employee)


class Resource(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    location: str
    capacity: int
    is_active: bool = True


class Booking(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resource_id: str = Field(index=True, foreign_key="resource.id")
    user_id: str = Field(index=True, foreign_key="user.id")
    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)
    purpose: str
    status: BookingStatus = Field(default=BookingStatus.pending, index=True)
