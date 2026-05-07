from __future__ import annotations

import json
from datetime import datetime, timedelta

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer


def _seed_history(client):
    resource = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Analytics Room", "type": "meeting_room", "location": "HQ", "building": "Building A", "capacity": 12, "is_active": True},
    ).json()
    base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    for offset in range(4):
        payload = {
            "resource_id": resource["id"],
            "user_id": "demo-employee",
            "start_time": (base + timedelta(days=offset)).isoformat(),
            "end_time": (base + timedelta(days=offset, hours=1)).isoformat(),
            "purpose": "Planning",
            "purpose_category": "planning",
            "attendees_count": 5,
        }
        client.post("/bookings?user_id=demo-employee", json=payload)
    return resource


def _write_model_artifacts(tmp_path, monkeypatch):
    vectorizer = DictVectorizer(sparse=True)
    features = [
        {"day_of_week": 0, "hour": 9, "resource_type": "meeting_room", "building": "Building A", "purpose_category": "planning", "duration_minutes": 60, "status": "approved"},
        {"day_of_week": 1, "hour": 10, "resource_type": "meeting_room", "building": "Building A", "purpose_category": "planning", "duration_minutes": 60, "status": "approved"},
    ]
    target = [2.0, 4.0]
    x = vectorizer.fit_transform(features)
    model = RandomForestRegressor(n_estimators=20, random_state=1)
    model.fit(x, target)
    model_path = tmp_path / "demand_model.joblib"
    meta_path = tmp_path / "demand_model.meta.json"
    joblib.dump({"model": model, "vectorizer": vectorizer}, model_path)
    meta_path.write_text(json.dumps({"model_version": "test"}), encoding="utf-8")
    monkeypatch.setenv("DEMAND_MODEL_PATH", str(model_path))
    monkeypatch.setenv("DEMAND_MODEL_META_PATH", str(meta_path))


def test_demand_forecast_requires_admin(client):
    response = client.get("/analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&user_id=demo-employee")
    assert response.status_code == 403


def test_demand_forecast_returns_service_unavailable_without_model(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DEMAND_MODEL_PATH", str(tmp_path / "missing_demand_model.joblib"))
    monkeypatch.setenv("DEMAND_MODEL_META_PATH", str(tmp_path / "missing_demand_model.meta.json"))
    response = client.get("/analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&user_id=demo-admin")
    assert response.status_code == 503


def test_demand_forecast_success(client, tmp_path, monkeypatch):
    _seed_history(client)
    _write_model_artifacts(tmp_path, monkeypatch)
    response = client.get("/analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&building=Building%20A&user_id=demo-admin")
    assert response.status_code == 200
    payload = response.json()
    assert payload["resource_type"] == "meeting_room"
    assert payload["date"] == "2026-04-10"
    assert len(payload["forecast"]) == 24
    assert len(payload["peak_hours"]) == 2


def test_demand_forecast_uses_baseline_when_selected(client, tmp_path, monkeypatch):
    _seed_history(client)
    meta_path = tmp_path / "demand_model.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "model_version": "test",
                "selected_model": "baseline",
                "baseline_runtime": {
                    "grouped_means": {"4|10|meeting_room": 3.5},
                    "fallback_mean": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEMAND_MODEL_PATH", str(tmp_path / "missing_demand_model.joblib"))
    monkeypatch.setenv("DEMAND_MODEL_META_PATH", str(meta_path))
    response = client.get("/analytics/demand-forecast?resource_type=meeting_room&date=2026-04-10&user_id=demo-admin")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["forecast"]) == 24
