from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session

from app.authorization import ALL_CATEGORIES, ROLE_CATEGORIES
from app.config import get_settings
from app.models import User
from tests.test_chat import add_chunk, login, prompt_text


@pytest.mark.parametrize("role,allowed", ROLE_CATEGORIES.items())
def test_every_role_retrieves_and_cites_only_allowed_categories(
    client: TestClient, qdrant: QdrantClient, llm, role: str, allowed: tuple[str, ...]
) -> None:
    for point_id, category in enumerate(ALL_CATEGORIES, start=100):
        add_chunk(qdrant, point_id, category, f"{category.upper()} EVIDENCE")
    login(client, role)
    response = client.post("/api/chat", json={"question": "policy"})
    assert response.status_code == 200
    citations = response.json()["citations"]
    assert citations and all(item["category"] in allowed for item in citations)
    prompt = prompt_text(llm)
    assert all(
        (f"{category.upper()} EVIDENCE" in prompt) == (category in allowed)
        for category in ALL_CATEGORIES
        if role != "admin" or category in {item["category"] for item in citations}
    )


@pytest.mark.parametrize(
    "role,forbidden",
    [(role, next(category for category in ALL_CATEGORIES if category not in allowed))
     for role, allowed in ROLE_CATEGORIES.items() if role != "admin"],
)
def test_inaccessible_evidence_refuses_before_generation(
    client: TestClient, qdrant: QdrantClient, llm, role: str, forbidden: str
) -> None:
    add_chunk(qdrant, 200, forbidden, "FORBIDDEN EVIDENCE")
    login(client, role)
    response = client.post("/api/chat", json={"question": "restricted policy"})
    assert response.json()["refused"] is True
    assert llm.calls == []


def test_request_role_and_jwt_role_claim_cannot_escalate(client: TestClient) -> None:
    login(client, "employee")
    assert client.post("/api/chat", json={"question": "policy", "role": "admin"}).status_code == 422
    settings = get_settings()
    token = jwt.encode(
        {"sub": "1", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS256",
    )
    client.cookies.set("access_token", token)
    assert client.get("/api/admin").status_code == 403


def test_database_role_change_controls_existing_session(client: TestClient, db: Session) -> None:
    login(client, "employee")
    user = db.get(User, 1)
    assert user is not None
    user.role = "admin"
    db.commit()
    assert client.get("/api/admin").status_code == 200


def test_explicit_unauthorized_department_refuses_before_generation(
    client: TestClient, qdrant: QdrantClient, llm
) -> None:
    add_chunk(qdrant, 300, "general", "Marketing is mentioned in this unrelated handbook text")
    login(client, "employee")
    response = client.post("/api/chat", json={"question": "What was the marketing ROI?"})
    assert response.status_code == 200 and response.json()["refused"] is True
    assert llm.calls == []


def test_inaccessible_employee_identifier_refuses_before_generation(
    client: TestClient, qdrant: QdrantClient, llm
) -> None:
    add_chunk(qdrant, 301, "marketing", "role: Marketing Manager")
    login(client, "marketing")
    response = client.post("/api/chat", json={"question": "What is FINEMP1000's role?"})
    assert response.status_code == 200 and response.json()["refused"] is True
    assert llm.calls == []
