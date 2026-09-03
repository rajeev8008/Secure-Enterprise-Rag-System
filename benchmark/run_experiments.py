import json
import statistics
from pathlib import Path
from time import perf_counter

from app.authorization import categories_for_role
from app.config import get_settings
from app.ingestion import get_embeddings
from app.qdrant import get_qdrant_client
from app.retrieval import retrieve_authorized_chunks

ROOT = Path(__file__).parent


def run(top_k: int, threshold: float) -> dict[str, float | int]:
    settings = get_settings().model_copy(update={"retrieval_top_k": top_k, "retrieval_score_threshold": threshold})
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    client, embeddings = get_qdrant_client(), get_embeddings()
    rows, latencies, unauthorized, retrieved, authorized_cases = [], [], 0, 0, 0
    for case in cases:
        started = perf_counter()
        chunks = retrieve_authorized_chunks(client, embeddings, settings, case["question"], case["role"])
        latencies.append((perf_counter() - started) * 1000)
        allowed = set(categories_for_role(case["role"]))
        unauthorized += sum(chunk.category not in allowed for chunk in chunks)
        authorized_cases += all(chunk.category in allowed for chunk in chunks)
        retrieved += len(chunks)
        rank = next((index for index, chunk in enumerate(chunks, 1) if chunk.filename == case["expected_source"]), None)
        rows.append((rank, not chunks))
    answerable = [(row, case) for row, case in zip(rows, cases) if not case["refusal_expected"]]
    ordered = sorted(latencies)
    return {
        "top_k": top_k, "score_threshold": threshold,
        "hit_rate_at_1": sum(row[0] == 1 for row, _ in answerable) / len(answerable),
        "hit_rate_at_3": sum(row[0] is not None and row[0] <= 3 for row, _ in answerable) / len(answerable),
        "mrr": sum(1 / row[0] if row[0] else 0 for row, _ in answerable) / len(answerable),
        "expected_source_accuracy": sum(row[0] is not None for row, _ in answerable) / len(answerable),
        "refusal_decision_accuracy": sum(row[1] == case["refusal_expected"] for row, case in zip(rows, cases)) / len(rows),
        "category_authorization_accuracy": authorized_cases / len(cases),
        "unauthorized_retrieval_rate": unauthorized / max(retrieved, 1),
        "latency_median_ms": statistics.median(latencies),
        "latency_p95_ms": ordered[min(len(ordered)-1, round((len(ordered)-1)*.95))],
    }


def main() -> None:
    results = [run(top_k, threshold) for threshold in (0.35, 0.4, 0.45, 0.5, 0.55) for top_k in (3, 4, 6, 10)]
    (ROOT / "experiment_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for result in results:
        print({key: round(value, 4) if isinstance(value, float) else value for key, value in result.items() if key not in {"category_authorization_accuracy", "unauthorized_retrieval_rate"}})


if __name__ == "__main__":
    main()
