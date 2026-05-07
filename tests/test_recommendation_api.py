from __future__ import annotations

import json
from datetime import datetime, timedelta

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer


def _seed_resources(client):
    client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Meeting Room X", "type": "meeting_room", "location": "HQ", "building": "Building A", "capacity": 10, "is_active": True},
    )
    client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Meeting Room Y", "type": "meeting_room", "location": "HQ", "building": "Building A", "capacity": 8, "is_active": True},
    )


def _write_reco_model(tmp_path, monkeypatch):
    features = [
        {
            "resource_id": "r1",
            "resource_type": "meeting_room",
            "building": "Building A",
            "resource_capacity": 10,
            "features": "projector",
            "candidate_start_hour": 10,
            "candidate_weekday": 2,
            "duration_minutes": 60,
            "attendees_count": 5,
            "purpose_category": "meeting",
            "current_demand_at_hour": 3,
            "historical_popularity": 0.7,
            "capacity_gap": 5,
            "time_difference_minutes": 0,
            "is_available": 1,
            "is_peak_hour": 1,
            "building_match": 1,
            "type_match": 1,
        },
        {
            "resource_id": "r2",
            "resource_type": "meeting_room",
            "building": "Building A",
            "resource_capacity": 6,
            "features": "whiteboard",
            "candidate_start_hour": 13,
            "candidate_weekday": 2,
            "duration_minutes": 60,
            "attendees_count": 5,
            "purpose_category": "meeting",
            "current_demand_at_hour": 8,
            "historical_popularity": 0.2,
            "capacity_gap": 1,
            "time_difference_minutes": 60,
            "is_available": 1,
            "is_peak_hour": 0,
            "building_match": 1,
            "type_match": 1,
        },
    ]
    target = [1, 0]
    vec = DictVectorizer(sparse=True)
    x = vec.fit_transform(features)
    model = RandomForestClassifier(n_estimators=20, random_state=1)
    model.fit(x, target)
    model_path = tmp_path / "reco_model.joblib"
    meta_path = tmp_path / "reco_model.meta.json"
    joblib.dump({"model": model, "vectorizer": vec}, model_path)
    meta_path.write_text(json.dumps({"model_version": "test"}), encoding="utf-8")
    monkeypatch.setenv("RECO_MODEL_PATH", str(model_path))
    monkeypatch.setenv("RECO_MODEL_META_PATH", str(meta_path))


def test_recommendation_model_missing_returns_503(client, tmp_path, monkeypatch):
    monkeypatch.setenv("RECO_MODEL_PATH", str(tmp_path / "missing_reco_model.joblib"))
    monkeypatch.setenv("RECO_MODEL_META_PATH", str(tmp_path / "missing_reco_model.meta.json"))
    response = client.post(
        "/recommendations/booking-options?user_id=demo-employee",
        json={
            "resource_type": "meeting_room",
            "preferred_start_time": "2026-04-10T10:00:00",
            "duration_minutes": 60,
            "attendees_count": 5,
            "purpose_category": "meeting",
            "building": "Building A",
            "top_n": 3,
        },
    )
    assert response.status_code == 503


def test_recommendation_api_returns_ranked_options(client, tmp_path, monkeypatch):
    _seed_resources(client)
    _write_reco_model(tmp_path, monkeypatch)
    response = client.post(
        "/recommendations/booking-options?user_id=demo-employee",
        json={
            "resource_type": "meeting_room",
            "preferred_start_time": (datetime.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0).isoformat(),
            "duration_minutes": 60,
            "attendees_count": 5,
            "purpose_category": "meeting",
            "building": "Building A",
            "top_n": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "recommendations" in payload
    assert len(payload["recommendations"]) <= 3
    if payload["recommendations"]:
        assert "score" in payload["recommendations"][0]
        assert "cancellation_risk" in payload["recommendations"][0]
    if len(payload["recommendations"]) >= 2:
        assert len({row["resource_id"] for row in payload["recommendations"]}) >= 2


class _DummyVectorizer:
    def transform(self, rows):
        return rows


class _DummyModel:
    def predict_proba(self, rows):
        probs = []
        for row in rows:
            time_bonus = max(0.0, 1.0 - (row["time_difference_minutes"] / 180.0))
            capacity_bonus = max(0.0, 1.0 - (abs(row["capacity_gap"]) / 20.0))
            score = min(0.95, max(0.05, 0.35 + (0.35 * time_bonus) + (0.30 * capacity_bonus)))
            probs.append([1.0 - score, score])
        return np.array(probs, dtype=float)


def test_recommendation_known_expected_order_with_risk_penalty(client, monkeypatch):
    import app.ml.recommendation.inference as reco_inference

    small = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Small Risky Room", "type": "meeting_room", "location": "HQ", "building": "Building A", "capacity": 6, "is_active": True},
    ).json()
    large = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Large Safe Room", "type": "meeting_room", "location": "HQ", "building": "Building A", "capacity": 20, "is_active": True},
    ).json()

    monkeypatch.setattr(reco_inference, "load_model_artifact", lambda: (_DummyModel(), _DummyVectorizer()))
    monkeypatch.setattr(
        reco_inference,
        "predict_risk_for_rows",
        lambda rows: [min(0.99, max(0.01, float(row["capacity_utilization"]) * 0.9)) for row in rows],
    )

    response = client.post(
        "/recommendations/booking-options?user_id=demo-employee",
        json={
            "resource_type": "meeting_room",
            "preferred_start_time": (datetime.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0).isoformat(),
            "duration_minutes": 60,
            "attendees_count": 6,
            "purpose_category": "meeting",
            "building": "Building A",
            "top_n": 2,
        },
    )
    assert response.status_code == 200
    recs = response.json()["recommendations"]
    assert len(recs) == 2
    assert {recs[0]["resource_id"], recs[1]["resource_id"]} == {small["id"], large["id"]}
    assert recs[0]["resource_id"] == large["id"]
    assert recs[0]["cancellation_risk"] < recs[1]["cancellation_risk"]
