from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.authorization import Role


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    category: str
    checksum: str
    status: str
    chunk_count: int
    uploaded_by: int
    created_at: datetime
    updated_at: datetime


class BootstrapResponse(BaseModel):
    indexed_files: int
    skipped_files: int
    indexed_chunks: dict[str, int]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


class Citation(BaseModel):
    document_id: int
    filename: str
    category: str
    section_or_row: str | int
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    blocked: bool
    guardrail_reason: str | None


class MonitoringSummary(BaseModel):
    total_requests: int
    successful_responses: int
    average_latency_ms: float
    input_tokens: int
    output_tokens: int
    refusals: int
    blocked_requests: int


class RecentRequest(BaseModel):
    created_at: datetime
    user_role: str
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    was_refused: bool
    was_blocked: bool
    reason: str | None
