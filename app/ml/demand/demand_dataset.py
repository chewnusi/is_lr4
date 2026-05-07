"""Build demand forecasting datasets from bookings/resources."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlmodel import Session, select

from app.db import engine
from app.models_db import Booking, Resource


@dataclass
class DemandRow:
    date: str
    day_of_week: int
    hour: int
    resource_type: str
    building: str
    purpose_category: str
    duration_minutes: int
    status: str
    bookings_count: int


def build_training_rows(session: Session) -> list[DemandRow]:
    resources = {resource.id: resource for resource in session.exec(select(Resource)).all()}
    aggregates: dict[tuple, int] = defaultdict(int)
    for booking in session.exec(select(Booking)).all():
        resource = resources.get(booking.resource_id)
        if resource is None:
            continue
        duration = max(1, int((booking.end_time - booking.start_time).total_seconds() // 60))
        key = (
            booking.start_time.date().isoformat(),
            booking.start_time.weekday(),
            booking.start_time.hour,
            resource.type,
            resource.building or "unknown",
            booking.purpose_category.value if booking.purpose_category else "other",
            duration,
            booking.status.value,
        )
        aggregates[key] += 1
    rows: list[DemandRow] = []
    for key, count in sorted(aggregates.items(), key=lambda item: (item[0][0], item[0][2])):
        rows.append(DemandRow(key[0], key[1], key[2], key[3], key[4], key[5], key[6], key[7], count))
    return rows


def build_hourly_inference_rows(session: Session, target_date: date, resource_type: str, building: str | None = None) -> list[dict[str, Any]]:
    rows = build_training_rows(session)
    candidates = [r for r in rows if r.resource_type == resource_type and (building is None or r.building == building)]
    if not candidates:
        candidates = [r for r in rows if r.resource_type == resource_type]
    if not candidates:
        candidates = rows
    by_hour: dict[int, list[DemandRow]] = defaultdict(list)
    for row in candidates:
        by_hour[row.hour].append(row)
    output: list[dict[str, Any]] = []
    for hour in range(24):
        hour_rows = by_hour.get(hour) or candidates
        avg_duration = int(sum(r.duration_minutes for r in hour_rows) / len(hour_rows))
        status_mode = Counter([r.status for r in hour_rows]).most_common(1)[0][0]
        purpose_mode = Counter([r.purpose_category for r in hour_rows]).most_common(1)[0][0]
        output.append(
            {
                "day_of_week": target_date.weekday(),
                "hour": hour,
                "resource_type": resource_type,
                "building": building or (hour_rows[0].building if hour_rows else "unknown"),
                "purpose_category": purpose_mode,
                "duration_minutes": avg_duration,
                "status": status_mode,
            }
        )
    return output


def load_training_rows_from_db() -> list[DemandRow]:
    with Session(engine) as session:
        return build_training_rows(session)
