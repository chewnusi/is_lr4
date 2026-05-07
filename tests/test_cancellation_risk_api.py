from __future__ import annotations

import json
from datetime import datetime, timedelta

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer


def _seed_resource(client):
    response = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Risk Room", "type": "meeting_room", "location": "HQ", "building": "Building A", "capacity": 10, "is_active": True},
    )
    return response.json()["id"]


def _write_risk_model(tmp_path, monkeypatch):
    rows = [
        {
            "user_id": "demo-employee",
            "user_role": "employee",
            "user_booking_count": 1,
            "user_cancel_rate": 0.0,
            "resource_type": "meeting_room",
            "building": "Building A",
            "day_of_week": 2,
            "hour": 10,
            "duration_minutes": 60,
            "lead_time_hours": 24,
            "attendees_count": 4,
            "capacity_utilization": 0.4,
            "purpose_category": "meeting",
        },
        {
            "user_id": "demo-employee",
            "user_role": "employee",
            "user_booking_count": 8,
            "user_cancel_rate": 0.5,
            "resource_type": "meeting_room",
            "building": "Building A",
            "day_of_week": 5,
            "hour": 8,
            "duration_minutes": 180,
            "lead_time_hours": 1,
            "attendees_count": 1,
            "capacity_utilization": 0.1,
            "purpose_category": "other",
        },
    ]
    target = [0, 1]
    vectorizer = DictVectorizer(sparse=True)
    x = vectorizer.fit_transform(rows)
    model = RandomForestClassifier(n_estimators=20, random_state=7)
    model.fit(x, target)
    model_path = tmp_path / "risk_model.joblib"
    meta_path = tmp_path / "risk_model.meta.json"
    joblib.dump({"model": model, "vectorizer": vectorizer}, model_path)
    meta_path.write_text(json.dumps({"model_version": "test"}), encoding="utf-8")
    monkeypatch.setenv("RISK_MODEL_PATH", str(model_path))
    monkeypatch.setenv("RISK_MODEL_META_PATH", str(meta_path))


def test_cancellation_risk_missing_model_returns_503(client, tmp_path, monkeypatch):
    resource_id = _seed_resource(client)
    monkeypatch.setenv("RISK_MODEL_PATH", str(tmp_path / "missing_risk_model.joblib"))
    monkeypatch.setenv("RISK_MODEL_META_PATH", str(tmp_path / "missing_risk_model.meta.json"))
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=3)
    response = client.post(
        "/analytics/cancellation-risk?user_id=demo-admin",
        json={
            "user_id": "demo-employee",
            "resource_id": resource_id,
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(hours=1)).isoformat(),
            "purpose_category": "meeting",
            "attendees_count": 4,
        },
    )
    assert response.status_code == 503


def test_cancellation_risk_success_returns_probability(client, tmp_path, monkeypatch):
    resource_id = _seed_resource(client)
    _write_risk_model(tmp_path, monkeypatch)
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=5)
    response = client.post(
        "/analytics/cancellation-risk?user_id=demo-employee",
        json={
            "user_id": "demo-employee",
            "resource_id": resource_id,
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(hours=2)).isoformat(),
            "purpose_category": "meeting",
            "attendees_count": 4,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "cancellation_risk" in payload
    assert 0.0 <= payload["cancellation_risk"] <= 1.0

