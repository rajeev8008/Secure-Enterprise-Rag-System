# Live Ragas evaluation

- Date: 2026-09-03T12:05:36.996603+00:00
- Ragas: 0.3.9
- Groq model: openai/gpt-oss-120b
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Cases: 12 (10 scored; 2 refusal cases skipped)
- Metrics: faithfulness, answer_relevancy, llm_context_precision_with_reference
- Aggregate scores: `{"faithfulness": 0.75, "answer_relevancy": 0.7489927418137861, "llm_context_precision_with_reference": 0.7833333332591667}`
- Token usage: 6022 input, 1001 output
- Duration: 63.89 seconds
- Evaluation error: None

Per-case scores, citations, contexts, and skipped reasons are in `results.json`. Ragas scores answer quality only; deterministic tests remain authoritative for RBAC.
