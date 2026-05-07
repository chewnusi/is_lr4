from __future__ import annotations

from datetime import datetime, timedelta


def test_employee_cannot_manage_resources(client):
    response = client.post(
        "/resources?user_id=demo-employee",
        json={"name": "Room", "type": "meeting_room", "location": "A", "capacity": 4, "is_active": True},
    )
    assert response.status_code == 403


def test_employee_can_only_view_own_bookings(client):
    rid = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Resource", "type": "meeting_room", "location": "HQ", "capacity": 5, "is_active": True},
    ).json()["id"]
    base = datetime.now().replace(microsecond=0) + timedelta(days=1)
    payload = {
        "resource_id": rid,
        "user_id": "demo-admin",
        "start_time": base.isoformat(),
        "end_time": (base + timedelta(hours=1)).isoformat(),
        "purpose": "admin-only",
    }
    create = client.post("/bookings?user_id=demo-admin", json=payload)
    assert create.status_code == 201

    employee_list = client.get("/bookings?user_id=demo-employee")
    assert all(row["user_id"] == "demo-employee" for row in employee_list.json())
