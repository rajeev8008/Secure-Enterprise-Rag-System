from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.authorization import ROLE_CATEGORIES
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import User

DEMO_PASSWORD = "DemoPass123!"


def seed_demo_users(db: Session, settings: Settings) -> int:
    if settings.app_env != "development":
        raise RuntimeError("Demo users may only be seeded in development")

    existing = set(db.scalars(select(User.email).where(User.email.in_(
        f"{role}@example.com" for role in ROLE_CATEGORIES
    ))))
    users = [
        User(email=f"{role}@example.com", password_hash=hash_password(DEMO_PASSWORD), role=role)
        for role in ROLE_CATEGORIES
        if f"{role}@example.com" not in existing
    ]
    db.add_all(users)
    db.commit()
    return len(users)


if __name__ == "__main__":
    with SessionLocal() as session:
        print(f"Created {seed_demo_users(session, get_settings())} demo users")

