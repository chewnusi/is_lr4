"""Train cancellation risk model and persist artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, precision_score, recall_score, roc_auc_score

from app.ml.cancellation_risk.dataset import feature_dict, load_training_rows_from_db

MODEL_DIR = Path(__file__).resolve().parent / "model_store"
MODEL_PATH = MODEL_DIR / "risk_model.joblib"
META_PATH = MODEL_DIR / "risk_model.meta.json"


def _best_threshold(y_true: list[int], probs: list[float]) -> tuple[float, dict]:
    if not y_true or len(set(y_true)) < 2:
        return 0.5, {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    best_t = 0.5
    best_metrics = {"precision": 0.0, "recall": 0.0, "f1": -1.0}
    for threshold in [x / 100 for x in range(10, 91, 5)]:
        preds = [1 if p >= threshold else 0 for p in probs]
        precision = precision_score(y_true, preds, zero_division=0)
        recall = recall_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        if f1 > best_metrics["f1"]:
            best_t = threshold
            best_metrics = {"precision": precision, "recall": recall, "f1": f1}
    return best_t, best_metrics


def train_and_save(random_state: int = 42) -> dict:
    rows = load_training_rows_from_db()
    if len(rows) < 200:
        raise RuntimeError("Cancellation-risk dataset too small. Generate more history first.")
    split_idx = max(1, int(len(rows) * 0.8))
    train_rows = rows[:split_idx]
    test_rows = rows[split_idx:]
    x_train = [feature_dict(row) for row in train_rows]
    x_test = [feature_dict(row) for row in test_rows]
    y_train = [row.will_cancel for row in train_rows]
    y_test = [row.will_cancel for row in test_rows]

    vectorizer = DictVectorizer(sparse=True)
    x_train_vec = vectorizer.fit_transform(x_train)
    x_test_vec = vectorizer.transform(x_test)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=14,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(x_train_vec, y_train)
    probs = model.predict_proba(x_test_vec)[:, 1]
    threshold, threshold_metrics = _best_threshold(y_test, probs.tolist())
    preds = [1 if prob >= threshold else 0 for prob in probs]

    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
        "roc_auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.0,
        "pr_auc": average_precision_score(y_test, probs) if len(set(y_test)) > 1 else 0.0,
        "optimal_threshold": threshold,
        "threshold_metrics": threshold_metrics,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "vectorizer": vectorizer, "optimal_threshold": threshold}, MODEL_PATH)
    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "model_version": "v1",
        "rows_total": len(rows),
        "rows_train": len(train_rows),
        "rows_test": len(test_rows),
        "cancel_rate_train": (sum(y_train) / len(y_train)) if y_train else 0.0,
        "cancel_rate_test": (sum(y_test) / len(y_test)) if y_test else 0.0,
        "metrics": metrics,
        "features": list(x_train[0].keys()) if x_train else [],
    }
    META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Train cancellation-risk model.")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(train_and_save(random_state=args.random_state), indent=2))


if __name__ == "__main__":
    _cli()

