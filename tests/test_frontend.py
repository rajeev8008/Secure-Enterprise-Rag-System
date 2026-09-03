from fastapi.testclient import TestClient

from tests.test_chat import login


def test_home_page_redirects_to_login(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_is_public(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "Welcome back" in response.text


def test_chat_page_requires_login_and_shows_role(client: TestClient) -> None:
    assert client.get("/chat").status_code == 401
    login(client, "finance")
    response = client.get("/chat")
    assert response.status_code == 200
    assert "finance@example.com" in response.text
    assert "general, finance" in response.text


def test_monitoring_page_remains_admin_only(client: TestClient) -> None:
    login(client, "employee")
    assert client.get("/admin/monitoring").status_code == 403
    login(client, "admin")
    assert client.get("/admin/monitoring").status_code == 200


def test_frontend_does_not_store_credentials_in_browser_storage(client: TestClient) -> None:
    for path in ("/login",):
        text = client.get(path).text.lower()
        assert "localstorage" not in text and "sessionstorage" not in text
