from fastapi.testclient import TestClient


def login(client: TestClient, role: str) -> None:
    response = client.post(
        "/auth/login",
        json={"email": f"{role}@example.com", "password": "DemoPass123!"},
    )
    assert response.status_code == 200


def test_document_endpoints_are_admin_only(client: TestClient) -> None:
    login(client, "employee")
    assert client.get("/api/documents").status_code == 403
    assert client.post("/api/documents/bootstrap").status_code == 403
    assert client.post(
        "/api/documents",
        data={"category": "general"},
        files={"file": ("policy.md", b"# Policy\nText", "text/markdown")},
    ).status_code == 403


def test_admin_can_upload_list_and_get_duplicate_response(client: TestClient) -> None:
    login(client, "admin")
    upload = lambda: client.post(
        "/api/documents",
        data={"category": "general"},
        files={"file": ("policy.md", b"# Policy\nText", "text/markdown")},
    )
    response = upload()
    assert response.status_code == 201
    assert response.json()["status"] == "INDEXED"
    documents = client.get("/api/documents")
    assert documents.status_code == 200 and len(documents.json()) == 1
    duplicate = upload()
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "This file has already been ingested"


def test_admin_upload_validates_extension_empty_file_and_category(client: TestClient) -> None:
    login(client, "admin")
    for filename, content, category in [
        ("notes.txt", b"text", "general"),
        ("empty.md", b"", "general"),
        ("policy.md", b"text", "sales"),
    ]:
        response = client.post(
            "/api/documents",
            data={"category": category},
            files={"file": (filename, content, "application/octet-stream")},
        )
        assert response.status_code == 400
