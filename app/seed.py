"""
One-time (manual) demo data seeding for local development and demos.

Strategy:
- All demo rows use ids starting with DEMO_ID_PREFIX.
- Each run removes existing demo rows first, then inserts fresh data.
- User-created resources/bookings (e.g. UUID ids) are never touched.

Run from project root:
    python -m app.seed
"""

from __future__ import annotations

from app import storage
from app.models import Booking, BookingCreate, Resource, ResourceCreate

# Must match seeded resource/booking ids so re-runs replace demo data only.
DEMO_ID_PREFIX = "demo-seed-"


def _is_demo_resource_id(resource_id: str) -> bool:
    return resource_id.startswith(DEMO_ID_PREFIX)


def clear_demo_data() -> tuple[int, int]:
    """Remove demo resources and any bookings tied to them or marked as demo."""
    resources = storage.load_resources()
    bookings = storage.load_bookings()

    kept_resources = [r for r in resources if not _is_demo_resource_id(str(r.get("id", "")))]
    removed_r = len(resources) - len(kept_resources)

    kept_bookings = [
        b
        for b in bookings
        if not str(b.get("id", "")).startswith(DEMO_ID_PREFIX)
        and not _is_demo_resource_id(str(b.get("resource_id", "")))
    ]
    removed_b = len(bookings) - len(kept_bookings)

    storage.save_resources(kept_resources)
    storage.save_bookings(kept_bookings)
    return removed_r, removed_b


def _resource_id(n: int) -> str:
    return f"{DEMO_ID_PREFIX}r{n:02d}"


def _booking_id(n: int) -> str:
    return f"{DEMO_ID_PREFIX}b{n:02d}"


def seed_demo_data() -> None:
    """
    Insert exactly 10 demo resources and 5 demo bookings.

    Safe to run multiple times: clears prior demo rows first.
    """
    removed_r, removed_b = clear_demo_data()
    print(
        f"Cleared previous demo data: {removed_r} resource(s), {removed_b} booking(s) removed."
    )

    resource_payloads: list[tuple[str, ResourceCreate]] = [
        (_resource_id(1), ResourceCreate(name="Executive Boardroom", type="meeting_room", location="Building A, 3rd floor", capacity=12, is_active=True)),
        (_resource_id(2), ResourceCreate(name="Huddle Pod 1", type="meeting_room", location="Building A, 2nd floor", capacity=4, is_active=True)),
        (_resource_id(3), ResourceCreate(name="Fleet Sedan 04 (Toyota Camry)", type="car", location="North parking, bay 4", capacity=5, is_active=True)),
        (_resource_id(4), ResourceCreate(name="Sprinter Van 2", type="car", location="Motor pool — Depot B", capacity=8, is_active=True)),
        (_resource_id(5), ResourceCreate(name="4K Projector Kit", type="equipment", location="AV closet, room 102", capacity=1, is_active=True)),
        (_resource_id(6), ResourceCreate(name="Portable PA System", type="equipment", location="Storage cage 12", capacity=1, is_active=True)),
        (_resource_id(7), ResourceCreate(name="Chemistry Lab A", type="lab", location="Science wing, east wing", capacity=20, is_active=True)),
        (_resource_id(8), ResourceCreate(name="Electronics Bench 3", type="lab", location="Engineering lab", capacity=4, is_active=True)),
        (_resource_id(9), ResourceCreate(name="Zoom Room West", type="meeting_room", location="Remote office pod", capacity=6, is_active=True)),
        (_resource_id(10), ResourceCreate(name="DSLR Camera Kit", type="equipment", location="Media cage", capacity=1, is_active=True)),
    ]

    resources = storage.load_resources()
    for rid, payload in resource_payloads:
        record = {"id": rid, **payload.model_dump()}
        Resource.model_validate(record)
        resources.append(record)
    storage.save_resources(resources)

    # Bookings reference seeded resource ids; times are ISO-like strings for the UI calendar.
    booking_defs: list[tuple[str, BookingCreate]] = [
        (
            _booking_id(1),
            BookingCreate(
                resource_id=_resource_id(1),
                user_name="Alice Chen",
                start_time="2026-04-02T09:00:00",
                end_time="2026-04-02T10:30:00",
                purpose="Team meeting",
            ),
        ),
        (
            _booking_id(2),
            BookingCreate(
                resource_id=_resource_id(3),
                user_name="Jordan Smith",
                start_time="2026-04-02T14:00:00",
                end_time="2026-04-02T17:00:00",
                purpose="Client call",
            ),
        ),
        (
            _booking_id(3),
            BookingCreate(
                resource_id=_resource_id(7),
                user_name="Dr. Patel",
                start_time="2026-04-03T10:00:00",
                end_time="2026-04-03T12:00:00",
                purpose="Workshop",
            ),
        ),
        (
            _booking_id(4),
            BookingCreate(
                resource_id=_resource_id(5),
                user_name="Sam Rivera",
                start_time="2026-04-03T13:00:00",
                end_time="2026-04-03T14:00:00",
                purpose="Presentation",
            ),
        ),
        (
            _booking_id(5),
            BookingCreate(
                resource_id=_resource_id(4),
                user_name="Morgan Lee",
                start_time="2026-04-04T08:00:00",
                end_time="2026-04-04T12:00:00",
                purpose="Maintenance",
            ),
        ),
    ]

    bookings = storage.load_bookings()
    demo_resource_ids = {rid for rid, _ in resource_payloads}
    for bid, payload in booking_defs:
        if payload.resource_id not in demo_resource_ids:
            raise RuntimeError("Booking references a resource id not in the demo set.")
        record = {"id": bid, **payload.model_dump(), "status": "pending"}
        Booking.model_validate(record)
        bookings.append(record)
    storage.save_bookings(bookings)

    print("Seeded 10 demo resources and 5 demo bookings.")
    print(f"Demo ids are prefixed with {DEMO_ID_PREFIX!r} — re-run this script anytime to reset demo data only.")


if __name__ == "__main__":
    seed_demo_data()
