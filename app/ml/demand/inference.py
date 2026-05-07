"""Model inference helpers for demand forecasting."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
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


def _baseline_predictions(feature_rows: list[dict], metadata: Mapping) -> list[float]:
    runtime = metadata.get("baseline_runtime")
    if not isinstance(runtime, dict):
        return [0.0 for _ in feature_rows]
    grouped_means = runtime.get("grouped_means")
    fallback = runtime.get("fallback_mean", 0.0)
    if not isinstance(grouped_means, dict):
        return [float(fallback) for _ in feature_rows]
    preds: list[float] = []
    for row in feature_rows:
        key = f"{row['day_of_week']}|{row['hour']}|{row['resource_type']}"
        preds.append(float(grouped_means.get(key, fallback)))
    return preds


def forecast_by_hour(session: Session, target_date: date, resource_type: str, building: str | None = None) -> list[dict]:
    metadata = load_metadata()
    feature_rows = build_hourly_inference_rows(session, target_date, resource_type, building)
    if metadata.get("selected_model") == "baseline":
        predictions = _baseline_predictions(feature_rows, metadata)
    else:
        model, vectorizer = load_model_artifact()
        matrix = vectorizer.transform(feature_rows)
        predictions = model.predict(matrix)
    return [{"hour": int(row["hour"]), "predicted_demand": max(0.0, float(round(pred, 3)))} for row, pred in zip(feature_rows, predictions)]
