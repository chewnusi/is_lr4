from __future__ import annotations

from datetime import datetime, timedelta


def _resource(client):
    return client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Desk", "type": "equipment", "location": "C", "capacity": 1, "is_active": True},
    ).json()["id"]


def test_invalid_resource_id(client, booking_payload):
    booking_payload["resource_id"] = "missing"
    response = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert response.status_code == 400


def test_past_booking_rejected(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    booking_payload["start_time"] = (datetime.now() - timedelta(hours=2)).isoformat()
    booking_payload["end_time"] = (datetime.now() - timedelta(hours=1)).isoformat()
    response = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert response.status_code == 400


def test_invalid_time_order_rejected(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    booking_payload["end_time"] = booking_payload["start_time"]
    response = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert response.status_code == 400


def test_invalid_time_format_rejected(client):
    rid = _resource(client)
    response = client.post(
        "/bookings?user_id=demo-employee",
        json={
            "resource_id": rid,
            "user_id": "demo-employee",
            "start_time": "2022 05 05 12:00",
            "end_time": "2022 05 05 12:50",
            "purpose": "bad format",
        },
    )
    assert response.status_code == 422


def test_attendees_count_cannot_exceed_capacity(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    booking_payload["attendees_count"] = 5
    response = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert response.status_code == 400
