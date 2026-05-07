from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.models_db import User
from app.recommendation_service import get_booking_recommendations
from app.schemas import RecommendationRequest, RecommendationResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/booking-options", response_model=RecommendationResponse)
def booking_options(
    payload: RecommendationRequest,
    session: Session = Depends(get_session),
    _actor: User = Depends(get_current_user),
) -> RecommendationResponse:
    try:
        return get_booking_recommendations(session, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
