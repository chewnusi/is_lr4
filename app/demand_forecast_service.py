"""Demand forecast service layer."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.ml.demand.inference import forecast_by_hour, load_metadata


def get_demand_forecast(session: Session, resource_type: str, target_date: date, building: str | None = None) -> dict:
    forecast = forecast_by_hour(session, target_date, resource_type, building)
    ranked = sorted(forecast, key=lambda row: row["predicted_demand"], reverse=True)
    peak_hours = sorted([item["hour"] for item in ranked[:2]])
    return {
        "resource_type": resource_type,
        "date": target_date.isoformat(),
        "building": building,
        "forecast": forecast,
        "peak_hours": peak_hours,
        "model_info": load_metadata(),
    }
