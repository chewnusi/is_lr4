"""Pydantic models for API request/response bodies."""

from typing import Literal

from pydantic import BaseModel, Field

BookingStatus = Literal["pending", "approved", "cancelled"]

BOOKING_STATUS_VALUES: frozenset[str] = frozenset({"pending", "approved", "cancelled"})


class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    capacity: int = Field(..., ge=1)
    is_active: bool = True


class ResourceCreate(ResourceBase):
    """Payload for creating a resource (id is assigned by the server)."""

    pass


class ResourceUpdate(BaseModel):
    """Payload for updating a resource; omitted fields keep existing values."""

    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    capacity: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class Resource(ResourceBase):
    id: str


class BookingCore(BaseModel):
    """Shared booking fields (no status — status is set by the server on create)."""

    resource_id: str = Field(..., min_length=1)
    user_name: str = Field(..., min_length=1)
    start_time: str = Field(..., min_length=1)
    end_time: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)


class BookingCreate(BookingCore):
    """Create payload; status is always started as pending."""

    pass


class BookingUpdate(BaseModel):
    """Payload for updating a booking; omitted fields keep existing values."""

    resource_id: str | None = Field(default=None, min_length=1)
    user_name: str | None = Field(default=None, min_length=1)
    start_time: str | None = Field(default=None, min_length=1)
    end_time: str | None = Field(default=None, min_length=1)
    purpose: str | None = Field(default=None, min_length=1)


class Booking(BookingCore):
    id: str
    status: BookingStatus = Field(default="pending", description="pending | approved | cancelled")
