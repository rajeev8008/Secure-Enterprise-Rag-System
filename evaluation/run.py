import json
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import ragas
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, ResponseRelevancy
from ragas.run_config import RunConfig

from app.config import get_settings
from app.generation import generate_grounded_answer, get_llm
from app.guardrails import redact_pii
from app.ingestion import get_embeddings
from app.qdrant import get_qdrant_client
from app.retrieval import retrieve_authorized_chunks

ROOT = Path(__file__).parent
REFUSAL = "I could not find sufficient information in the documents available to you."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    settings = get_settings()
    cases = json.loads((ROOT / "sample.json").read_text(encoding="utf-8"))
    embeddings, llm, client = get_embeddings(), get_llm(), get_qdrant_client()
    started = perf_counter()
    ordinary, output, input_tokens, output_tokens = [], [], 0, 0
    for case in cases:
        chunks = retrieve_authorized_chunks(client, embeddings, settings, case["user_input"], case["role"])
        citations = [{"filename": chunk.filename, "category": chunk.category, "section_or_row": chunk.section_or_row, "score": chunk.score} for chunk in chunks]
        contexts = [redact_pii(chunk.text) for chunk in chunks]
        if not chunks:
            output.append({"id": case["id"], "response": REFUSAL, "citations": [], "retrieved_contexts": [], "skipped_metrics": "refusal_has_no_context"})
            continue
        generation = generate_grounded_answer(
            redact_pii(case["user_input"]),
            [replace(chunk, text=redact_pii(chunk.text)) for chunk in chunks],
            llm,
        )
        input_tokens += generation.input_tokens or 0
        output_tokens += generation.output_tokens or 0
        ordinary.append({"user_input": case["user_input"], "response": redact_pii(generation.answer), "retrieved_contexts": contexts, "reference": case["reference"]})
        output.append({"id": case["id"], "response": redact_pii(generation.answer), "citations": citations, "retrieved_contexts": contexts})

    metrics = [Faithfulness(), ResponseRelevancy(strictness=1), LLMContextPrecisionWithReference()]
    metric_names = [metric.name for metric in metrics]
    error = None
    if ordinary:
        try:
            scored = evaluate(
                EvaluationDataset.from_list(ordinary),
                metrics=metrics,
                llm=LangchainLLMWrapper(llm),
                embeddings=LangchainEmbeddingsWrapper(embeddings),
                run_config=RunConfig(max_workers=1, timeout=180),
                raise_exceptions=False,
            ).to_pandas()
            scores = scored[metric_names].to_dict(orient="records")
            cursor = 0
            for row in output:
                if "skipped_metrics" not in row:
                    row["scores"] = scores[cursor]
                    cursor += 1
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

    aggregates = {
        metric: sum(float(row["scores"][metric]) for row in output if "scores" in row and row["scores"][metric] == row["scores"][metric]) / max(sum("scores" in row and row["scores"][metric] == row["scores"][metric] for row in output), 1)
        for metric in metric_names
    }
    result = {
        "date": datetime.now(timezone.utc).isoformat(), "ragas_version": ragas.__version__,
        "groq_model": settings.llm_model, "embedding_model": settings.embedding_model,
        "case_count": len(cases), "metric_configuration": metric_names,
        "aggregates": aggregates, "error": error, "input_tokens": input_tokens,
        "output_tokens": output_tokens, "duration_seconds": round(perf_counter() - started, 2), "cases": output,
    }
    suffix = f"_{args.label}" if args.label else ""
    (ROOT / f"results{suffix}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    report = f"""# Live Ragas evaluation\n\n- Date: {result['date']}\n- Ragas: {ragas.__version__}\n- Groq model: {settings.llm_model}\n- Embeddings: {settings.embedding_model}\n- Cases: {len(cases)} ({len(ordinary)} scored; {len(cases)-len(ordinary)} refusal cases skipped)\n- Metrics: {', '.join(metric_names)}\n- Aggregate scores: `{json.dumps(aggregates)}`\n- Token usage: {input_tokens} input, {output_tokens} output\n- Duration: {result['duration_seconds']} seconds\n- Evaluation error: {error or 'None'}\n\nPer-case scores, citations, contexts, and skipped reasons are in `results.json`. Ragas scores answer quality only; deterministic tests remain authoritative for RBAC.\n"""
    (ROOT / f"report{suffix}.md").write_text(report, encoding="utf-8")
    print(json.dumps({"aggregates": aggregates, "error": error, "duration_seconds": result["duration_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
