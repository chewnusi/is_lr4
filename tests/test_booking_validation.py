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


def test_partial_overlap_booking_rejected(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    first = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert first.status_code == 201
    base_start = datetime.fromisoformat(booking_payload["start_time"])
    overlap_payload = dict(booking_payload)
    overlap_payload["start_time"] = (base_start + timedelta(minutes=30)).isoformat()
    overlap_payload["end_time"] = (base_start + timedelta(minutes=90)).isoformat()
    second = client.post("/bookings?user_id=demo-employee", json=overlap_payload)
    assert second.status_code == 400
    assert "conflict" in second.json()["detail"].lower()


def test_touching_timeslots_do_not_conflict(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    first = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert first.status_code == 201
    base_end = datetime.fromisoformat(booking_payload["end_time"])
    next_payload = dict(booking_payload)
    next_payload["start_time"] = base_end.isoformat()
    next_payload["end_time"] = (base_end + timedelta(hours=1)).isoformat()
    second = client.post("/bookings?user_id=demo-employee", json=next_payload)
    assert second.status_code == 201


def test_cancelled_booking_frees_timeslot_for_rebooking(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    created = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert created.status_code == 201
    booking_id = created.json()["id"]
    cancelled = client.patch(f"/bookings/{booking_id}/cancel?user_id=demo-employee")
    assert cancelled.status_code == 200
    reused = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert reused.status_code == 201


def test_update_booking_into_conflicting_slot_rejected(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    first = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert first.status_code == 201

    base_start = datetime.fromisoformat(booking_payload["start_time"])
    later_payload = dict(booking_payload)
    later_payload["start_time"] = (base_start + timedelta(hours=2)).isoformat()
    later_payload["end_time"] = (base_start + timedelta(hours=3)).isoformat()
    second = client.post("/bookings?user_id=demo-employee", json=later_payload)
    assert second.status_code == 201

    update = client.put(
        f"/bookings/{second.json()['id']}?user_id=demo-employee",
        json={
            "resource_id": rid,
            "start_time": booking_payload["start_time"],
            "end_time": booking_payload["end_time"],
            "purpose": "Shifted into conflict",
        },
    )
    assert update.status_code == 400
    assert "conflict" in update.json()["detail"].lower()


def test_cross_user_same_resource_timeslot_conflict_rejected(client, booking_payload):
    rid = _resource(client)
    booking_payload["resource_id"] = rid
    first = client.post("/bookings?user_id=demo-employee", json=booking_payload)
    assert first.status_code == 201

    same_slot_other_user = dict(booking_payload)
    same_slot_other_user["user_id"] = "demo-employee-001"
    second = client.post("/bookings?user_id=demo-admin", json=same_slot_other_user)
    assert second.status_code == 400
    assert "conflict" in second.json()["detail"].lower()
