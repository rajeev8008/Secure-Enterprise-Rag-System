from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=60, gt=0)
    database_url: str
    qdrant_url: str | None = None
    qdrant_path: str = "./qdrant_data"
    qdrant_api_key: str | None = None
    qdrant_collection: str = Field(
        default="company_documents",
        validation_alias=AliasChoices("QDRANT_COLLECTION_NAME", "QDRANT_COLLECTION"),
    )
    groq_api_key: str | None = None
    llm_model: str | None = Field(
        default=None, validation_alias=AliasChoices("GROQ_MODEL", "LLM_MODEL")
    )
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retrieval_top_k: int = Field(default=4, gt=0)
    retrieval_score_threshold: float = Field(default=0.4, ge=0, le=1)
    max_upload_size_mb: int = Field(default=10, gt=0)
    chunk_size: int = Field(default=800, gt=0)
    chunk_overlap: int = Field(default=100, ge=0)
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, gt=0, le=65535)

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
