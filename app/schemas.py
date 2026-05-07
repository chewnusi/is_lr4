"""API schemas separated from database models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models_db import BookingPurposeCategory, BookingStatus, UserRole


class ErrorResponse(BaseModel):
    detail: str


class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    building: str | None = None
    floor: str | None = None
    description: str | None = None
    features: str | None = None
    capacity: int = Field(..., ge=1)
    is_active: bool = True


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    building: str | None = None
    floor: str | None = None
    description: str | None = None
    features: str | None = None
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
    purpose_category: BookingPurposeCategory | None = None
    attendees_count: int | None = Field(default=None, ge=1)


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    resource_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    purpose: str | None = Field(default=None, min_length=1)
    purpose_category: BookingPurposeCategory | None = None
    attendees_count: int | None = Field(default=None, ge=1)


class BookingRead(BookingBase):
    id: str
    status: BookingStatus
    created_at: datetime
    updated_at: datetime | None = None
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None


class DemandForecastHour(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    predicted_demand: float = Field(..., ge=0)


class DemandForecastResponse(BaseModel):
    resource_type: str
    date: str
    building: str | None = None
    forecast: list[DemandForecastHour]
    peak_hours: list[int]
    model_info: dict = Field(default_factory=dict)


class RecommendationRequest(BaseModel):
    resource_type: str = Field(..., min_length=1)
    preferred_start_time: datetime
    duration_minutes: int = Field(..., ge=15, le=480)
    attendees_count: int = Field(..., ge=1)
    purpose_category: str = Field(..., min_length=1)
    building: str | None = None
    top_n: int = Field(default=3, ge=1, le=10)


class RecommendationOption(BaseModel):
    resource_id: str
    resource_name: str
    start_time: str
    end_time: str
    building: str | None = None
    resource_type: str
    score: float
    reason: str


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendationOption]
    model_info: dict = Field(default_factory=dict)
