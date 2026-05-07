"""Feature construction for booking recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models_db import Booking, Resource


@dataclass
class RecommendationRequest:
    resource_type: str
    preferred_start_time: datetime
    duration_minutes: int
    attendees_count: int
    purpose_category: str
    building: str | None = None


@dataclass
class CandidateOption:
    resource: Resource
    start_time: datetime
    end_time: datetime
    is_available: bool
    current_demand_at_hour: int
    historical_popularity: float


def time_difference_minutes(preferred_start: datetime, candidate_start: datetime) -> int:
    return abs(int((candidate_start - preferred_start).total_seconds() // 60))


def capacity_gap(attendees_count: int, resource_capacity: int) -> int:
    return resource_capacity - attendees_count


def is_peak_hour(hour: int) -> bool:
    return hour in {10, 11, 12, 13, 14, 17}


def candidate_to_features(request: RecommendationRequest, candidate: CandidateOption) -> dict:
    return {
        "resource_id": candidate.resource.id,
        "resource_type": candidate.resource.type,
        "building": candidate.resource.building or "unknown",
        "resource_capacity": candidate.resource.capacity,
        "features": candidate.resource.features or "",
        "candidate_start_hour": candidate.start_time.hour,
        "candidate_weekday": candidate.start_time.weekday(),
        "duration_minutes": request.duration_minutes,
        "attendees_count": request.attendees_count,
        "purpose_category": request.purpose_category,
        "current_demand_at_hour": candidate.current_demand_at_hour,
        "historical_popularity": candidate.historical_popularity,
        "capacity_gap": capacity_gap(request.attendees_count, candidate.resource.capacity),
        "time_difference_minutes": time_difference_minutes(request.preferred_start_time, candidate.start_time),
        "is_available": 1 if candidate.is_available else 0,
        "is_peak_hour": 1 if is_peak_hour(candidate.start_time.hour) else 0,
        "building_match": 1 if request.building and candidate.resource.building == request.building else 0,
        "type_match": 1 if candidate.resource.type == request.resource_type else 0,
    }


def generate_candidate_offsets() -> list[timedelta]:
    return [
        timedelta(minutes=0),
        timedelta(minutes=30),
        timedelta(minutes=-30),
        timedelta(minutes=60),
        timedelta(minutes=-60),
        timedelta(days=1),
    ]


def check_availability(existing_bookings: list[Booking], resource_id: str, start_time: datetime, end_time: datetime) -> bool:
    for booking in existing_bookings:
        if booking.resource_id != resource_id:
            continue
        if booking.status.value == "cancelled":
            continue
        if booking.start_time < end_time and booking.end_time > start_time:
            return False
    return True
