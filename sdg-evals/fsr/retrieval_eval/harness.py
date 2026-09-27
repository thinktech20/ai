"""FSR retrieval eval harness — lightweight mode.

This harness currently logs one primary metric:
"number of FSRs retrieved vs what exists" (ratio + counts).
"""
from __future__ import annotations

import json
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

import mlflow

from fsr.retrieval_eval import metrics as m
from fsr.retrieval_eval.probe_set import ProbeQuery
from fsr.retrieval.retriever import ProbeInput, Retriever


def run_eval(
    retriever: Retriever,
    probe_set: list[ProbeQuery],
    experiment_name: str,
    run_name_prefix: str = "fsr_retrieval_eval",
    extra_tags: dict[str, str] | None = None,
    probe_set_params: dict[str, Any] | None = None,
) -> str:
    """Execute the harness end-to-end. Returns the MLflow run id."""
    result = run_eval_detailed(
        retriever=retriever,
        probe_set=probe_set,
        experiment_name=experiment_name,
        run_name_prefix=run_name_prefix,
        extra_tags=extra_tags,
        probe_set_params=probe_set_params,
    )
    return result["run_id"]


def run_eval_detailed(
    retriever: Retriever,
    probe_set: list[ProbeQuery],
    experiment_name: str,
    run_name_prefix: str = "fsr_retrieval_eval",
    extra_tags: dict[str, str] | None = None,
    probe_set_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute harness and return run id plus aggregate metrics for comparisons."""
    mlflow.set_experiment(experiment_name)
    per_probe: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for probe in probe_set:
        t0 = time.perf_counter()
        try:
            results = retriever.retrieve(
                ProbeInput(esn=probe.esn, issue_prompt=probe.issue_prompt or probe.query)
            )
        except Exception as e:
            failed.append({"esn": probe.esn, "bucket": probe.bucket, "error": str(e)[:300]})
            print(f"[probe failed] esn={probe.esn} bucket={probe.bucket}: {e}")
            continue
        latency_ms = (time.perf_counter() - t0) * 1000.0

        probe_metrics: dict[str, Any] = {
            "esn": probe.esn,
            "bucket": probe.bucket,
            "query": probe.query,
            "component": probe.component,
            "issue_name": probe.issue_name,
            "issue_prompt": probe.issue_prompt,
            "n_returned": len(results),
            "topk_chunk_ids": [str(r.get("chunk_id")) for r in results if r.get("chunk_id")],
            "topk_document_ids": [str(r.get("document_id")) for r in results if r.get("document_id")],
            **m.retrieved_vs_exists_counts(results, probe.known_doc_ids),
            "retrieved_vs_exists_ratio": m.retrieved_vs_exists_ratio(results, probe.known_doc_ids),
            "latency_ms": latency_ms,
        }

        expected_doc_ids = probe.expected_document_ids or set()
        if expected_doc_ids:
            probe_metrics.update(
                m.doc_hit_at_k_metrics(
                    results=results,
                    expected_document_ids=expected_doc_ids,
                    min_expected_doc_hits_top_k=probe.min_expected_doc_hits_top_k,
                )
            )
            probe_metrics.update(
                m.doc_id_diff_details(
                    results=results,
                    expected_document_ids=expected_doc_ids,
                )
            )

        expected_cited_doc_pages = probe.expected_cited_doc_pages or []
        if expected_cited_doc_pages:
            probe_metrics.update(
                m.cited_doc_page_hit_metrics(
                    results=results,
                    expected_cited_doc_pages=expected_cited_doc_pages,
                )
            )

        expected_terms = probe.expected_evidence_terms or []
        if expected_terms:
            probe_metrics.update(
                m.evidence_term_at_k_metrics(
                    results=results,
                    expected_terms=expected_terms,
                    chunk_text_field="chunk_text",
                )
            )

        probe_metrics.update(
            m.filter_fidelity_at_k_metrics(
                results=results,
                probe_esn=probe.esn,
                probe_equip_type=probe.equip_type,
                esn_field="region_primary_esn",
                equip_type_field="region_primary_equip_type",
                eligible_document_ids=expected_doc_ids,
            )
        )

        if expected_cited_doc_pages:
            probe_metrics.update(
                m.page_level_metrics(results, expected_cited_doc_pages)
            )
        if probe.expected_chunk_ids:
            probe_metrics.update(m.exact_chunk_metrics(results, probe.expected_chunk_ids))

        per_probe.append(probe_metrics)

    agg = _aggregate(per_probe)
    run_name = f"{run_name_prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(
            {
                "strategy": retriever.strategy_name,
                "probe_set_size": len(probe_set),
                **{f"probe_{k}": str(v) for k, v in (probe_set_params or {}).items()},
            }
        )

        for key, value in agg.items():
            if key == "latency_ms":
                mlflow.log_metric("avg_latency_ms", float(value))
            else:
                mlflow.log_metric(f"avg_{key}", float(value))

        if per_probe:
            mlflow.log_metric("p95_latency_ms", float(_p95([float(p["latency_ms"]) for p in per_probe])))
        mlflow.log_metric("probes_succeeded", len(per_probe))
        mlflow.log_metric("probes_failed", len(failed))
        mlflow.set_tags(
            {
                "pipeline": "fsr",
                "stage": "retrieval_eval",
                **(extra_tags or {}),
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
            for row in per_probe:
                fh.write(json.dumps(row, default=str) + "\n")
            artifact_path = fh.name
        mlflow.log_artifact(artifact_path, artifact_path="per_probe")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(asdict(retriever.config), fh, indent=2)
            cfg_path = fh.name
        mlflow.log_artifact(cfg_path, artifact_path="config")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(
                {
                    "aggregate": agg,
                    "probes_succeeded": len(per_probe),
                    "probes_failed": len(failed),
                },
                fh,
                indent=2,
                default=str,
            )
            summary_path = fh.name
        mlflow.log_artifact(summary_path, artifact_path="summary")

        if failed:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
                for row in failed:
                    fh.write(json.dumps(row, default=str) + "\n")
                fail_path = fh.name
            mlflow.log_artifact(fail_path, artifact_path="failed_probes")

        return {
            "run_id": run.info.run_id,
            "aggregate": agg,
            "probes_succeeded": len(per_probe),
            "probes_failed": len(failed),
        }


def _aggregate(per_probe: list[dict[str, Any]]) -> dict[str, float]:
    if not per_probe:
        return {}

    numeric_keys: set[str] = set()
    for row in per_probe:
        for key, value in row.items():
            if isinstance(value, (int, float)):
                numeric_keys.add(key)

    # Exclude non-metric identifier fields.
    numeric_keys.difference_update({"esn", "query", "bucket"})
    return {
        k: mean(float(p[k]) for p in per_probe if isinstance(p.get(k), (int, float)))
        for k in sorted(numeric_keys)
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(int(0.95 * (len(sorted_values) - 1)), 0)
    return sorted_values[idx]
