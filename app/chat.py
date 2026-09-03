from dataclasses import replace
import json
from typing import Annotated, Any
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from qdrant_client import QdrantClient

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.generation import generate_grounded_answer, get_llm, stream_grounded_answer
from app.guardrails import prompt_injection_reason, redact_pii
from app.ingestion import get_embeddings
from app.models import User
from app.database import get_db
from app.monitoring import record_chat_request
from app.qdrant import get_qdrant_client
from app.retrieval import retrieve_authorized_chunks
from app.schemas import ChatRequest, ChatResponse, Citation
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/chat", tags=["chat"])
REFUSAL = "I could not find sufficient information in the documents available to you."


def _citations(chunks: list) -> list[Citation]:
    return list(
        {
            (chunk.document_id, chunk.filename, str(chunk.section_or_row)): Citation(
                document_id=chunk.document_id,
                filename=chunk.filename,
                category=chunk.category,
                section_or_row=chunk.section_or_row,
                score=round(chunk.score, 4),
            )
            for chunk in chunks
        }.values()
    )


def _event(event_type: str, **data: Any) -> bytes:
    return (json.dumps({"type": event_type, **data}) + "\n").encode()


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    llm: Annotated[Any, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    started = perf_counter()
    reason = prompt_injection_reason(request.question)
    if reason:
        record_chat_request(
            db, user, (perf_counter() - started) * 1000, [], blocked=True, refused=True, reason=reason
        )
        return ChatResponse(
            answer="I cannot process that request.",
            citations=[],
            refused=True,
            blocked=True,
            guardrail_reason=reason,
        )

    chunks = []
    try:
        safe_question = redact_pii(request.question)
        chunks = retrieve_authorized_chunks(
            client, embeddings, settings, safe_question, user.role
        )
        if not chunks:
            record_chat_request(
                db,
                user,
                (perf_counter() - started) * 1000,
                [],
                refused=True,
                reason="insufficient_context",
            )
            return ChatResponse(
                answer=REFUSAL,
                citations=[],
                refused=True,
                blocked=False,
                guardrail_reason="insufficient_context",
            )
        safe_chunks = [replace(chunk, text=redact_pii(chunk.text)) for chunk in chunks]
        generation = generate_grounded_answer(safe_question, safe_chunks, llm)
    except Exception as exc:
        record_chat_request(
            db, user, (perf_counter() - started) * 1000, chunks, refused=True, reason="service_error"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable",
        ) from exc

    citations = _citations(chunks)
    record_chat_request(
        db,
        user,
        (perf_counter() - started) * 1000,
        chunks,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
    )
    return ChatResponse(
        answer=redact_pii(generation.answer),
        citations=citations,
        refused=False,
        blocked=False,
        guardrail_reason=None,
    )


@router.post("/stream")
def stream_chat(
    request: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    llm: Annotated[Any, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    started = perf_counter()
    reason = prompt_injection_reason(request.question)
    if reason:
        record_chat_request(
            db, user, (perf_counter() - started) * 1000, [], blocked=True, refused=True, reason=reason
        )
        events = [
            _event("token", content="I cannot process that request."),
            _event("done", citations=[], refused=True, blocked=True, guardrail_reason=reason),
        ]
        return StreamingResponse(iter(events), media_type="application/x-ndjson")

    chunks = []
    try:
        safe_question = redact_pii(request.question)
        chunks = retrieve_authorized_chunks(client, embeddings, settings, safe_question, user.role)
    except Exception as exc:
        record_chat_request(
            db, user, (perf_counter() - started) * 1000, chunks, refused=True, reason="service_error"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable",
        ) from exc

    if not chunks:
        record_chat_request(
            db, user, (perf_counter() - started) * 1000, [], refused=True, reason="insufficient_context"
        )
        events = [
            _event("token", content=REFUSAL),
            _event(
                "done",
                citations=[],
                refused=True,
                blocked=False,
                guardrail_reason="insufficient_context",
            ),
        ]
        return StreamingResponse(iter(events), media_type="application/x-ndjson")

    safe_chunks = [replace(chunk, text=redact_pii(chunk.text)) for chunk in chunks]
    citations = [citation.model_dump() for citation in _citations(chunks)]

    def events():
        try:
            for content in stream_grounded_answer(safe_question, safe_chunks, llm):
                yield _event("token", content=content)
            record_chat_request(db, user, (perf_counter() - started) * 1000, chunks)
            yield _event(
                "done",
                citations=citations,
                refused=False,
                blocked=False,
                guardrail_reason=None,
            )
        except Exception:
            record_chat_request(
                db, user, (perf_counter() - started) * 1000, chunks, refused=True, reason="service_error"
            )
            yield _event("error", message="The answer service is temporarily unavailable.")

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
