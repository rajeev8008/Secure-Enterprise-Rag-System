import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.ingestion import (
    DuplicateDocument,
    IngestionFailed,
    InvalidDocument,
    bootstrap_dataset,
    get_embeddings,
    ingest_path,
)
from app.models import Document, User
from app.qdrant import get_qdrant_client
from app.schemas import BootstrapResponse, DocumentResponse

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BootstrapResponse:
    try:
        indexed, skipped, chunks = bootstrap_dataset(db, client, embeddings, settings, admin.id)
    except IngestionFailed as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return BootstrapResponse(indexed_files=indexed, skipped_files=skipped, indexed_chunks=chunks)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    category: Annotated[str, Form()],
) -> Document:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    temporary_path: str | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(content)
            temporary_path = temporary.name
        return ingest_path(
            db,
            client,
            embeddings,
            settings,
            Path(temporary_path),
            category,
            admin.id,
            filename,
            filename,
        )
    except DuplicateDocument as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InvalidDocument as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except IngestionFailed as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    finally:
        if temporary_path:
            os.unlink(temporary_path)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc(), Document.id.desc())))
