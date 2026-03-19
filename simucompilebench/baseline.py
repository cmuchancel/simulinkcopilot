"""Baseline lock-in helpers for regression-safe benchmark extensions."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


BASELINE_ABSOLUTE_METRIC_EPSILON = 1e-12
BASELINE_RELATIVE_METRIC_EPSILON = 0.05


def _quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = fraction * (len(ordered) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_legacy_benchmark_report(report: dict[str, Any]) -> dict[str, Any]:
    """Create a compact, regression-focused summary of the legacy synthetic benchmark."""
    systems = list(report.get("systems", []))
    rmse_values = [float(item["rmse"]) for item in systems if item.get("rmse") is not None]
    max_values = [float(item["max_abs_error"]) for item in systems if item.get("max_abs_error") is not None]
    stage_success_counts: dict[str, int] = {}
    system_summaries: dict[str, dict[str, Any]] = {}

    for item in systems:
        stage_flags = {
            key: bool(item[key])
            for key in (
                "parse_success",
                "state_extraction_success",
                "solve_success",
                "first_order_success",
                "state_space_success",
                "graph_success",
                "simulink_build_success",
                "simulation_success",
            )
            if key in item
        }
        for key, passed in stage_flags.items():
            if passed:
                stage_success_counts[key] = stage_success_counts.get(key, 0) + 1
        system_summaries[str(item["system_id"])] = {
            "overall_pass": bool(item["overall_pass"]),
            "rmse": item.get("rmse"),
            "max_abs_error": item.get("max_abs_error"),
            "stage_flags": stage_flags,
        }

    return {
        "generated_systems": int(report["generated_systems"]),
        "evaluated_systems": int(report["evaluated_systems"]),
        "passed_systems": int(report["passed_systems"]),
        "failed_systems": int(report["failed_systems"]),
        "success_rate": float(report["passed_systems"] / report["evaluated_systems"]),
        "failure_categories": dict(report.get("failure_categories", {})),
        "rmse_stats": {
            "average": float(report.get("average_rmse") or 0.0),
            "median": _quantile(rmse_values, 0.5),
            "p95": _quantile(rmse_values, 0.95),
            "max": max(rmse_values) if rmse_values else 0.0,
        },
        "max_abs_error_stats": {
            "average": float(report.get("average_max_abs_error") or 0.0),
            "median": _quantile(max_values, 0.5),
            "p95": _quantile(max_values, 0.95),
            "max": max(max_values) if max_values else 0.0,
        },
        "stage_success_counts": dict(sorted(stage_success_counts.items())),
        "system_summaries": system_summaries,
    }


def write_baseline_metrics(path: str | Path, report: dict[str, Any], *, source_commit: str | None = None) -> dict[str, Any]:
    """Write the locked baseline metrics to disk."""
    baseline = summarize_legacy_benchmark_report(report)
    if source_commit is not None:
        baseline["source_commit"] = source_commit
    output_path = Path(path)
    output_path.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")
    return baseline


def load_baseline_metrics(path: str | Path) -> dict[str, Any]:
    """Load baseline metrics from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metric_limit(reference: float) -> float:
    return max(
        reference + BASELINE_ABSOLUTE_METRIC_EPSILON,
        reference * (1.0 + BASELINE_RELATIVE_METRIC_EPSILON),
    )


def compare_legacy_report_to_baseline(report: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Compare the current legacy benchmark report to the locked baseline."""
    current = summarize_legacy_benchmark_report(report)
    mismatches: list[str] = []

    for key in ("generated_systems", "evaluated_systems", "passed_systems", "failed_systems"):
        if current[key] != baseline[key]:
            mismatches.append(f"{key} mismatch: current={current[key]} baseline={baseline[key]}")

    if current["failure_categories"] != baseline["failure_categories"]:
        mismatches.append(
            f"failure_categories mismatch: current={current['failure_categories']} baseline={baseline['failure_categories']}"
        )

    for bucket_name in ("rmse_stats", "max_abs_error_stats"):
        for metric_name, current_value in current[bucket_name].items():
            baseline_value = float(baseline[bucket_name][metric_name])
            if current_value > _metric_limit(baseline_value):
                mismatches.append(
                    f"{bucket_name}.{metric_name} regression: current={current_value} baseline={baseline_value}"
                )

    baseline_systems = dict(baseline.get("system_summaries", {}))
    current_systems = dict(current.get("system_summaries", {}))
    if set(current_systems) != set(baseline_systems):
        missing = sorted(set(baseline_systems) - set(current_systems))
        extra = sorted(set(current_systems) - set(baseline_systems))
        mismatches.append(f"system_id mismatch: missing={missing[:5]} extra={extra[:5]}")

    for system_id in sorted(set(current_systems) & set(baseline_systems)):
        current_item = current_systems[system_id]
        baseline_item = baseline_systems[system_id]
        if bool(current_item["overall_pass"]) != bool(baseline_item["overall_pass"]):
            mismatches.append(
                f"{system_id} overall_pass mismatch: current={current_item['overall_pass']} baseline={baseline_item['overall_pass']}"
            )
        for metric_name in ("rmse", "max_abs_error"):
            current_value = float(current_item[metric_name] or 0.0)
            baseline_value = float(baseline_item[metric_name] or 0.0)
            if current_value > _metric_limit(baseline_value):
                mismatches.append(
                    f"{system_id} {metric_name} regression: current={current_value} baseline={baseline_value}"
                )
        if current_item["stage_flags"] != baseline_item["stage_flags"]:
            mismatches.append(
                f"{system_id} stage_flags mismatch: current={current_item['stage_flags']} baseline={baseline_item['stage_flags']}"
            )

    return {
        "matches": not mismatches,
        "mismatches": mismatches,
        "current": current,
        "baseline": baseline,
    }
