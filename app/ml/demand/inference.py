"""Model inference helpers for demand forecasting."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import joblib
from sqlmodel import Session

from app.ml.demand.demand_dataset import build_hourly_inference_rows

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "model_store"


def _model_path() -> Path:
    return Path(os.getenv("DEMAND_MODEL_PATH", str(DEFAULT_MODEL_DIR / "demand_model.joblib")))


def _meta_path() -> Path:
    return Path(os.getenv("DEMAND_MODEL_META_PATH", str(DEFAULT_MODEL_DIR / "demand_model.meta.json")))


def load_model_artifact() -> tuple[object, object]:
    path = _model_path()
    if not path.exists():
        raise FileNotFoundError("Demand model artifact not found. Run: python -m app.ml.demand.train_model")
    artifact = joblib.load(path)
    return artifact["model"], artifact["vectorizer"]


def load_metadata() -> dict:
    path = _meta_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def forecast_by_hour(session: Session, target_date: date, resource_type: str, building: str | None = None) -> list[dict]:
    model, vectorizer = load_model_artifact()
    feature_rows = build_hourly_inference_rows(session, target_date, resource_type, building)
    matrix = vectorizer.transform(feature_rows)
    predictions = model.predict(matrix)
    return [{"hour": int(row["hour"]), "predicted_demand": max(0.0, float(round(pred, 3)))} for row, pred in zip(feature_rows, predictions)]
