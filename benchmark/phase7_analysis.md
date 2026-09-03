# Phase 7 retrieval error analysis

Baseline configuration: MiniLM dense retrieval, top-k 4, cosine threshold 0.50, chunks 800/100. Authorization filtering was inside Qdrant and had no failures.

| Case | Role | Expected | Retrieved baseline | Classification | Correction |
|---|---|---|---|---|---|
| GEN-03 | hr | `employee_handbook.md`, provident-fund rate | No result; best expected chunk scored 0.480 | Threshold calibration | Threshold 0.40 and lexical overlap |
| HR-02 | admin | `hr_data.csv`, FINEMP1000 role | No result; unrelated HR rows scored up to 0.398 | Dense lexical mismatch | Require and rank exact structured identifiers |
| HR-04 | admin | `hr_data.csv`, FINEMP1005 rating | No result; generic performance text outranked the row | Dense lexical mismatch | Require and rank exact structured identifiers |
| FIN-03 | admin | `financial_summary.md`, revenue growth | Quarterly report and marketing results scored 0.500–0.552 | Ranking/source wording | Authorized lexical overlap over filename, heading, and text |
| FIN-04 | finance | `financial_summary.md`, software-subscription share | Quarterly report scored 0.507; expected source was rank 4 at 0.461 without threshold | Ranking/threshold | Threshold 0.40 and lexical reranking |
| XROLE-03 | finance | Refusal for marketing ROI | Authorized finance chunks scored 0.513–0.680 | Explicit category intent | Refuse explicit inaccessible department queries before vector search |

The initial optimized run left XROLE-04 incorrect because generic authorized text matched the word `role` while the requested employee ID was inaccessible. The final correction requires an exact authorized identifier match for structured employee-ID questions.

## Experiments

Twenty dense configurations compared thresholds 0.35–0.55 and top-k 3, 4, 6, and 10 on the frozen 28 cases. Threshold 0.40/top-k 4 was the simplest useful base: it raised expected-source accuracy to 0.85 and refusal accuracy to 0.9286. Lowering to 0.35 improved source metrics but introduced four false non-refusals. Increasing top-k alone did not improve the 0.50 baseline.

The final authorized lexical overlap and structured-query checks reached Hit@1 0.85, Hit@3 0.95, MRR 0.9042, expected-source accuracy 1.0, refusal accuracy 1.0, authorization accuracy 1.0, and unauthorized retrieval rate 0.0. Reproducible baseline p95 was 37.16 ms and final p95 was 46.33 ms, a 24.7% increase.

## Grounded-answer evaluation

With the corrected retrieval contexts and concise untrusted-context generation instructions, the frozen 12-case Ragas evaluation improved faithfulness from 0.6000 to 0.7500, answer relevancy from 0.5965 to 0.7490, and context precision from 0.4833 to 0.7833. Ten answerable cases were scored and two no-context refusal cases remained explicitly excluded.
