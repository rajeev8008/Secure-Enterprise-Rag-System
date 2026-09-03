# Codex IDE Prompt - Secure Enterprise RAG Assistant

Build the project described in `project.md`, `architecture.md`, and `techstack.md`.

## Important direction

Keep this project simple, complete, and easy to defend in an interview. Do not add microservices, Kafka, Kubernetes, LangGraph, autonomous agents, or features not requested in the documentation.

Use LangChain for document loading, chunking, embeddings, retrieval, and connecting retrieved context to the LLM. LangGraph is not needed because the application follows a direct RAG pipeline.

## Product to build

Create a secure internal company chatbot for the fictional fintech company **FinSolve Technologies**. Use the synthetic enterprise corpus from the official Codebasics `ds-rpc-01` repository as the knowledge base:

`https://github.com/codebasics/ds-rpc-01/tree/main/resources/data`

Copy the dataset into `sample_data/finsolve/`, preserve its department folders, and credit Codebasics in the README. It contains nine Markdown files and one CSV file across general, HR, finance, engineering, and marketing categories.

The system has six roles:

- `employee`: can access general documents only.
- `hr`: can access general and HR documents.
- `finance`: can access general and finance documents.
- `engineering`: can access general and engineering documents.
- `marketing`: can access general and marketing documents.
- `admin`: can access every category, upload documents, and view monitoring.

Every document chunk must contain access metadata. Apply RBAC as a Qdrant metadata filter before retrieved text is sent to the LLM. Do not rely on the system prompt to hide unauthorized information.

## Required features

1. Email-and-password login with JWT authentication.
2. Seeded demo users for all six roles.
3. Load the Codebasics FinSolve Markdown and CSV corpus as sample data.
4. Admin-only Markdown and CSV document upload.
5. Document category selection: `general`, `hr`, `finance`, `engineering`, or `marketing`.
6. LangChain ingestion: load, split, embed, and store chunks in Qdrant.
7. Chat endpoint that retrieves only role-authorized chunks.
8. Answers grounded in retrieved context with filename and section or row citations.
9. Refusal when no sufficiently relevant context is found.
10. Simple guardrails:
   - block obvious prompt-injection phrases;
   - reject questions unrelated to available company documents when retrieval is weak;
   - redact common PII patterns from the final response.
11. Request logging in PostgreSQL for role, latency, token usage, retrieved sources, refusal status, and guardrail result.
12. Admin monitoring page with total requests, average latency, token usage, refusals, and blocked requests.
13. A small Ragas evaluation script with a sample dataset.
14. Unit tests for role permissions, metadata filters, guardrails, and citations.
15. Dockerfiles, Docker Compose for local development, `.env.example`, and clear README instructions.

## UI

Use FastAPI with Jinja templates and minimal JavaScript so the project remains a single application.

Pages:

- Login
- Chat
- Admin document upload
- Admin monitoring dashboard

The UI should be clean and functional, but visual polish is secondary to correctness.

## Implementation phases

### Phase 1 - Foundation

- Create the project structure.
- Add configuration management and environment variables.
- Configure PostgreSQL, SQLAlchemy, Alembic, and Qdrant.
- Create database models and migrations.
- Add health endpoints.

### Phase 2 - Authentication and RBAC

- Implement password hashing, login, JWT creation, and authenticated dependencies.
- Add the six roles and seed demo users.
- Implement a single centralized role-to-document-category mapping.
- Add authorization tests.

### Phase 3 - Document ingestion

- Add the attributed FinSolve corpus under `sample_data/finsolve/`.
- Implement admin-only Markdown and CSV upload.
- Validate file type and size.
- Load Markdown with a text loader and CSV with LangChain's CSV loader.
- Split documents into chunks.
- Add `document_id`, `category`, `filename`, and `section_or_row` metadata.
- Generate embeddings and upsert chunks into Qdrant.
- Prevent duplicate ingestion using a file checksum.

### Phase 4 - Secure RAG chat

- Implement role-filtered similarity search.
- Use retrieved chunks to create a concise grounded answer.
- Return structured citations.
- Refuse when retrieval has insufficient evidence.
- Ensure unauthorized chunks never enter the LLM prompt.

### Phase 5 - Guardrails, monitoring, and evaluation

- Implement deterministic prompt-injection checks.
- Implement PII redaction.
- Log request metrics.
- Build the admin monitoring page.
- Add a small Ragas evaluation dataset and runner.
- Complete the test suite.

### Phase 6 - Packaging

- Add Docker and Docker Compose.
- Add GitHub Actions for linting and tests.
- Write local setup and deployment documentation.

## Engineering rules

- Use typed Python and Pydantic schemas.
- Keep business logic out of route handlers.
- Use dependency injection for authentication, database sessions, the retriever, and LLM client.
- Return clear errors without exposing internal details.
- Never log passwords, JWTs, document text, or raw prompts containing sensitive data.
- Do not fabricate citations.
- Do not claim security or evaluation metrics that have not been tested.
- Prefer small, readable modules over abstractions with only one implementation.
- After every phase, run the relevant tests and update the README progress checklist.

## Definition of done

The project is complete when the FinSolve corpus is indexed, an admin can upload additional categorized Markdown or CSV documents, users can log in and receive answers only from authorized categories, responses contain valid citations, weak or unsafe questions are refused, basic metrics appear on the admin dashboard, and automated tests verify that RBAC is applied before generation.
