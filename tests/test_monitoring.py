from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ChatRequestLog
from tests.test_chat import login


def add_logs(db: Session) -> None:
    db.add_all(
        [
            ChatRequestLog(
                user_id=1,
                user_role="employee",
                latency_ms=10,
                input_tokens=20,
                output_tokens=5,
                retrieved_document_ids=[1],
                was_blocked=False,
                was_refused=False,
            ),
            ChatRequestLog(
                user_id=1,
                user_role="employee",
                latency_ms=30,
                input_tokens=None,
                output_tokens=None,
                retrieved_document_ids=[],
                was_blocked=True,
                was_refused=True,
                guardrail_reason="prompt_injection",
            ),
        ]
    )
    db.commit()


def test_monitoring_is_admin_only(client: TestClient) -> None:
    login(client, "employee")
    assert client.get("/api/monitoring/summary").status_code == 403
    assert client.get("/admin/monitoring").status_code == 403


def test_admin_monitoring_summary_and_page(client: TestClient, db: Session) -> None:
    add_logs(db)
    login(client, "admin")
    response = client.get("/api/monitoring/summary")
    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 2,
        "successful_responses": 1,
        "average_latency_ms": 20.0,
        "input_tokens": 20,
        "output_tokens": 5,
        "refusals": 1,
        "blocked_requests": 1,
    }
    page = client.get("/admin/monitoring")
    assert page.status_code == 200
    assert "Request monitoring" in page.text and "20.0 ms" in page.text
