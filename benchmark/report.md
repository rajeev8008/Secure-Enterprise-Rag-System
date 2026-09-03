# Retrieval benchmark

- Date: 2026-09-03T11:06:58.489522+00:00
- Environment: local, real MiniLM and persistent Qdrant
- Dataset: 28 cases; expected-category distribution {'general': 4, 'hr': 5, 'finance': 6, 'engineering': 5, 'marketing': 5}; 5 cross-role; 3 absent-evidence
- Configuration: top-k 4, score threshold 0.5
- Metrics: `{
  "hit_rate_at_1": 0.7,
  "hit_rate_at_3": 0.75,
  "mean_reciprocal_rank": 0.7166666666666667,
  "category_authorization_accuracy": 1.0,
  "unauthorized_retrieval_rate": 0.0,
  "expected_source_accuracy": 0.75,
  "refusal_decision_accuracy": 0.8571428571428571,
  "retrieval_latency_median_ms": 12.528099992778152,
  "retrieval_latency_p95_ms": 19.632300012744963
}`
- Failed cases: GEN-03, HR-02, HR-04, FIN-03, FIN-04, XROLE-03
- Failure analysis: GEN-03: expected source missing; HR-02: expected source missing; HR-04: expected source missing; FIN-03: expected source missing; FIN-04: expected source missing; XROLE-03: refusal mismatch The current semantic threshold missed several short/numeric facts and one cross-role query matched accessible but irrelevant finance text.

Failures are reported as measured; expected answers were not changed. See `results.json` for per-case output.
