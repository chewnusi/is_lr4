"""Inference helpers for booking recommendations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import joblib
from sqlmodel import Session, select

from app.ml.cancellation_risk.inference import build_feature_row as build_risk_feature_row
from app.ml.cancellation_risk.inference import predict_risk_for_rows
from app.ml.recommendation.feature_builder import CandidateOption, RecommendationRequest, candidate_to_features, check_availability, generate_candidate_offsets
from app.models_db import Booking, Resource

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "model_store"
DEFAULT_RISK_PENALTY_ALPHA = float(os.getenv("RECO_RISK_ALPHA", "0.35"))


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


def rank_candidates(session: Session, request: RecommendationRequest, user_id: str, top_n: int = 5) -> list[dict]:
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
                    "time_difference_minutes": abs(int((candidate_start - request.preferred_start_time).total_seconds() // 60)),
                    "capacity_gap": resource.capacity - request.attendees_count,
                }
            )
    if not feature_rows:
        return []
    matrix = vectorizer.transform(feature_rows)
    probs = model.predict_proba(matrix)[:, 1]
    risk_feature_rows: list[dict] = []
    for candidate in raw_candidates:
        risk_feature_rows.append(
            build_risk_feature_row(
                session,
                user_id=user_id,
                resource_id=candidate["resource_id"],
                start_time=datetime.fromisoformat(candidate["start_time"]),
                end_time=datetime.fromisoformat(candidate["end_time"]),
                purpose_category=request.purpose_category,
                attendees_count=request.attendees_count,
            )
        )
    try:
        cancellation_risks = predict_risk_for_rows(risk_feature_rows)
    except FileNotFoundError:
        cancellation_risks = [0.0 for _ in risk_feature_rows]
    scored: list[dict] = []
    for candidate, prob, cancel_risk in zip(raw_candidates, probs, cancellation_risks):
        final_score = float(prob) * (1.0 - (DEFAULT_RISK_PENALTY_ALPHA * float(cancel_risk)))
        scored.append(
            {
                **candidate,
                "raw_score": float(round(prob, 4)),
                "cancellation_risk": float(round(cancel_risk, 4)),
                "score": float(round(final_score, 4)),
            }
        )

    # Primary rank: model score.
    # Tie-breakers: closer requested time, tighter positive capacity fit.
    scored.sort(
        key=lambda item: (
            -item["score"],
            item["time_difference_minutes"],
            abs(item["capacity_gap"]),
        )
    )

    # Diversify output so top-N is not dominated by one resource.
    # First pass keeps only the best slot per resource.
    selected: list[dict] = []
    seen_resources: set[str] = set()
    for item in scored:
        if item["resource_id"] in seen_resources:
            continue
        selected.append(item)
        seen_resources.add(item["resource_id"])
        if len(selected) >= top_n:
            break

    # Backfill if diversity filtering left fewer than top_n.
    if len(selected) < top_n:
        seen_pairs = {(row["resource_id"], row["start_time"]) for row in selected}
        for item in scored:
            pair = (item["resource_id"], item["start_time"])
            if pair in seen_pairs:
                continue
            selected.append(item)
            seen_pairs.add(pair)
            if len(selected) >= top_n:
                break

    return [
        {
            "resource_id": item["resource_id"],
            "resource_name": item["resource_name"],
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "building": item["building"],
            "resource_type": item["resource_type"],
            "score": item["score"],
            "cancellation_risk": item["cancellation_risk"],
            "reason": "Combined recommendation score adjusted by cancellation risk",
        }
        for item in selected
    ]
