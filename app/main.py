from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.auth import authenticate_user, create_access_token, get_current_user, require_admin
from app.database import get_db
from app.chat import router as chat_router
from app.monitoring_routes import router as monitoring_router
from app.frontend import router as frontend_router
from app.documents import router as documents_router
from app.models import User
from app.schemas import LoginRequest, UserResponse

app = FastAPI(title="Secure Enterprise RAG Assistant")
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(monitoring_router)
app.include_router(frontend_router)


@app.post("/auth/login", response_model=UserResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = authenticate_user(db, credentials.email, credentials.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    response.set_cookie(
        "access_token",
        create_access_token(user.id, settings),
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return user


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie("access_token", httponly=True, samesite="lax")


@app.get("/auth/me", response_model=UserResponse)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@app.get("/api/admin", response_model=UserResponse)
def admin_only(user: Annotated[User, Depends(require_admin)]) -> User:
    return user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    checks = {"database": "ok", "qdrant": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        checks["database"] = "unavailable"

    try:
        from app.qdrant import get_qdrant_client

        get_qdrant_client().get_collections()
    except Exception:
        checks["qdrant"] = "unavailable"

    if "unavailable" in checks.values():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks
