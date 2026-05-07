"""Inference helpers for cancellation risk scoring."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import joblib
from sqlmodel import Session, select

from app.models_db import Booking, Resource, User

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "model_store"


def _model_path() -> Path:
    return Path(os.getenv("RISK_MODEL_PATH", str(DEFAULT_MODEL_DIR / "risk_model.joblib")))


def _meta_path() -> Path:
    return Path(os.getenv("RISK_MODEL_META_PATH", str(DEFAULT_MODEL_DIR / "risk_model.meta.json")))


def load_model_artifact() -> tuple[object, object]:
    path = _model_path()
    if not path.exists():
        raise FileNotFoundError("Cancellation-risk model artifact not found. Run: python -m app.ml.cancellation_risk.train_model")
    artifact = joblib.load(path)
    return artifact["model"], artifact["vectorizer"]


def load_metadata() -> dict:
    path = _meta_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _user_history_stats(session: Session, user_id: str) -> tuple[int, float]:
    bookings = session.exec(select(Booking).where(Booking.user_id == user_id)).all()
    total = len(bookings)
    if total == 0:
        return 0, 0.0
    cancelled = sum(1 for booking in bookings if booking.status.value == "cancelled")
    return total, (cancelled / total)


def build_feature_row(
    session: Session,
    *,
    user_id: str,
    resource_id: str,
    start_time: datetime,
    end_time: datetime,
    purpose_category: str,
    attendees_count: int | None,
) -> dict:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise ValueError(f"Unknown resource_id: {resource_id}")
    user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"Unknown user_id: {user_id}")
    booking_count, cancel_rate = _user_history_stats(session, user_id)
    duration_minutes = max(1, int((end_time - start_time).total_seconds() // 60))
    lead_time_hours = max(0, int((start_time - datetime.now()).total_seconds() // 3600))
    attendees = attendees_count or 1
    return {
        "user_id": user_id,
        "user_role": user.role.value,
        "user_booking_count": booking_count,
        "user_cancel_rate": cancel_rate,
        "resource_type": resource.type,
        "building": resource.building or "unknown",
        "day_of_week": start_time.weekday(),
        "hour": start_time.hour,
        "duration_minutes": duration_minutes,
        "lead_time_hours": lead_time_hours,
        "attendees_count": attendees,
        "capacity_utilization": min(2.0, attendees / max(1, resource.capacity)),
        "purpose_category": purpose_category or "other",
    }


def predict_risk_for_rows(feature_rows: list[dict]) -> list[float]:
    if not feature_rows:
        return []
    model, vectorizer = load_model_artifact()
    matrix = vectorizer.transform(feature_rows)
    probs = model.predict_proba(matrix)[:, 1]
    return [float(round(prob, 4)) for prob in probs]

