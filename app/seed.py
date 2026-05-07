"""SQLite demo data seeding."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Session, delete, func, select

from app.db import engine
from app.models_db import Booking, BookingStatus, Resource

# Must match seeded resource/booking ids so re-runs replace demo data only.
DEMO_ID_PREFIX = "demo-seed-"
SEED_RESOURCES_FILE = Path(__file__).resolve().parent / "data" / "seed_resources.json"
TARGET_DEMO_RESOURCE_COUNT = 150


def _is_demo_resource_id(resource_id: str) -> bool:
    return resource_id.startswith(DEMO_ID_PREFIX)


def clear_demo_data(session: Session) -> None:
    session.exec(delete(Booking).where(Booking.id.startswith(DEMO_ID_PREFIX)))
    session.exec(delete(Resource).where(Resource.id.startswith(DEMO_ID_PREFIX)))
    session.commit()


def _resource_id(n: int) -> str:
    return f"{DEMO_ID_PREFIX}r{n:02d}"


def _booking_id(n: int) -> str:
    return f"{DEMO_ID_PREFIX}b{n:02d}"


def _load_seed_resources() -> list[dict]:
    with SEED_RESOURCES_FILE.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("seed_resources.json must contain a JSON array")
    return data


def _expanded_seed_resources(resource_defs: list[dict], target_count: int = TARGET_DEMO_RESOURCE_COUNT) -> list[dict]:
    """Expand base seed definitions up to target_count with deterministic near-duplicates."""
    if len(resource_defs) >= target_count:
        return resource_defs
    if not resource_defs:
        raise ValueError("seed_resources.json must contain at least one resource definition")

    expanded = list(resource_defs)
    clone_index = 1
    while len(expanded) < target_count:
        template = resource_defs[(len(expanded) - len(resource_defs)) % len(resource_defs)]
        clone = dict(template)
        clone["name"] = f"{template.get('name', 'Resource')} Clone {clone_index:03d}"
        base_location = template.get("location") or "Generated location"
        clone["location"] = f"{base_location} / clone {clone_index:03d}"
        description = template.get("description") or "Auto-generated similar resource"
        clone["description"] = f"{description} (auto-generated clone)"
        expanded.append(clone)
        clone_index += 1
    return expanded


def seed_demo_data(sql_engine=engine) -> None:
    with Session(sql_engine) as session:
        clear_demo_data(session)
        resource_defs = _expanded_seed_resources(_load_seed_resources())
        resources: list[Resource] = []
        for index, resource in enumerate(resource_defs, start=1):
            resources.append(Resource(id=_resource_id(index), **resource))
        for resource in resources:
            session.add(resource)
        base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        bookings = [
            Booking(id=_booking_id(1), resource_id=_resource_id(1), user_id="demo-employee", start_time=base.replace(hour=9), end_time=base.replace(hour=10, minute=30), purpose="Team meeting", purpose_category="meeting", attendees_count=8, status=BookingStatus.pending, created_at=base - timedelta(days=3)),
            Booking(id=_booking_id(2), resource_id=_resource_id(3), user_id="demo-employee", start_time=base.replace(hour=14), end_time=base.replace(hour=17), purpose="Client call", purpose_category="other", attendees_count=3, status=BookingStatus.pending, created_at=base - timedelta(days=2)),
            Booking(id=_booking_id(3), resource_id=_resource_id(7), user_id="demo-admin", start_time=(base + timedelta(days=1)).replace(hour=10), end_time=(base + timedelta(days=1)).replace(hour=12), purpose="Workshop", purpose_category="workshop", attendees_count=14, status=BookingStatus.pending, created_at=base - timedelta(days=1)),
            Booking(id=_booking_id(4), resource_id=_resource_id(5), user_id="demo-employee", start_time=(base + timedelta(days=1)).replace(hour=13), end_time=(base + timedelta(days=1)).replace(hour=14), purpose="Presentation", purpose_category="presentation", attendees_count=1, status=BookingStatus.pending, created_at=base - timedelta(days=1)),
            Booking(id=_booking_id(5), resource_id=_resource_id(4), user_id="demo-admin", start_time=(base + timedelta(days=2)).replace(hour=8), end_time=(base + timedelta(days=2)).replace(hour=12), purpose="Maintenance", purpose_category="maintenance", attendees_count=6, status=BookingStatus.pending, created_at=base - timedelta(days=1)),
            Booking(id=_booking_id(6), resource_id=_resource_id(11), user_id="demo-admin", start_time=(base + timedelta(days=2)).replace(hour=14), end_time=(base + timedelta(days=2)).replace(hour=16), purpose="Quarterly planning", purpose_category="planning", attendees_count=22, status=BookingStatus.pending, created_at=base - timedelta(days=2)),
            Booking(id=_booking_id(7), resource_id=_resource_id(13), user_id="demo-employee", start_time=(base + timedelta(days=3)).replace(hour=9), end_time=(base + timedelta(days=3)).replace(hour=12), purpose="Internal training", purpose_category="training", attendees_count=16, status=BookingStatus.pending, created_at=base - timedelta(days=2)),
            Booking(id=_booking_id(8), resource_id=_resource_id(20), user_id="demo-employee", start_time=(base + timedelta(days=3)).replace(hour=13), end_time=(base + timedelta(days=3)).replace(hour=14), purpose="Customer interview recording", purpose_category="interview", attendees_count=3, status=BookingStatus.pending, created_at=base - timedelta(days=1)),
        ]
        for booking in bookings:
            session.add(booking)
        session.commit()


def seed_if_empty(sql_engine=engine) -> bool:
    """Seed demo rows only when the database has no resources yet."""
    with Session(sql_engine) as session:
        resource_count = session.exec(select(func.count()).select_from(Resource)).one()
    if int(resource_count) > 0:
        return False
    seed_demo_data(sql_engine)
    return True


if __name__ == "__main__":
    seed_demo_data()
