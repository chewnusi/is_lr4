"""API schemas separated from database models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models_db import BookingStatus, UserRole


class ErrorResponse(BaseModel):
    detail: str


class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    capacity: int = Field(..., ge=1)
    is_active: bool = True


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    capacity: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class ResourceRead(ResourceBase):
    id: str


class UserRead(BaseModel):
    id: str
    name: str
    role: UserRole


class BookingBase(BaseModel):
    resource_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    start_time: datetime
    end_time: datetime
    purpose: str = Field(..., min_length=1)


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    resource_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    purpose: str | None = Field(default=None, min_length=1)


class BookingRead(BookingBase):
    id: str
    status: BookingStatus
