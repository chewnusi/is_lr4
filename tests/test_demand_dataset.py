from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session
from sqlmodel import select

from app.ml.demand.demand_dataset import build_training_rows
from app.ml.demand.synthetic_history import generate_synthetic_history
from app.models_db import Booking, BookingPurposeCategory, BookingStatus, Resource


def test_dataset_parses_weekday_hour_and_duration(db_engine):
    with Session(db_engine) as session:
        resource = Resource(
            id="r1",
            name="Room",
            type="meeting_room",
            location="A",
            building="Building A",
            capacity=10,
            is_active=True,
        )
        session.add(resource)
        start = datetime(2026, 4, 7, 10, 0, 0)  # Tuesday
        booking = Booking(
            id="b1",
            resource_id="r1",
            user_id="demo-employee",
            start_time=start,
            end_time=start + timedelta(minutes=90),
            purpose="Team sync",
            purpose_category=BookingPurposeCategory.meeting,
            attendees_count=5,
            status=BookingStatus.approved,
            created_at=start - timedelta(days=1),
        )
        session.add(booking)
        session.commit()

        rows = build_training_rows(session)
    assert len(rows) == 1
    row = rows[0]
    assert row.day_of_week == 1
    assert row.hour == 10
    assert row.duration_minutes == 90
    assert row.bookings_count == 1


def test_synthetic_generator_creates_patterned_history(db_engine, monkeypatch):
    import app.ml.demand.synthetic_history as synthetic_module

    monkeypatch.setattr(synthetic_module, "engine", db_engine)
    with Session(db_engine) as session:
        for index, resource_type in enumerate(["meeting_room", "lab", "car", "equipment"], start=1):
            session.add(
                Resource(
                    id=f"r{index}",
                    name=f"Resource {index}",
                    type=resource_type,
                    location="Seed location",
                    building="Seed building",
                    capacity=20,
                    is_active=True,
                )
            )
        session.commit()

    inserted = generate_synthetic_history(count=220, months_back=2, seed=7, reset=True)
    assert inserted == 220

    with Session(db_engine) as session:
        synthetic_rows = session.exec(select(Booking).where(Booking.id.startswith("synthetic-bk-"))).all()
    assert len(synthetic_rows) == 220
