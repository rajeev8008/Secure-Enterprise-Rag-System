import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain_community.document_loaders import CSVLoader, TextLoader
from langchain_core.documents import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authorization import ALL_CATEGORIES, Category
from app.config import Settings
from app.models import Document
from app.qdrant import ensure_collection

ALLOWED_EXTENSIONS = {".md", ".csv"}
DATASET_ROOT = Path(__file__).resolve().parent.parent / "sample_data" / "finsolve"
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


class InvalidDocument(ValueError):
    pass


class DuplicateDocument(ValueError):
    pass


class IngestionFailed(RuntimeError):
    pass


@lru_cache
def get_embeddings() -> Any:
    from app.config import get_settings
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=get_settings().embedding_model)


def validate_category(category: str) -> Category:
    normalized = category.strip().lower()
    if normalized not in ALL_CATEGORIES:
        raise InvalidDocument("Unsupported document category")
    return normalized  # type: ignore[return-value]


def category_from_dataset(path: Path, root: Path = DATASET_ROOT) -> Category:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise InvalidDocument("Dataset file is outside the trusted dataset directory") from exc
    if len(relative.parts) != 2:
        raise InvalidDocument("Dataset files must be inside one category directory")
    return validate_category(relative.parts[0])


def checksum_for(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def point_id(checksum: str, chunk_index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"{checksum}:{chunk_index}"))


def _markdown_sections(text: str) -> list[tuple[str, str, str]]:
    matches = list(HEADING.finditer(text))
    if not matches:
        return [("Document", "", text)]
    sections: list[tuple[str, str, str]] = []
    if text[: matches[0].start()].strip():
        sections.append(("Document", "", text[: matches[0].start()]))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if body:
            sections.append((match.group(1).strip(), match.group(0).strip(), body))
    return sections


def load_chunks(path: Path, settings: Settings) -> list[LangChainDocument]:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise InvalidDocument("Only Markdown and CSV files are supported")
    content = path.read_bytes()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise InvalidDocument(f"File exceeds {settings.max_upload_size_mb} MB limit")
    if not content.strip():
        raise InvalidDocument("File is empty")

    if suffix == ".csv":
        rows = CSVLoader(str(path), encoding="utf-8").load()
        if not rows:
            raise InvalidDocument("CSV contains no data rows")
        for row_number, row in enumerate(rows, start=2):
            row.metadata = {"section_or_row": row_number}
        return rows

    text = TextLoader(str(path), encoding="utf-8").load()[0].page_content
    documents = []
    for heading, heading_text, body in _markdown_sections(text):
        prefix = f"{heading_text}\n\n" if heading_text else ""
        body_size = max(settings.chunk_overlap + 1, settings.chunk_size - len(prefix))
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=body_size,
            chunk_overlap=settings.chunk_overlap,
        )
        documents.extend(
            LangChainDocument(
                page_content=f"{prefix}{chunk}",
                metadata={"section_or_row": heading},
            )
            for chunk in splitter.split_text(body)
            if chunk.strip()
        )
    return documents


def ingest_path(
    db: Session,
    client: QdrantClient,
    embeddings: Any,
    settings: Settings,
    path: Path,
    category: str,
    uploaded_by: int,
    source_path: str,
    filename: str | None = None,
) -> Document:
    validated_category = validate_category(category)
    content = path.read_bytes()
    chunks = load_chunks(path, settings)
    checksum = checksum_for(content)
    if db.scalar(select(Document.id).where(Document.checksum == checksum)) is not None:
        raise DuplicateDocument("This file has already been ingested")
    record = Document(
        filename=filename or path.name,
        category=validated_category,
        checksum=checksum,
        status="PENDING",
        chunk_count=0,
        uploaded_by=uploaded_by,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return _index_record(db, client, embeddings, settings, record, chunks, source_path)


def _index_record(
    db: Session,
    client: QdrantClient,
    embeddings: Any,
    settings: Settings,
    record: Document,
    chunks: list[LangChainDocument],
    source_path: str,
) -> Document:
    try:
        texts = [chunk.page_content for chunk in chunks]
        vectors = embeddings.embed_documents(texts)
        ensure_collection(client, settings)
        points = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            metadata = {
                "document_id": record.id,
                "filename": record.filename,
                "category": record.category,
                "source_path": source_path,
                "chunk_index": index,
                "section_or_row": chunk.metadata["section_or_row"],
                "checksum": record.checksum,
            }
            points.append(
                PointStruct(
                    id=point_id(record.checksum, index),
                    vector=vector,
                    payload={"text": chunk.page_content, **metadata},
                )
            )
        client.upsert(settings.qdrant_collection, points=points, wait=True)
        record.status = "INDEXED"
        record.chunk_count = len(points)
        db.commit()
        db.refresh(record)
        return record
    except Exception as exc:
        record.status = "FAILED"
        db.commit()
        raise IngestionFailed(f"Failed to index {record.filename}") from exc


def bootstrap_dataset(
    db: Session,
    client: QdrantClient,
    embeddings: Any,
    settings: Settings,
    uploaded_by: int,
) -> tuple[int, int, dict[str, int]]:
    indexed = skipped = 0
    chunk_counts = {category: 0 for category in ALL_CATEGORIES}
    paths = sorted(path for path in DATASET_ROOT.rglob("*") if path.suffix.lower() in ALLOWED_EXTENSIONS)
    for path in paths:
        category = category_from_dataset(path)
        checksum = checksum_for(path.read_bytes())
        existing = db.scalar(select(Document).where(Document.checksum == checksum))
        if existing is not None:
            ensure_collection(client, settings)
            stored = client.count(
                settings.qdrant_collection,
                count_filter=Filter(
                    must=[FieldCondition(key="checksum", match=MatchValue(value=checksum))]
                ),
                exact=True,
            ).count
            if existing.status == "INDEXED" and stored == existing.chunk_count:
                skipped += 1
                continue
            chunks = load_chunks(path, settings)
            existing.status = "PENDING"
            db.commit()
            record = _index_record(
                db,
                client,
                embeddings,
                settings,
                existing,
                chunks,
                path.relative_to(DATASET_ROOT).as_posix(),
            )
            indexed += 1
            chunk_counts[category] += record.chunk_count
            continue
        try:
            record = ingest_path(
                db,
                client,
                embeddings,
                settings,
                path,
                category,
                uploaded_by,
                path.relative_to(DATASET_ROOT).as_posix(),
            )
        except DuplicateDocument:
            skipped += 1
            continue
        indexed += 1
        chunk_counts[category] += record.chunk_count
    return indexed, skipped, chunk_counts
