from __future__ import annotations


def test_resource_crud(client):
    create = client.post(
        "/resources?user_id=demo-admin",
        json={"name": "Room 1", "type": "meeting_room", "location": "A", "capacity": 4, "is_active": True},
    )
    assert create.status_code == 201
    rid = create.json()["id"]

    listing = client.get("/resources")
    assert listing.status_code == 200
    assert any(row["id"] == rid for row in listing.json())

    update = client.put(f"/resources/{rid}?user_id=demo-admin", json={"capacity": 6})
    assert update.status_code == 200
    assert update.json()["capacity"] == 6

    delete = client.delete(f"/resources/{rid}?user_id=demo-admin")
    assert delete.status_code == 204
