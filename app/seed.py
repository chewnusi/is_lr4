"""SQLite demo data seeding."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, delete, func, select

from app.db import engine
from app.models_db import Booking, BookingStatus, Resource

# Must match seeded resource/booking ids so re-runs replace demo data only.
DEMO_ID_PREFIX = "demo-seed-"


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


def seed_demo_data(sql_engine=engine) -> None:
    with Session(sql_engine) as session:
        clear_demo_data(session)
        resources: list[Resource] = [
            Resource(id=_resource_id(1), name="Executive Boardroom", type="meeting_room", location="Building A, 3rd floor", capacity=12, is_active=True),
            Resource(id=_resource_id(2), name="Huddle Pod 1", type="meeting_room", location="Building A, 2nd floor", capacity=4, is_active=True),
            Resource(id=_resource_id(3), name="Fleet Sedan 04 (Toyota Camry)", type="car", location="North parking, bay 4", capacity=5, is_active=True),
            Resource(id=_resource_id(4), name="Sprinter Van 2", type="car", location="Motor pool — Depot B", capacity=8, is_active=True),
            Resource(id=_resource_id(5), name="4K Projector Kit", type="equipment", location="AV closet, room 102", capacity=1, is_active=True),
            Resource(id=_resource_id(6), name="Portable PA System", type="equipment", location="Storage cage 12", capacity=1, is_active=True),
            Resource(id=_resource_id(7), name="Chemistry Lab A", type="lab", location="Science wing, east wing", capacity=20, is_active=True),
            Resource(id=_resource_id(8), name="Electronics Bench 3", type="lab", location="Engineering lab", capacity=4, is_active=True),
            Resource(id=_resource_id(9), name="Zoom Room West", type="meeting_room", location="Remote office pod", capacity=6, is_active=True),
            Resource(id=_resource_id(10), name="DSLR Camera Kit", type="equipment", location="Media cage", capacity=1, is_active=True),
        ]
        for resource in resources:
            session.add(resource)
        base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        bookings = [
            Booking(id=_booking_id(1), resource_id=_resource_id(1), user_id="demo-employee", start_time=base.replace(hour=9), end_time=base.replace(hour=10, minute=30), purpose="Team meeting", status=BookingStatus.pending),
            Booking(id=_booking_id(2), resource_id=_resource_id(3), user_id="demo-employee", start_time=base.replace(hour=14), end_time=base.replace(hour=17), purpose="Client call", status=BookingStatus.pending),
            Booking(id=_booking_id(3), resource_id=_resource_id(7), user_id="demo-admin", start_time=(base + timedelta(days=1)).replace(hour=10), end_time=(base + timedelta(days=1)).replace(hour=12), purpose="Workshop", status=BookingStatus.pending),
            Booking(id=_booking_id(4), resource_id=_resource_id(5), user_id="demo-employee", start_time=(base + timedelta(days=1)).replace(hour=13), end_time=(base + timedelta(days=1)).replace(hour=14), purpose="Presentation", status=BookingStatus.pending),
            Booking(id=_booking_id(5), resource_id=_resource_id(4), user_id="demo-admin", start_time=(base + timedelta(days=2)).replace(hour=8), end_time=(base + timedelta(days=2)).replace(hour=12), purpose="Maintenance", status=BookingStatus.pending),
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
