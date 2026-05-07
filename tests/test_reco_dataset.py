from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.ml.recommendation.synthetic_dataset import generate_reco_synthetic_dataset
from app.models_db import Booking, BookingPurposeCategory, BookingStatus, Resource
from datetime import datetime, timedelta


def test_reco_synthetic_dataset_generation(db_engine, monkeypatch, tmp_path):
    import app.ml.recommendation.synthetic_dataset as synthetic_module

    monkeypatch.setattr(synthetic_module, "engine", db_engine)
    with Session(db_engine) as session:
        session.add(Resource(id="r1", name="Room 1", type="meeting_room", location="A", building="B1", capacity=8, is_active=True))
        session.add(Resource(id="r2", name="Lab 1", type="lab", location="B", building="B1", capacity=20, is_active=True))
        session.add(
            Booking(
                id="b1",
                resource_id="r1",
                user_id="demo-employee",
                start_time=datetime.now() + timedelta(days=1),
                end_time=datetime.now() + timedelta(days=1, hours=1),
                purpose="Planning",
                purpose_category=BookingPurposeCategory.planning,
                attendees_count=4,
                status=BookingStatus.approved,
                created_at=datetime.now(),
            )
        )
        session.commit()
    output = tmp_path / "reco.csv"
    path = generate_reco_synthetic_dataset(samples=80, seed=7, output_path=output)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "accepted" in content
