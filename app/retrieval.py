from dataclasses import dataclass
import re
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from app.authorization import Category, categories_for_role
from app.config import Settings


@dataclass(frozen=True)
class RetrievedChunk:
    point_id: str
    text: str
    document_id: int
    filename: str
    category: Category
    section_or_row: str | int
    score: float
    chunk_index: int


CATEGORY_TERMS = {
    "hr": re.compile(r"\b(?:hr|human resources?)\b", re.IGNORECASE),
    "finance": re.compile(r"\bfinance(?: department|-only)?\b", re.IGNORECASE),
    "engineering": re.compile(r"\bengineering(?: department|-only)?\b", re.IGNORECASE),
    "marketing": re.compile(r"\bmarketing(?: department|-only)?\b", re.IGNORECASE),
}
STOP_WORDS = {"a", "an", "and", "by", "does", "for", "from", "how", "in", "is", "of", "the", "to", "was", "what", "when", "where", "who"}


def _terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2 and word not in STOP_WORDS}


def _authorized_filter(allowed: tuple[Category, ...]) -> Filter:
    return Filter(must=[FieldCondition(key="category", match=MatchAny(any=list(allowed)))])


def _explicit_category(question: str) -> str | None:
    return next((category for category, pattern in CATEGORY_TERMS.items() if pattern.search(question)), None)


def retrieve_authorized_chunks(
    client: QdrantClient,
    embeddings: Any,
    settings: Settings,
    question: str,
    role: str,
) -> list[RetrievedChunk]:
    allowed = categories_for_role(role)
    requested_category = _explicit_category(question)
    if requested_category and requested_category not in allowed:
        return []
    if not client.collection_exists(settings.qdrant_collection):
        return []
    authorized_filter = _authorized_filter(allowed)
    response = client.query_points(
        settings.qdrant_collection,
        query=embeddings.embed_query(question),
        query_filter=authorized_filter,
        limit=max(settings.retrieval_top_k, 20),
        with_payload=True,
    )
    candidates = {str(point.id): [point, point.score, 0.0] for point in response.points}
    query_terms = _terms(question)
    identifiers = set(re.findall(r"\bfinemp\d+\b", question.lower()))
    if len(query_terms) >= 2:
        offset = None
        while True:
            points, offset = client.scroll(
                settings.qdrant_collection,
                scroll_filter=authorized_filter,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                searchable = f"{payload.get('filename', '')} {payload.get('section_or_row', '')} {payload.get('text', '')}"
                if identifiers and not identifiers.issubset(_terms(searchable)):
                    continue
                lexical_score = len(query_terms & _terms(searchable)) / len(query_terms)
                previous = candidates.setdefault(str(point.id), [point, 0.0, 0.0])
                previous[2] = lexical_score
            if offset is None:
                break
    if identifiers:
        candidates = {
            point_id: candidate
            for point_id, candidate in candidates.items()
            if identifiers.issubset(_terms(str((candidate[0].payload or {}).get("text", ""))))
        }

    chunks = []
    for point, dense_score, lexical_score in candidates.values():
        if max(dense_score, lexical_score) < settings.retrieval_score_threshold:
            continue
        score = (dense_score + 3 * lexical_score) / 4 if len(query_terms) >= 2 else dense_score
        payload = point.payload or {}
        if payload.get("category") not in allowed:
            continue
        try:
            chunks.append(
                RetrievedChunk(
                    point_id=str(point.id),
                    text=str(payload["text"]),
                    document_id=int(payload["document_id"]),
                    filename=str(payload["filename"]),
                    category=payload["category"],
                    section_or_row=payload["section_or_row"],
                    score=score,
                    chunk_index=int(payload["chunk_index"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(chunks, key=lambda chunk: chunk.score, reverse=True)[: settings.retrieval_top_k]
