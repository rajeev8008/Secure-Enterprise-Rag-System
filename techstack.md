# Technology Stack

## Framework decision

Use **LangChain**, not LangGraph.

LangChain provides everything required here:

- document loaders;
- text splitting;
- embedding integration;
- Qdrant retrieval;
- prompt construction;
- LLM integration.

LangGraph is designed for stateful, branching, cyclic, or agent-based workflows. This project uses a direct request pipeline, so adding LangGraph would increase complexity without solving a real requirement.

## Selected stack

| Area | Technology | Reason |
| --- | --- | --- |
| Language | Python 3.11+ | Strong LangChain and FastAPI support |
| Application | FastAPI | Typed APIs, authentication dependencies, and async support |
| Web UI | Jinja2 + minimal JavaScript | Keeps frontend and backend in one application |
| RAG framework | LangChain | Loading, chunking, retrieval, and LLM integration |
| Relational database | PostgreSQL | Users, roles, documents, and monitoring logs |
| ORM and migrations | SQLAlchemy + Alembic | Structured models and reproducible schema changes |
| Vector database | Qdrant | Metadata filtering is well suited to RBAC retrieval |
| Embeddings | SentenceTransformers | Free local embeddings |
| LLM | Llama through Groq | Simple hosted inference with a free development option |
| Authentication | JWT + pwdlib/Argon2 | Standard password authentication for the project scope |
| Document loading | LangChain text and CSV loaders | Matches the Markdown and CSV FinSolve corpus |
| Evaluation | Ragas | Retrieval and answer-quality evaluation |
| Testing | Pytest | Unit and integration tests |
| Packaging | Docker + Docker Compose | Reproducible local setup |
| CI | GitHub Actions | Automated linting and tests |
| Deployment | Azure App Service | Simple container deployment target |

## Local services

Docker Compose should run only the required services:

1. FastAPI application
2. PostgreSQL
3. Qdrant

No Kafka, Redis, worker cluster, monitoring cluster, or Kubernetes is required.

## Main Python packages

```text
fastapi
uvicorn
jinja2
python-multipart
sqlalchemy
alembic
psycopg
pydantic-settings
pyjwt
pwdlib
langchain
langchain-community
langchain-qdrant
langchain-groq
sentence-transformers
qdrant-client
ragas
pytest
httpx
```

Pin compatible versions after the initial working installation.

## Environment variables

```dotenv
APP_ENV=development
SECRET_KEY=replace-with-a-long-random-value
ACCESS_TOKEN_EXPIRE_MINUTES=60

DATABASE_URL=postgresql+psycopg://app:app@postgres:5432/enterprise_rag

QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=company_documents

GROQ_API_KEY=
LLM_MODEL=
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

RETRIEVAL_TOP_K=4
RETRIEVAL_SCORE_THRESHOLD=0.50
MAX_UPLOAD_SIZE_MB=10
```

Do not commit the real `.env` file or API keys.

## RBAC metadata strategy

Each vector contains one FinSolve category: `general`, `hr`, `finance`, `engineering`, or `marketing`.

The backend converts the authenticated role into allowed categories and passes them to Qdrant as a filter. Admin receives all categories. The frontend does not choose or submit the user's role.

## Dataset

Use the Codebasics FinSolve Technologies corpus from:

`https://github.com/codebasics/ds-rpc-01/tree/main/resources/data`

Store its nine Markdown files and one CSV file under `sample_data/finsolve/` with the original department folders. This is the only required knowledge corpus for version one. Do not combine it with Kaggle datasets.

## Guardrail implementation

Keep guardrails deterministic and visible:

- Compiled patterns for obvious prompt injection.
- Retrieval score threshold for unsupported questions.
- Regex-based PII redaction for selected patterns.
- Citation validation against retrieved chunk metadata.

Do not introduce a separate guardrail framework unless the basic implementation proves insufficient.

## Monitoring implementation

Use a PostgreSQL request-log table and an admin dashboard. Calculate totals and averages with SQL queries.

Track token usage only when the Groq response exposes it. Cost can be calculated from configurable per-token rates. If usage data is unavailable, store `null` rather than estimating silently.

Do not add Prometheus, Grafana, OpenTelemetry, or a separate logging platform in the first version.

## Deployment scope

First make the project reliable locally with Docker Compose. Then deploy the application container to Azure App Service and configure hosted PostgreSQL and Qdrant endpoints through environment variables.

Cloud deployment is the final phase, not a prerequisite for implementing or testing the application.
