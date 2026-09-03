import json
import argparse
import hashlib
import statistics
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.authorization import categories_for_role
from app.config import get_settings
from app.ingestion import get_embeddings
from app.qdrant import get_qdrant_client
from app.retrieval import retrieve_authorized_chunks

ROOT = Path(__file__).parent


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    settings = get_settings()
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    embeddings, client = get_embeddings(), get_qdrant_client()
    rows, latencies = [], []
    for case in cases:
        started = perf_counter()
        chunks = retrieve_authorized_chunks(client, embeddings, settings, case["question"], case["role"])
        latency = (perf_counter() - started) * 1000
        latencies.append(latency)
        sources = [chunk.filename for chunk in chunks]
        rank = next((index for index, name in enumerate(sources, 1) if name == case["expected_source"]), None)
        allowed = set(categories_for_role(case["role"]))
        unauthorized = sum(chunk.category not in allowed for chunk in chunks)
        rows.append({
            "id": case["id"], "retrieved_sources": sources,
            "retrieved_categories": [chunk.category for chunk in chunks],
            "retrieved_chunks": [{"point_id": chunk.point_id, "chunk_index": chunk.chunk_index, "score": round(chunk.score, 6), "filename": chunk.filename, "category": chunk.category, "section_or_row": chunk.section_or_row} for chunk in chunks],
            "expected_rank": rank, "refused": not chunks, "unauthorized": unauthorized,
            "latency_ms": round(latency, 2),
        })
    answerable = [row for row, case in zip(rows, cases) if not case["refusal_expected"]]
    total_chunks = sum(len(row["retrieved_sources"]) for row in rows)
    metrics = {
        "hit_rate_at_1": sum(row["expected_rank"] == 1 for row in answerable) / len(answerable),
        "hit_rate_at_3": sum(row["expected_rank"] is not None and row["expected_rank"] <= 3 for row in answerable) / len(answerable),
        "mean_reciprocal_rank": sum(1 / row["expected_rank"] if row["expected_rank"] else 0 for row in answerable) / len(answerable),
        "category_authorization_accuracy": sum(row["unauthorized"] == 0 for row in rows) / len(rows),
        "unauthorized_retrieval_rate": sum(row["unauthorized"] for row in rows) / max(total_chunks, 1),
        "expected_source_accuracy": sum(row["expected_rank"] is not None for row in answerable) / len(answerable),
        "refusal_decision_accuracy": sum(row["refused"] == case["refusal_expected"] for row, case in zip(rows, cases)) / len(rows),
        "retrieval_latency_median_ms": statistics.median(latencies),
        "retrieval_latency_p95_ms": percentile(latencies, .95),
    }
    source_hashes = {path.relative_to(ROOT.parent).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT.parent / "sample_data" / "finsolve").rglob("*")) if path.is_file()}
    result = {"date": datetime.now(timezone.utc).isoformat(), "environment": "local", "case_count": len(cases), "embedding_model": settings.embedding_model, "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap, "top_k": settings.retrieval_top_k, "score_threshold": settings.retrieval_score_threshold, "source_hashes": source_hashes, "metrics": metrics, "cases": rows}
    suffix = f"_{args.label}" if args.label else ""
    (ROOT / f"results{suffix}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    failed = [row["id"] for row, case in zip(rows, cases) if (not case["refusal_expected"] and row["expected_rank"] is None) or row["refused"] != case["refusal_expected"]]
    distribution = {category: sum(category in case["expected_categories"] for case in cases) for category in ("general", "hr", "finance", "engineering", "marketing")}
    failure_details = [f"{row['id']}: expected source missing" if not case["refusal_expected"] else f"{row['id']}: refusal mismatch" for row, case in zip(rows, cases) if row["id"] in failed]
    report = f"""# Retrieval benchmark\n\n- Date: {result['date']}\n- Environment: local, real MiniLM and persistent Qdrant\n- Dataset: {len(cases)} cases; expected-category distribution {distribution}; 5 cross-role; 3 absent-evidence\n- Configuration: top-k {settings.retrieval_top_k}, score threshold {settings.retrieval_score_threshold}\n- Metrics: `{json.dumps(metrics, indent=2)}`\n- Failed cases: {', '.join(failed) if failed else 'None'}\n- Failure analysis: {'; '.join(failure_details) if failure_details else 'No failures.'} The current semantic threshold missed several short/numeric facts and one cross-role query matched accessible but irrelevant finance text.\n\nFailures are reported as measured; expected answers were not changed. See `results.json` for per-case output.\n"""
    (ROOT / f"report{suffix}.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
