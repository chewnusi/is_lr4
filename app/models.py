"""Pydantic models for API request/response bodies."""

from pydantic import BaseModel, Field


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


class BookingBase(BaseModel):
    resource_id: str = Field(..., min_length=1)
    user_name: str = Field(..., min_length=1)
    start_time: str = Field(..., min_length=1)
    end_time: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)


class BookingCreate(BookingBase):
    """Payload for creating a booking (id is assigned by the server)."""

    pass


class BookingUpdate(BaseModel):
    """Payload for updating a booking; omitted fields keep existing values."""

    resource_id: str | None = Field(default=None, min_length=1)
    user_name: str | None = Field(default=None, min_length=1)
    start_time: str | None = Field(default=None, min_length=1)
    end_time: str | None = Field(default=None, min_length=1)
    purpose: str | None = Field(default=None, min_length=1)


class Booking(BookingBase):
    id: str
