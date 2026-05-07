"""Build cancellation-risk datasets from booking history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.db import engine
from app.models_db import Booking, Resource, User


@dataclass
class CancellationRiskRow:
    user_id: str
    user_role: str
    user_booking_count: int
    user_cancel_rate: float
    resource_type: str
    building: str
    day_of_week: int
    hour: int
    duration_minutes: int
    lead_time_hours: int
    attendees_count: int
    capacity_utilization: float
    purpose_category: str
    will_cancel: int


def _duration_minutes(start_time: datetime, end_time: datetime) -> int:
    return max(1, int((end_time - start_time).total_seconds() // 60))


def build_training_rows(session: Session) -> list[CancellationRiskRow]:
    resources = {resource.id: resource for resource in session.exec(select(Resource)).all()}
    users = {user.id: user for user in session.exec(select(User)).all()}
    bookings = session.exec(select(Booking)).all()
    bookings_sorted = sorted(bookings, key=lambda b: (b.created_at, b.start_time, b.id))

    user_total: dict[str, int] = {}
    user_cancelled: dict[str, int] = {}
    rows: list[CancellationRiskRow] = []
    for booking in bookings_sorted:
        resource = resources.get(booking.resource_id)
        user = users.get(booking.user_id)
        if resource is None or user is None:
            continue
        past_total = user_total.get(booking.user_id, 0)
        past_cancelled = user_cancelled.get(booking.user_id, 0)
        user_cancel_rate = (past_cancelled / past_total) if past_total else 0.0
        duration_minutes = _duration_minutes(booking.start_time, booking.end_time)
        lead_hours = max(0, int((booking.start_time - booking.created_at).total_seconds() // 3600))
        attendees = booking.attendees_count or 1
        capacity_utilization = min(2.0, attendees / max(1, resource.capacity))

        rows.append(
            CancellationRiskRow(
                user_id=booking.user_id,
                user_role=user.role.value,
                user_booking_count=past_total,
                user_cancel_rate=user_cancel_rate,
                resource_type=resource.type,
                building=resource.building or "unknown",
                day_of_week=booking.start_time.weekday(),
                hour=booking.start_time.hour,
                duration_minutes=duration_minutes,
                lead_time_hours=lead_hours,
                attendees_count=attendees,
                capacity_utilization=capacity_utilization,
                purpose_category=booking.purpose_category.value if booking.purpose_category else "other",
                will_cancel=1 if booking.status.value == "cancelled" else 0,
            )
        )
        user_total[booking.user_id] = past_total + 1
        user_cancelled[booking.user_id] = past_cancelled + (1 if booking.status.value == "cancelled" else 0)
    return rows


def feature_dict(row: CancellationRiskRow) -> dict:
    return {
        "user_id": row.user_id,
        "user_role": row.user_role,
        "user_booking_count": row.user_booking_count,
        "user_cancel_rate": row.user_cancel_rate,
        "resource_type": row.resource_type,
        "building": row.building,
        "day_of_week": row.day_of_week,
        "hour": row.hour,
        "duration_minutes": row.duration_minutes,
        "lead_time_hours": row.lead_time_hours,
        "attendees_count": row.attendees_count,
        "capacity_utilization": row.capacity_utilization,
        "purpose_category": row.purpose_category,
    }


def load_training_rows_from_db() -> list[CancellationRiskRow]:
    with Session(engine) as session:
        return build_training_rows(session)

