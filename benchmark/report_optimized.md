# Retrieval benchmark

- Date: 2026-09-03T12:02:30.299641+00:00
- Environment: local, real MiniLM and persistent Qdrant
- Dataset: 28 cases; expected-category distribution {'general': 4, 'hr': 5, 'finance': 6, 'engineering': 5, 'marketing': 5}; 5 cross-role; 3 absent-evidence
- Configuration: top-k 4, score threshold 0.4
- Metrics: `{
  "hit_rate_at_1": 0.85,
  "hit_rate_at_3": 0.95,
  "mean_reciprocal_rank": 0.9041666666666666,
  "category_authorization_accuracy": 1.0,
  "unauthorized_retrieval_rate": 0.0,
  "expected_source_accuracy": 1.0,
  "refusal_decision_accuracy": 1.0,
  "retrieval_latency_median_ms": 36.89809999195859,
  "retrieval_latency_p95_ms": 46.325900009833276
}`
- Failed cases: None
- Failure analysis: No failures. The current semantic threshold missed several short/numeric facts and one cross-role query matched accessible but irrelevant finance text.

Failures are reported as measured; expected answers were not changed. See `results.json` for per-case output.
