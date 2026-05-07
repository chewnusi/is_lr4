from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import get_current_user
from app.cancellation_risk_service import score_cancellation_risk
from app.db import get_session
from app.models_db import User, UserRole
from app.schemas import CancellationRiskRequest, CancellationRiskResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/cancellation-risk", response_model=CancellationRiskResponse)
def cancellation_risk(
    payload: CancellationRiskRequest,
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> CancellationRiskResponse:
    if actor.role == UserRole.employee and payload.user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees can only score their own bookings")
    try:
        return score_cancellation_risk(session, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

