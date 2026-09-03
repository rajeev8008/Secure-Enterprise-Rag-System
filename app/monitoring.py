from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import ChatRequestLog, User
from app.retrieval import RetrievedChunk
from app.schemas import MonitoringSummary


def record_chat_request(
    db: Session,
    user: User,
    latency_ms: float,
    chunks: list[RetrievedChunk],
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    blocked: bool = False,
    refused: bool = False,
    reason: str | None = None,
) -> None:
    db.add(
        ChatRequestLog(
            user_id=user.id,
            user_role=user.role,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retrieved_document_ids=sorted({chunk.document_id for chunk in chunks}),
            was_blocked=blocked,
            was_refused=refused,
            guardrail_reason=reason,
        )
    )
    db.commit()


def monitoring_summary(db: Session) -> MonitoringSummary:
    row = db.execute(
        select(
            func.count(ChatRequestLog.id),
            func.coalesce(func.avg(ChatRequestLog.latency_ms), 0.0),
            func.coalesce(func.sum(ChatRequestLog.input_tokens), 0),
            func.coalesce(func.sum(ChatRequestLog.output_tokens), 0),
            func.coalesce(func.sum(case((ChatRequestLog.was_refused, 1), else_=0)), 0),
            func.coalesce(func.sum(case((ChatRequestLog.was_blocked, 1), else_=0)), 0),
            func.coalesce(func.sum(case((~ChatRequestLog.was_refused, 1), else_=0)), 0),
        )
    ).one()
    return MonitoringSummary(
        total_requests=row[0],
        successful_responses=row[6],
        average_latency_ms=round(float(row[1]), 2),
        input_tokens=row[2],
        output_tokens=row[3],
        refusals=row[4],
        blocked_requests=row[5],
    )
