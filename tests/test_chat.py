from typing import Any
import json

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.config import get_settings
from app.qdrant import ensure_collection
from app.retrieval import retrieve_authorized_chunks


def login(client: TestClient, role: str) -> None:
    response = client.post(
        "/auth/login",
        json={"email": f"{role}@example.com", "password": "DemoPass123!"},
    )
    assert response.status_code == 200


def add_chunk(qdrant: QdrantClient, point_id: int, category: str, text: str) -> None:
    settings = get_settings()
    ensure_collection(qdrant, settings)
    qdrant.upsert(
        settings.qdrant_collection,
        points=[
            PointStruct(
                id=point_id,
                vector=[1.0] + [0.0] * 383,
                payload={
                    "text": text,
                    "document_id": point_id,
                    "filename": f"{category}.md",
                    "category": category,
                    "section_or_row": "Policy",
                    "chunk_index": 0,
                },
            )
        ],
        wait=True,
    )


def prompt_text(llm: Any) -> str:
    return str(llm.calls[0])


def test_chat_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/chat", json={"question": "What is the policy?"}).status_code == 401
    assert client.post("/api/chat/stream", json={"question": "What is the policy?"}).status_code == 401


def test_chat_streams_answer_and_citations(
    client: TestClient, qdrant: QdrantClient, llm
) -> None:
    add_chunk(qdrant, 1, "general", "PUBLIC POLICY")
    login(client, "employee")

    with client.stream("POST", "/api/chat/stream", json={"question": "What is the policy?"}) as response:
        events = [json.loads(line) for line in response.iter_lines()]

    assert response.status_code == 200
    assert "".join(event.get("content", "") for event in events).strip() == "A grounded answer."
    assert events[-1]["type"] == "done"
    assert events[-1]["citations"][0]["category"] == "general"
    assert events[-1]["refused"] is False


def test_employee_prompt_contains_only_general_context(
    client: TestClient, qdrant: QdrantClient, llm
) -> None:
    add_chunk(qdrant, 1, "general", "PUBLIC POLICY")
    add_chunk(qdrant, 2, "finance", "PRIVATE FINANCE DATA")
    login(client, "employee")
    response = client.post("/api/chat", json={"question": "What is the policy?"})
    assert response.status_code == 200
    assert response.json() == {
        "answer": "A grounded answer.",
        "citations": [{"document_id": 1, "filename": "general.md", "category": "general", "section_or_row": "Policy", "score": 1.0}],
        "refused": False,
        "blocked": False,
        "guardrail_reason": None,
    }
    assert "PUBLIC POLICY" in prompt_text(llm)
    assert "PRIVATE FINANCE DATA" not in prompt_text(llm)


def test_finance_retrieval_allows_general_and_finance(
    qdrant: QdrantClient, embeddings
) -> None:
    add_chunk(qdrant, 1, "general", "PUBLIC POLICY")
    add_chunk(qdrant, 2, "finance", "FINANCE POLICY")
    add_chunk(qdrant, 3, "hr", "HR POLICY")
    chunks = retrieve_authorized_chunks(
        qdrant, embeddings, get_settings(), "policy", "finance"
    )
    assert {chunk.category for chunk in chunks} == {"general", "finance"}


def test_weak_retrieval_refuses_without_calling_llm(
    client: TestClient, qdrant: QdrantClient, llm
) -> None:
    settings = get_settings()
    ensure_collection(qdrant, settings)
    qdrant.upsert(
        settings.qdrant_collection,
        points=[
            PointStruct(
                id=1,
                vector=[0.0, 1.0] + [0.0] * 382,
                payload={
                    "text": "Unrelated",
                    "document_id": 1,
                    "filename": "general.md",
                    "category": "general",
                    "section_or_row": "Other",
                    "chunk_index": 0,
                },
            )
        ],
        wait=True,
    )
    login(client, "employee")
    response = client.post("/api/chat", json={"question": "Unknown topic"})
    assert response.status_code == 200
    assert response.json()["refused"] is True
    assert response.json()["guardrail_reason"] == "insufficient_context"
    assert response.json()["citations"] == []
    assert llm.calls == []


def test_authorized_lexical_identifier_ranks_the_exact_csv_row_first(
    qdrant: QdrantClient, embeddings
) -> None:
    settings = get_settings().model_copy(update={"retrieval_score_threshold": 0.4})
    ensure_collection(qdrant, settings)
    qdrant.upsert(
        settings.qdrant_collection,
        points=[
            PointStruct(id=40, vector=[1.0] + [0.0] * 383, payload={"text": "employee_id: FINEMP9999\nrole: Manager", "document_id": 1, "filename": "hr_data.csv", "category": "hr", "section_or_row": 3, "chunk_index": 1}),
            PointStruct(id=41, vector=[0.0, 1.0] + [0.0] * 382, payload={"text": "employee_id: FINEMP1000\nrole: Sales Manager", "document_id": 1, "filename": "hr_data.csv", "category": "hr", "section_or_row": 2, "chunk_index": 0}),
        ],
        wait=True,
    )
    chunks = retrieve_authorized_chunks(qdrant, embeddings, settings, "What is FINEMP1000's role?", "admin")
    assert chunks[0].section_or_row == 2
