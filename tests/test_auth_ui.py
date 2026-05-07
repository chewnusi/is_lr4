from __future__ import annotations


def test_ui_login_and_logout_flow(client):
    login_response = client.post("/ui/login", data={"user_id": "demo-employee", "password": "ChangeMe123!"}, follow_redirects=False)
    assert login_response.status_code == 303
    assert login_response.headers["location"].startswith("/ui/dashboard")

    dashboard_response = client.get("/ui/dashboard")
    assert dashboard_response.status_code == 200

    logout_response = client.post("/ui/logout", follow_redirects=False)
    assert logout_response.status_code == 303
    assert logout_response.headers["location"].startswith("/ui/login")

    redirected_response = client.get("/ui/dashboard", follow_redirects=False)
    assert redirected_response.status_code == 303
    assert redirected_response.headers["location"] == "/ui/login"


def test_admin_can_create_and_toggle_user(client):
    login_response = client.post("/ui/login", data={"user_id": "demo-admin", "password": "ChangeMe123!"}, follow_redirects=False)
    assert login_response.status_code == 303

    create_response = client.post(
        "/ui/admin/users",
        data={"user_id": "qa-user-001", "name": "QA User", "role": "employee", "temp_password": "TempPass123!"},
        follow_redirects=False,
    )
    assert create_response.status_code == 303

    admin_page = client.get("/ui/admin")
    assert admin_page.status_code == 200
    assert "qa-user-001" in admin_page.text

    deactivate_response = client.post("/ui/admin/users/qa-user-001/toggle-active", data={"is_active": "false"}, follow_redirects=False)
    assert deactivate_response.status_code == 303

    admin_page_after = client.get("/ui/admin")
    assert admin_page_after.status_code == 200
    assert "Activate" in admin_page_after.text

