from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.config import get_settings


def login(client: TestClient, role: str, password: str = "DemoPass123!"):
    return client.post("/auth/login", json={"email": f"{role}@example.com", "password": password})


def test_valid_login_sets_secure_cookie_and_current_user(client: TestClient) -> None:
    response = login(client, "employee")
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/auth/me").json()["role"] == "employee"


def test_invalid_login(client: TestClient) -> None:
    assert login(client, "employee", "wrong-password").status_code == 401
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_client_supplied_role(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={
            "email": "employee@example.com",
            "password": "DemoPass123!",
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_unauthenticated_access(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_invalid_and_expired_jwt(client: TestClient) -> None:
    client.cookies.set("access_token", "not-a-jwt")
    assert client.get("/auth/me").status_code == 401

    expired = create_access_token(1, get_settings(), timedelta(seconds=-1))
    client.cookies.set("access_token", expired)
    assert client.get("/auth/me").status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    login(client, "employee")
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_employee_blocked_from_admin_route(client: TestClient) -> None:
    login(client, "employee")
    assert client.get("/api/admin").status_code == 403


def test_admin_allowed_into_admin_route(client: TestClient) -> None:
    login(client, "admin")
    response = client.get("/api/admin")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
