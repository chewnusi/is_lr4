"""Generate patterned synthetic historical bookings for demand forecasting."""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, delete, select

from app.db import engine
from app.models_db import Booking, BookingPurposeCategory, BookingStatus, Resource, User, UserRole

SYNTHETIC_ID_PREFIX = "synthetic-bk-"
SYNTHETIC_USER_PREFIX = "synthetic-user-"


@dataclass
class _Pattern:
    purpose: BookingPurposeCategory
    status_weights: dict[BookingStatus, int]
    hour_candidates: list[int]
    duration_candidates: list[int]


PATTERNS_BY_RESOURCE_TYPE: dict[str, _Pattern] = {
    "meeting_room": _Pattern(BookingPurposeCategory.meeting, {BookingStatus.approved: 70, BookingStatus.pending: 20, BookingStatus.cancelled: 10}, [9, 10, 11, 12, 13, 14, 15], [30, 45, 60, 90]),
    "lab": _Pattern(BookingPurposeCategory.workshop, {BookingStatus.approved: 75, BookingStatus.pending: 15, BookingStatus.cancelled: 10}, [10, 11, 12, 13, 14, 15, 16], [60, 90, 120, 180]),
    "car": _Pattern(BookingPurposeCategory.client_meeting, {BookingStatus.approved: 65, BookingStatus.pending: 20, BookingStatus.cancelled: 15}, [7, 8, 9, 10, 11], [60, 120, 180, 240]),
    "equipment": _Pattern(BookingPurposeCategory.maintenance, {BookingStatus.approved: 55, BookingStatus.pending: 20, BookingStatus.cancelled: 25}, [13, 14, 15, 16, 17, 18], [30, 60, 90]),
}


def _pick_status(weights: dict[BookingStatus, int]) -> BookingStatus:
    statuses = list(weights.keys())
    return random.choices(statuses, weights=[weights[s] for s in statuses], k=1)[0]


def _pattern_for_resource_type(resource_type: str) -> _Pattern:
    resource_type = (resource_type or "").lower()
    if resource_type in PATTERNS_BY_RESOURCE_TYPE:
        return PATTERNS_BY_RESOURCE_TYPE[resource_type]
    if "meeting" in resource_type or "room" in resource_type:
        return PATTERNS_BY_RESOURCE_TYPE["meeting_room"]
    if "lab" in resource_type:
        return PATTERNS_BY_RESOURCE_TYPE["lab"]
    if "car" in resource_type or "vehicle" in resource_type or "van" in resource_type:
        return PATTERNS_BY_RESOURCE_TYPE["car"]
    if "equipment" in resource_type or "kit" in resource_type:
        return PATTERNS_BY_RESOURCE_TYPE["equipment"]
    return PATTERNS_BY_RESOURCE_TYPE["meeting_room"]


def clear_synthetic_bookings(session: Session) -> int:
    rows = session.exec(select(Booking.id).where(Booking.id.startswith(SYNTHETIC_ID_PREFIX))).all()
    if rows:
        session.exec(delete(Booking).where(Booking.id.startswith(SYNTHETIC_ID_PREFIX)))
        session.commit()
    return len(rows)


def _ensure_synthetic_users(session: Session, minimum_count: int = 50) -> list[str]:
    users = session.exec(select(User.id).where(User.role == UserRole.employee, User.is_active == True)).all()  # noqa: E712
    existing = list(users)
    if len(existing) >= minimum_count:
        return existing
    next_index = 1
    while len(existing) < minimum_count:
        candidate_id = f"{SYNTHETIC_USER_PREFIX}{next_index:03d}"
        next_index += 1
        if candidate_id in existing:
            continue
        session.add(User(id=candidate_id, name=f"Synthetic User {len(existing) + 1:03d}", role=UserRole.employee))
        existing.append(candidate_id)
    session.commit()
    return existing


def generate_synthetic_history(count: int = 800, months_back: int = 3, seed: int = 42, reset: bool = False) -> int:
    random.seed(seed)
    now = datetime.now(UTC).replace(tzinfo=None)
    horizon_start = now - timedelta(days=months_back * 30)
    created = 0
    with Session(engine) as session:
        resources = session.exec(select(Resource).where(Resource.is_active == True)).all()  # noqa: E712
        if not resources:
            raise RuntimeError("No active resources found. Seed resources before generating synthetic history.")
        users = _ensure_synthetic_users(session, minimum_count=50)
        if reset:
            clear_synthetic_bookings(session)
        existing_ids = session.exec(select(Booking.id).where(Booking.id.startswith(SYNTHETIC_ID_PREFIX))).all()
        next_index = 1
        for booking_id in existing_ids:
            try:
                suffix = int(booking_id.removeprefix(SYNTHETIC_ID_PREFIX))
            except ValueError:
                continue
            if suffix >= next_index:
                next_index = suffix + 1
        for _ in range(count):
            resource = random.choice(resources)
            pattern = _pattern_for_resource_type(resource.type)
            random_day = horizon_start + timedelta(days=random.randint(0, max(1, (now - horizon_start).days - 1)))
            hour = random.choice(pattern.hour_candidates)
            minute = random.choice([0, 15, 30, 45])
            start_time = random_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            duration = random.choice(pattern.duration_candidates)
            end_time = start_time + timedelta(minutes=duration)
            status = _pick_status(pattern.status_weights)
            lead_days = random.randint(0, 14)
            created_at = max(horizon_start, start_time - timedelta(days=lead_days, hours=random.randint(0, 8)))
            attendees_count = random.randint(1, max(1, resource.capacity))
            # Collision-safe even when synthetic IDs are sparse due to partial deletes.
            booking_id = f"{SYNTHETIC_ID_PREFIX}{next_index:05d}"
            next_index += 1
            booking = Booking(
                id=booking_id,
                resource_id=resource.id,
                user_id=random.choice(users),
                start_time=start_time,
                end_time=end_time,
                purpose=f"Synthetic {pattern.purpose.value.replace('_', ' ')} booking",
                purpose_category=pattern.purpose,
                attendees_count=attendees_count,
                status=status,
                created_at=created_at,
                updated_at=created_at + timedelta(hours=random.randint(1, 48)) if status != BookingStatus.pending else None,
                cancelled_at=(start_time - timedelta(hours=random.randint(1, 24))) if status == BookingStatus.cancelled else None,
                completed_at=end_time if status == BookingStatus.approved and end_time < now else None,
            )
            session.add(booking)
            created += 1
        session.commit()
    return created


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic booking history.")
    parser.add_argument("--count", type=int, default=800)
    parser.add_argument("--months-back", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    inserted = generate_synthetic_history(count=args.count, months_back=args.months_back, seed=args.seed, reset=args.reset)
    print(f"Inserted {inserted} synthetic bookings.")


if __name__ == "__main__":
    _cli()
