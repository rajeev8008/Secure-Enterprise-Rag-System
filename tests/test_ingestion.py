from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.ingestion import (
    DATASET_ROOT,
    DuplicateDocument,
    IngestionFailed,
    InvalidDocument,
    bootstrap_dataset,
    category_from_dataset,
    ingest_path,
    load_chunks,
    point_id,
)
from app.models import Document, User
from app.qdrant import ensure_collection


def make_settings(**changes: object) -> Settings:
    values = {
        "app_env": "development",
        "secret_key": "test-secret-key-that-is-at-least-32-characters",
        "database_url": "sqlite://",
        "qdrant_url": ":memory:",
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def admin_id(db: Session) -> int:
    return db.scalar(select(User.id).where(User.role == "admin"))  # type: ignore[return-value]


def test_markdown_loading_preserves_nearest_heading(work_path: Path) -> None:
    path = work_path / "heading-policy.md"
    path.write_text("# Benefits\nHealth coverage details.\n\n## Leave\nAnnual leave details.", encoding="utf-8")
    chunks = load_chunks(path, make_settings(chunk_size=40, chunk_overlap=5))
    assert {chunk.metadata["section_or_row"] for chunk in chunks} == {"Benefits", "Leave"}
    assert all(chunk.page_content for chunk in chunks)
    assert chunks[0].page_content.startswith("# Benefits\n\n")


def test_markdown_has_no_blank_or_heading_only_chunks() -> None:
    chunks = [
        chunk
        for path in DATASET_ROOT.rglob("*.md")
        for chunk in load_chunks(path, make_settings())
    ]
    assert chunks
    assert all(chunk.page_content.strip() for chunk in chunks)
    assert all(len(chunk.page_content) <= 800 for chunk in chunks)
    assert all(chunk.metadata.get("section_or_row") for chunk in chunks)
    assert not any(
        all(line.strip().startswith("#") for line in chunk.page_content.splitlines() if line.strip())
        for chunk in chunks
    )


def test_markdown_continuation_chunks_keep_heading_context(work_path: Path) -> None:
    path = work_path / "long-section.md"
    path.write_text("## Long Section\n" + "useful content " * 200, encoding="utf-8")
    chunks = load_chunks(path, make_settings())
    assert len(chunks) > 1
    assert all(chunk.metadata["section_or_row"] == "Long Section" for chunk in chunks)
    assert all(chunk.page_content.startswith("## Long Section\n\n") for chunk in chunks)


def test_csv_loader_returns_one_document_per_row(work_path: Path) -> None:
    path = work_path / "hr_data.csv"
    path.write_text("name,team\nAna,HR\nBo,Finance\n", encoding="utf-8")
    rows = load_chunks(path, make_settings())
    assert len(rows) == 2
    assert [row.metadata["section_or_row"] for row in rows] == [2, 3]


def test_finsolve_csv_has_exactly_100_unsplit_rows() -> None:
    rows = load_chunks(DATASET_ROOT / "hr" / "hr_data.csv", make_settings())
    assert len(rows) == 100
    assert [row.metadata["section_or_row"] for row in rows] == list(range(2, 102))


def test_category_is_derived_from_trusted_folder(work_path: Path) -> None:
    assert category_from_dataset(DATASET_ROOT / "engineering" / "engineering_master_doc.md") == "engineering"
    outside = work_path / "finance" / "fake.md"
    outside.parent.mkdir(exist_ok=True)
    outside.write_text("data", encoding="utf-8")
    with pytest.raises(InvalidDocument, match="outside"):
        category_from_dataset(outside)


@pytest.mark.parametrize(("filename", "content", "message"), [
    ("notes.txt", b"hello", "Only Markdown and CSV"),
    ("empty.md", b"  \n", "empty"),
])
def test_invalid_files_are_rejected(work_path: Path, filename: str, content: bytes, message: str) -> None:
    path = work_path / filename
    path.write_bytes(content)
    with pytest.raises(InvalidDocument, match=message):
        load_chunks(path, make_settings())


def test_file_size_limit_is_enforced(work_path: Path) -> None:
    path = work_path / "large.md"
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(InvalidDocument, match="exceeds 1 MB"):
        load_chunks(path, make_settings(max_upload_size_mb=1))


def test_point_ids_are_deterministic() -> None:
    assert point_id("abc", 2) == point_id("abc", 2)
    assert point_id("abc", 2) != point_id("abc", 3)


def test_ingestion_metadata_duplicate_and_deterministic_ids(
    work_path: Path,
    db: Session,
    qdrant: QdrantClient,
    embeddings,
) -> None:
    path = work_path / "metadata-policy.md"
    path.write_text("# Policy\nCompany policy text.", encoding="utf-8")
    settings = make_settings()
    record = ingest_path(db, qdrant, embeddings, settings, path, "general", admin_id(db), "general/policy.md")
    points, _ = qdrant.scroll(settings.qdrant_collection, limit=100, with_payload=True)
    assert record.status == "INDEXED" and record.chunk_count == 1
    assert str(points[0].id) == point_id(record.checksum, 0)
    assert set(points[0].payload or {}) >= {
        "text", "document_id", "filename", "category", "source_path",
        "chunk_index", "section_or_row", "checksum",
    }
    with pytest.raises(DuplicateDocument, match="already"):
        ingest_path(db, qdrant, embeddings, settings, path, "general", admin_id(db), "general/policy.md")


@pytest.mark.integration
def test_finsolve_bootstrap_is_idempotent_and_categorized(
    db: Session,
    qdrant: QdrantClient,
    embeddings,
) -> None:
    settings = make_settings()
    first = bootstrap_dataset(db, qdrant, embeddings, settings, admin_id(db))
    second = bootstrap_dataset(db, qdrant, embeddings, settings, admin_id(db))
    points, _ = qdrant.scroll(settings.qdrant_collection, limit=1000, with_payload=True)
    assert first[0] == 10 and first[1] == 0
    assert second == (0, 10, {category: 0 for category in first[2]})
    assert db.scalar(select(func.count()).select_from(Document)) == 10
    assert len(points) == sum(first[2].values())
    assert all((point.payload or {}).get("category") in first[2] for point in points)


@pytest.mark.integration
def test_bootstrap_repairs_missing_qdrant_points_without_duplicate_rows(
    db: Session, qdrant: QdrantClient, embeddings
) -> None:
    settings = make_settings()
    bootstrap_dataset(db, qdrant, embeddings, settings, admin_id(db))
    qdrant.delete_collection(settings.qdrant_collection)
    repaired = bootstrap_dataset(db, qdrant, embeddings, settings, admin_id(db))
    assert repaired[0:2] == (10, 0)
    assert db.scalar(select(func.count()).select_from(Document)) == 10
    assert qdrant.count(settings.qdrant_collection, exact=True).count == sum(repaired[2].values())


class FailingQdrant:
    def collection_exists(self, _: str) -> bool:
        return True

    def upsert(self, *args, **kwargs) -> None:
        raise RuntimeError("Qdrant unavailable")


def test_qdrant_failure_marks_document_failed(work_path: Path, db: Session, embeddings) -> None:
    path = work_path / "failure-policy.md"
    path.write_text("# Policy\nCompany policy text.", encoding="utf-8")
    with pytest.raises(IngestionFailed, match="Failed to index"):
        ingest_path(
            db,
            FailingQdrant(),  # type: ignore[arg-type]
            embeddings,
            make_settings(),
            path,
            "general",
            admin_id(db),
            "policy.md",
        )
    record = db.scalar(select(Document))
    assert record is not None and record.status == "FAILED" and record.chunk_count == 0
