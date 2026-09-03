import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from qdrant_client import QdrantClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.auth import hash_password
from app.authorization import ROLE_CATEGORIES
from app.database import Base, get_db
from app.generation import get_llm
from app.ingestion import get_embeddings
from app.main import app
from app.models import User
from app.qdrant import get_qdrant_client


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 383 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 383


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.content = "A grounded answer."
        self.usage_metadata = {"input_tokens": 20, "output_tokens": 5}

    def invoke(self, messages: object):
        from types import SimpleNamespace

        self.calls.append(messages)
        return SimpleNamespace(content=self.content, usage_metadata=self.usage_metadata)


@pytest.fixture
def work_path() -> Path:
    path = Path(".test-tmp")
    path.mkdir(exist_ok=True)
    return path


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    for role in ROLE_CATEGORIES:
        session.add(User(email=f"{role}@example.com", password_hash=hash_password("DemoPass123!"), role=role))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def qdrant() -> QdrantClient:
    return QdrantClient(location=":memory:")


@pytest.fixture
def embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(db: Session, qdrant: QdrantClient, embeddings: FakeEmbeddings, llm: FakeLLM) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_qdrant_client] = lambda: qdrant
    app.dependency_overrides[get_embeddings] = lambda: embeddings
    app.dependency_overrides[get_llm] = lambda: llm
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
