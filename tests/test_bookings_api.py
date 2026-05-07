from __future__ import annotations

from datetime import timedelta


def _resource(client):
    response = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Lab", "type": "lab", "location": "B", "capacity": 8, "is_active": True},
    )
    return response.json()["id"]


def test_booking_crud_and_transitions(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    created = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert created.status_code == 201
    created_data = created.json()
    bid = created_data["id"]
    assert created_data["created_at"] is not None
    assert created_data["updated_at"] is None
    assert created_data["cancelled_at"] is None

    bad_approve = client.patch(f"/bookings/{bid}/approve?user_id=demo-employee")
    assert bad_approve.status_code == 403

    approved = client.patch(f"/bookings/{bid}/approve?user_id=demo-admin")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["updated_at"] is not None

    second_approve = client.patch(f"/bookings/{bid}/approve?user_id=demo-admin")
    assert second_approve.status_code == 400

    cancelled = client.patch(f"/bookings/{bid}/cancel?user_id=demo-employee")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None

    deleted = client.delete(f"/bookings/{bid}?user_id=demo-employee")
    assert deleted.status_code == 204


def test_conflict_detection(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    first_response = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert first_response.status_code == 201
    first = first_response.json()
    conflict_payload = dict(booking_payload)
    conflict_payload["start_time"] = booking_payload["start_time"]
    conflict_payload["end_time"] = booking_payload["end_time"]
    second_response = client.post("/bookings?user_id=demo-employee", json=conflict_payload)
    assert second_response.status_code == 400
    assert "conflict" in second_response.json()["detail"].lower()
