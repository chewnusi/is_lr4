"""Recommendation service layer."""

from __future__ import annotations

from app.ml.recommendation.feature_builder import RecommendationRequest as RecoRequestFeatures
from app.ml.recommendation.inference import load_metadata, rank_candidates
from app.schemas import RecommendationRequest
from sqlmodel import Session


def get_booking_recommendations(session: Session, payload: RecommendationRequest) -> dict:
    request = RecoRequestFeatures(
        resource_type=payload.resource_type,
        preferred_start_time=payload.preferred_start_time,
        duration_minutes=payload.duration_minutes,
        attendees_count=payload.attendees_count,
        purpose_category=payload.purpose_category,
        building=payload.building,
    )
    recommendations = rank_candidates(session, request, top_n=payload.top_n)
    return {"recommendations": recommendations, "model_info": load_metadata()}
