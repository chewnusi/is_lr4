from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.auth import get_current_user, require_admin
from app.db import get_session
from app.demand_forecast_service import get_demand_forecast
from app.models_db import User
from app.schemas import DemandForecastResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/demand-forecast", response_model=DemandForecastResponse)
def demand_forecast(
    resource_type: str = Query(..., min_length=1),
    date_value: date = Query(..., alias="date"),
    building: str | None = Query(default=None),
    session: Session = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> DemandForecastResponse:
    require_admin(actor)
    try:
        return get_demand_forecast(session, resource_type=resource_type, target_date=date_value, building=building)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
