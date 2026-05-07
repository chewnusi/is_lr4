"""Inference helpers for booking recommendations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import joblib
from sqlmodel import Session, select

from app.ml.recommendation.feature_builder import CandidateOption, RecommendationRequest, candidate_to_features, check_availability, generate_candidate_offsets
from app.models_db import Booking, Resource

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "model_store"


def _model_path() -> Path:
    return Path(os.getenv("RECO_MODEL_PATH", str(DEFAULT_MODEL_DIR / "reco_model.joblib")))


def _meta_path() -> Path:
    return Path(os.getenv("RECO_MODEL_META_PATH", str(DEFAULT_MODEL_DIR / "reco_model.meta.json")))


def load_model_artifact() -> tuple[object, object]:
    path = _model_path()
    if not path.exists():
        raise FileNotFoundError("Recommendation model artifact not found. Run: python -m app.ml.recommendation.train_model")
    artifact = joblib.load(path)
    return artifact["model"], artifact["vectorizer"]


def load_metadata() -> dict:
    path = _meta_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rank_candidates(session: Session, request: RecommendationRequest, top_n: int = 5) -> list[dict]:
    model, vectorizer = load_model_artifact()
    resources = session.exec(select(Resource).where(Resource.is_active == True)).all()  # noqa: E712
    resources = [resource for resource in resources if resource.type == request.resource_type and (request.building is None or resource.building == request.building)]
    if not resources:
        resources = session.exec(select(Resource).where(Resource.is_active == True)).all()  # noqa: E712
    bookings = session.exec(select(Booking)).all()
    demand_by_hour: dict[int, int] = {}
    popularity: dict[str, int] = {}
    for booking in bookings:
        demand_by_hour[booking.start_time.hour] = demand_by_hour.get(booking.start_time.hour, 0) + 1
        popularity[booking.resource_id] = popularity.get(booking.resource_id, 0) + 1
    max_popularity = max(popularity.values()) if popularity else 1

    feature_rows: list[dict] = []
    raw_candidates: list[dict] = []
    for resource in resources:
        for offset in generate_candidate_offsets():
            candidate_start = request.preferred_start_time + offset
            candidate_end = candidate_start + timedelta(minutes=request.duration_minutes)
            available = check_availability(bookings, resource.id, candidate_start, candidate_end)
            if request.attendees_count > resource.capacity:
                continue
            if not available:
                continue
            candidate = CandidateOption(
                resource=resource,
                start_time=candidate_start,
                end_time=candidate_end,
                is_available=available,
                current_demand_at_hour=demand_by_hour.get(candidate_start.hour, 0),
                historical_popularity=popularity.get(resource.id, 0) / max_popularity,
            )
            feature_rows.append(candidate_to_features(request, candidate))
            raw_candidates.append(
                {
                    "resource_id": resource.id,
                    "resource_name": resource.name,
                    "start_time": candidate_start.isoformat(),
                    "end_time": candidate_end.isoformat(),
                    "building": resource.building,
                    "resource_type": resource.type,
                }
            )
    if not feature_rows:
        return []
    matrix = vectorizer.transform(feature_rows)
    probs = model.predict_proba(matrix)[:, 1]
    ranked = []
    for candidate, prob in sorted(zip(raw_candidates, probs), key=lambda item: item[1], reverse=True)[:top_n]:
        ranked.append(
            {
                **candidate,
                "score": float(round(prob, 4)),
                "reason": "ML model ranked this option as a strong match",
            }
        )
    return ranked
