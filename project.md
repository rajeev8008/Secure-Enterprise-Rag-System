# Secure Enterprise RAG Assistant for FinSolve Technologies

## Project summary

The Secure Enterprise RAG Assistant is an internal chatbot for FinSolve Technologies, a fictional fintech company. It answers employee questions using the synthetic company-document corpus supplied by Codebasics and uses role-based access control so users retrieve only information permitted for their role.

The project demonstrates RAG, authentication, authorization, guardrails, evaluation, monitoring, and cloud-ready deployment without using agents or an unnecessarily complex architecture.

## Problem

Company information is often spread across policy documents, HR files, financial reports, and internal guides. Employees waste time finding the correct document, while a normal chatbot may expose information that a user is not permitted to access.

This project provides one searchable assistant while enforcing permissions before information reaches the language model.

## Users and permissions

| Role | Accessible document categories | Additional permissions |
| --- | --- | --- |
| Employee | General | Ask questions |
| HR | General, HR | Ask questions |
| Finance | General, Finance | Ask questions |
| Engineering | General, Engineering | Ask questions |
| Marketing | General, Marketing | Ask questions |
| Admin | All categories | Ask questions, upload documents, view monitoring |

## Dataset

Use the synthetic **FinSolve Technologies** corpus from the official Codebasics `ds-rpc-01` starter repository:

`https://github.com/codebasics/ds-rpc-01/tree/main/resources/data`

This is a RAG knowledge base, not a model-training dataset. Preserve its original folder structure under `sample_data/finsolve/` and credit Codebasics in the README.

| Category | Provided files |
| --- | --- |
| General | `employee_handbook.md` |
| HR | `hr_data.csv` |
| Finance | `financial_summary.md`, `quarterly_financial_report.md` |
| Engineering | `engineering_master_doc.md` |
| Marketing | `market_report_q4_2024.md`, `marketing_report_2024.md`, and Q1-Q3 marketing reports |

## Core user flow

1. A user logs in.
2. The backend reads the user's role from the validated JWT.
3. The user submits a company-related question.
4. Input guardrails check for obvious prompt injection.
5. The retriever applies a metadata filter based on the user's role.
6. Only authorized chunks are supplied to the LLM.
7. The application returns a grounded answer with citations.
8. The request's basic operational metrics are recorded.

## Required features

### Authentication

- Email-and-password login.
- Secure password hashing.
- JWT-based sessions.
- Six seeded demonstration accounts.

### Document management

- Admin-only upload for Markdown and CSV files.
- Each document is assigned `general`, `hr`, `finance`, `engineering`, or `marketing`.
- Documents are split and indexed through LangChain.
- Duplicate files are detected using a checksum.

### Secure RAG

- Semantic retrieval using Qdrant.
- Metadata filtering based on the authenticated user's role.
- Answers generated only from retrieved context.
- Filename and section or row citations.
- Refusal when relevant evidence is unavailable.

### Guardrails

- Block obvious prompt-injection requests.
- Treat low-relevance retrieval as out of scope or unanswerable.
- Redact common PII patterns from generated answers.

### Monitoring and evaluation

- Record latency, token usage, role, citations, refusals, and blocked requests.
- Provide an admin-only summary dashboard.
- Include a small Ragas evaluation dataset and runner.
- Test RBAC and retrieval filtering independently from the LLM.

## Functional examples

### Allowed request

A finance user asks, "What were the approved marketing expenses?" The retriever searches `general` and `finance` chunks and returns an answer with the relevant financial-report citation.

### Denied by retrieval

An employee asks, "Show me individual HR records." The employee's retrieval filter searches only `general` documents. HR content is never retrieved or placed in the prompt. The assistant reports that it cannot answer from the information available to the user.

### Insufficient information

A user asks a company-related question that is not answered by any accessible document. The system says it could not find sufficient information instead of inventing an answer.

## Non-goals

- No autonomous agents.
- No LangGraph workflow.
- No microservices.
- No Kafka or distributed job system.
- No enterprise identity-provider integration in the first version.
- No complex policy engine beyond the six defined roles.
- No support for formats beyond Markdown and CSV in the first version.
- No claim that the guardrails provide complete security.

## Success criteria

- Unauthorized document categories are excluded before LLM generation.
- Every normal answer includes at least one valid citation.
- Weak retrieval produces a refusal.
- Only admins can upload documents or see monitoring.
- PII patterns covered by tests are redacted.
- The application runs locally through Docker Compose.
- The automated test suite covers all role/category combinations.

## Suggested demo

1. Log in as an employee and successfully ask about a general leave policy.
2. Ask the employee account about payroll and show that no HR or finance source is retrieved.
3. Log in as finance and retrieve an authorized expense report.
4. Try an obvious prompt-injection request and show the refusal.
5. Log in as admin, upload a document, query it, and view the monitoring dashboard.
