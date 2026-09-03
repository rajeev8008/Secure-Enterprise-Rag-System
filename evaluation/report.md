# Live Ragas evaluation

- Date: 2026-09-03T11:01:26.619071+00:00
- Ragas: 0.3.9
- Groq model: openai/gpt-oss-120b
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Cases: 12 (10 scored; 2 refusal cases skipped)
- Metrics: faithfulness, answer_relevancy, llm_context_precision_with_reference
- Aggregate scores: `{"faithfulness": 0.6, "answer_relevancy": 0.5964960851591806, "llm_context_precision_with_reference": 0.48333333328499994}`
- Token usage: 4709 input, 862 output
- Duration: 86.25 seconds
- Evaluation error: None

Per-case scores, citations, contexts, and skipped reasons are in `results.json`. Ragas scores answer quality only; deterministic tests remain authoritative for RBAC.
