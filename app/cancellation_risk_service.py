"""Cancellation-risk service layer."""

from __future__ import annotations

from sqlmodel import Session

from app.ml.cancellation_risk.inference import build_feature_row, load_metadata, predict_risk_for_rows
from app.schemas import CancellationRiskRequest


def score_cancellation_risk(session: Session, payload: CancellationRiskRequest) -> dict:
    feature_row = build_feature_row(
        session,
        user_id=payload.user_id,
        resource_id=payload.resource_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        purpose_category=payload.purpose_category,
        attendees_count=payload.attendees_count,
    )
    risks = predict_risk_for_rows([feature_row])
    risk = risks[0] if risks else 0.0
    return {"cancellation_risk": risk, "model_info": load_metadata()}

