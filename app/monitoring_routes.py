from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import ChatRequestLog, User
from app.monitoring import monitoring_summary
from app.schemas import MonitoringSummary, RecentRequest
from sqlalchemy import select

router = APIRouter(tags=["monitoring"])
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/api/monitoring/summary", response_model=MonitoringSummary)
def summary(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> MonitoringSummary:
    return monitoring_summary(db)


@router.get("/admin/monitoring", response_class=HTMLResponse)
def dashboard(
    request: Request,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    recent = [
        RecentRequest(
            created_at=item.created_at,
            user_role=item.user_role,
            latency_ms=round(item.latency_ms, 2),
            input_tokens=item.input_tokens,
            output_tokens=item.output_tokens,
            was_refused=item.was_refused,
            was_blocked=item.was_blocked,
            reason=item.guardrail_reason,
        )
        for item in db.scalars(select(ChatRequestLog).order_by(ChatRequestLog.id.desc()).limit(20))
    ]
    return templates.TemplateResponse(
        request=request,
        name="monitoring.html",
        context={"summary": monitoring_summary(db), "recent": recent},
    )
