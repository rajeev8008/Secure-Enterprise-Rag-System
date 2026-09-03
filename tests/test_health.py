import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient

from app.main import app


def test_liveness() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

