"""Train demand forecasting model and persist artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.ml.demand.demand_dataset import DemandRow, load_training_rows_from_db

MODEL_DIR = Path(__file__).resolve().parent / "model_store"
MODEL_PATH = MODEL_DIR / "demand_model.joblib"
META_PATH = MODEL_DIR / "demand_model.meta.json"


def _chronological_split(rows: list[DemandRow], holdout_ratio: float = 0.2) -> tuple[list[DemandRow], list[DemandRow]]:
    ordered = sorted(rows, key=lambda row: (row.date, row.hour))
    cutoff = max(1, int(len(ordered) * (1 - holdout_ratio)))
    return ordered[:cutoff], ordered[cutoff:]


def _feature_dict(row: DemandRow) -> dict:
    return {
        "day_of_week": row.day_of_week,
        "hour": row.hour,
        "resource_type": row.resource_type,
        "building": row.building,
        "purpose_category": row.purpose_category,
        "duration_minutes": row.duration_minutes,
        "status": row.status,
    }


def _baseline_predict(train_rows: list[DemandRow], test_rows: list[DemandRow]) -> list[float]:
    grouped: dict[tuple[int, int, str], list[int]] = {}
    for row in train_rows:
        grouped.setdefault((row.day_of_week, row.hour, row.resource_type), []).append(row.bookings_count)
    fallback = mean([row.bookings_count for row in train_rows]) if train_rows else 0.0
    preds: list[float] = []
    for row in test_rows:
        values = grouped.get((row.day_of_week, row.hour, row.resource_type))
        preds.append(float(mean(values)) if values else float(fallback))
    return preds


def train_and_save(random_state: int = 42) -> dict:
    rows = load_training_rows_from_db()
    if len(rows) < 50:
        raise RuntimeError("Not enough rows for training. Generate synthetic history first.")
    train_rows, test_rows = _chronological_split(rows)
    y_train = [row.bookings_count for row in train_rows]
    y_test = [row.bookings_count for row in test_rows]
    baseline_preds = _baseline_predict(train_rows, test_rows)
    baseline_mae = mean_absolute_error(y_test, baseline_preds)
    baseline_rmse = mean_squared_error(y_test, baseline_preds) ** 0.5
    vec = DictVectorizer(sparse=True)
    x_train = vec.fit_transform([_feature_dict(row) for row in train_rows])
    x_test = vec.transform([_feature_dict(row) for row in test_rows])
    model = RandomForestRegressor(n_estimators=200, max_depth=12, min_samples_leaf=2, random_state=random_state, n_jobs=-1)
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    rf_mae = mean_absolute_error(y_test, predictions)
    rf_rmse = mean_squared_error(y_test, predictions) ** 0.5
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "vectorizer": vec}, MODEL_PATH)
    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "model_version": "v1",
        "rows_total": len(rows),
        "rows_train": len(train_rows),
        "rows_test": len(test_rows),
        "train_window": {"start": train_rows[0].date, "end": train_rows[-1].date},
        "test_window": {"start": test_rows[0].date, "end": test_rows[-1].date},
        "features": ["day_of_week", "hour", "resource_type", "building", "purpose_category", "duration_minutes", "status"],
        "baseline": {"mae": baseline_mae, "rmse": baseline_rmse},
        "random_forest": {"mae": rf_mae, "rmse": rf_rmse},
    }
    META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Train demand forecasting model.")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(train_and_save(random_state=args.random_state), indent=2))


if __name__ == "__main__":
    _cli()
