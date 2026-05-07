"""Train recommendation ranking/classification model."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

from app.ml.recommendation.synthetic_dataset import OUTPUT_PATH

MODEL_DIR = Path(__file__).resolve().parent / "model_store"
MODEL_PATH = MODEL_DIR / "reco_model.joblib"
META_PATH = MODEL_DIR / "reco_model.meta.json"


def _load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _precision_at_k(rows: list[dict], probs: list[float], k: int = 3) -> float:
    grouped: dict[str, list[tuple[float, int]]] = {}
    for row, prob in zip(rows, probs):
        key = row["candidate_start_time"]
        grouped.setdefault(key, []).append((prob, int(row["accepted"])))
    if not grouped:
        return 0.0
    precisions = []
    for pairs in grouped.values():
        pairs.sort(key=lambda item: item[0], reverse=True)
        top = pairs[:k]
        precisions.append(sum(label for _, label in top) / len(top))
    return sum(precisions) / len(precisions)


def train_recommendation_model(dataset_path: Path = OUTPUT_PATH, random_state: int = 42) -> dict:
    rows = _load_rows(dataset_path)
    if len(rows) < 200:
        raise RuntimeError("Recommendation dataset too small. Generate with synthetic_dataset first.")
    targets = [int(row["accepted"]) for row in rows]
    features = []
    for row in rows:
        feature_row = dict(row)
        feature_row.pop("accepted", None)
        feature_row.pop("candidate_start_time", None)
        feature_row.pop("candidate_end_time", None)
        features.append(feature_row)
    x_train, x_test, y_train, y_test, rows_train, rows_test = train_test_split(
        features,
        targets,
        rows,
        test_size=0.2,
        random_state=random_state,
        stratify=targets,
    )
    vec = DictVectorizer(sparse=True)
    x_train_vec = vec.fit_transform(x_train)
    x_test_vec = vec.transform(x_test)
    model = RandomForestClassifier(n_estimators=250, max_depth=14, random_state=random_state, n_jobs=-1)
    model.fit(x_train_vec, y_train)
    preds = model.predict(x_test_vec)
    probs = model.predict_proba(x_test_vec)[:, 1]
    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
        "precision_at_3": _precision_at_k(rows_test, probs, k=3),
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "vectorizer": vec}, MODEL_PATH)
    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "model_version": "v1",
        "dataset_path": str(dataset_path),
        "rows_total": len(rows),
        "metrics": metrics,
    }
    META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Train recommendation model.")
    parser.add_argument("--dataset", type=str, default=str(OUTPUT_PATH))
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    metadata = train_recommendation_model(dataset_path=Path(args.dataset), random_state=args.random_state)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    _cli()
