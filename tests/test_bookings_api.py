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
    bid = created.json()["id"]

    bad_approve = client.patch(f"/bookings/{bid}/approve?user_id=demo-employee")
    assert bad_approve.status_code == 403

    approved = client.patch(f"/bookings/{bid}/approve?user_id=demo-admin")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    second_approve = client.patch(f"/bookings/{bid}/approve?user_id=demo-admin")
    assert second_approve.status_code == 400

    cancelled = client.patch(f"/bookings/{bid}/cancel?user_id=demo-employee")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    deleted = client.delete(f"/bookings/{bid}?user_id=demo-employee")
    assert deleted.status_code == 204


def test_conflict_detection(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    first = client.post("/bookings?user_id=demo-employee", json=booking_payload).json()
    conflict_payload = dict(booking_payload)
    conflict_payload["start_time"] = booking_payload["start_time"]
    conflict_payload["end_time"] = booking_payload["end_time"]
    second = client.post("/bookings?user_id=demo-employee", json=conflict_payload).json()

    assert client.patch(f"/bookings/{first['id']}/approve?user_id=demo-admin").status_code == 200
    conflict = client.patch(f"/bookings/{second['id']}/approve?user_id=demo-admin")
    assert conflict.status_code == 400
