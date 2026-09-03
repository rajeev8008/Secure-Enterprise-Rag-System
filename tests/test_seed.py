import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User
from app.seed import seed_demo_users


def settings(environment: str) -> Settings:
    return Settings(
        app_env=environment,
        secret_key="test-secret-key-that-is-at-least-32-characters",
        database_url="sqlite://",
    )


def test_seed_creates_six_users_once(db: Session) -> None:
    db.execute(User.__table__.delete())
    db.commit()
    assert seed_demo_users(db, settings("development")) == 6
    assert seed_demo_users(db, settings("development")) == 0
    assert db.scalar(select(func.count()).select_from(User)) == 6


def test_seed_is_blocked_outside_development(db: Session) -> None:
    with pytest.raises(RuntimeError, match="only be seeded in development"):
        seed_demo_users(db, settings("production"))
