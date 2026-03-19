#!/usr/bin/env python3
"""Run the locked legacy synthetic benchmark and the additive SimuCompileBench suite."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from reports.generate_benchmark import main as _legacy_cli_main  # noqa: F401
from simulate.synthetic_benchmark import write_synthetic_benchmark_outputs
from simucompilebench.baseline import (
    compare_legacy_report_to_baseline,
    load_baseline_metrics,
    write_baseline_metrics,
)
from simucompilebench.catalog import build_simucompilebench_specs, write_benchmark_dataset
from simucompilebench.runner import combine_benchmark_results, run_extended_benchmark, write_simucompilebench_reports


def _current_commit() -> str | None:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
            .strip()
        )
    except Exception:
        return None


def _progress(prefix: str):
    def _callback(index: int, total: int, result: dict[str, object]) -> None:
        status = "PASS" if result["overall_pass"] else "FAIL"
        print(f"[{prefix} {index}/{total}] {result['system_id']}: {status}")

    return _callback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-simulink", action="store_true", help="Disable Simulink builds and simulations.")
    parser.add_argument("--baseline-path", default="baseline_metrics.json", help="Path to the locked baseline metrics file.")
    parser.add_argument("--benchmark-dir", default="benchmark", help="Directory for the tiered benchmark dataset.")
    parser.add_argument("--data-path", default="data/simucompilebench_systems.json", help="Path for the combined dataset manifest.")
    parser.add_argument("--reports-dir", default="reports", help="Directory for benchmark reports.")
    parser.add_argument("--refresh-baseline", action="store_true", help="Rewrite baseline_metrics.json from the current legacy benchmark.")
    args = parser.parse_args()

    run_simulink = not args.skip_simulink

    print("Running locked legacy synthetic benchmark...")
    legacy_report = write_synthetic_benchmark_outputs(
        output_dir=args.reports_dir,
        data_dir="data",
        run_simulink=run_simulink,
        progress_callback=_progress("legacy"),
    )

    baseline_path = Path(args.baseline_path)
    if args.refresh_baseline or not baseline_path.exists():
        print(f"Writing baseline metrics to {baseline_path}...")
        baseline = write_baseline_metrics(baseline_path, legacy_report, source_commit=_current_commit())
        baseline_comparison = {
            "matches": True,
            "mismatches": [],
            "current": baseline,
            "baseline": baseline,
        }
    else:
        baseline = load_baseline_metrics(baseline_path)
        baseline_comparison = compare_legacy_report_to_baseline(legacy_report, baseline)
        if not baseline_comparison["matches"]:
            print("Baseline regression detected:", file=sys.stderr)
            for mismatch in baseline_comparison["mismatches"]:
                print(f"- {mismatch}", file=sys.stderr)
            return 1

    all_specs = build_simucompilebench_specs(include_legacy=True)
    dataset_manifest = write_benchmark_dataset(
        all_specs,
        root_dir=args.benchmark_dir,
        data_path=args.data_path,
    )
    extended_specs = [spec for spec in all_specs if spec.tier != "tier1_verified"]
    legacy_specs = [spec for spec in all_specs if spec.tier == "tier1_verified"]

    print("Running additive SimuCompileBench extension...")
    extended_report = run_extended_benchmark(
        extended_specs,
        run_simulink=run_simulink,
        progress_callback=_progress("extended"),
    )

    combined_report = combine_benchmark_results(
        legacy_report=legacy_report,
        legacy_specs=legacy_specs,
        extended_report=extended_report,
        dataset_manifest=dataset_manifest,
        baseline_comparison=baseline_comparison,
    )
    write_simucompilebench_reports(combined_report, output_dir=args.reports_dir)

    print(
        "SimuCompileBench complete: "
        f"{combined_report['passed_systems']}/{combined_report['evaluated_systems']} systems passed."
    )
    print(f"Reports written to {Path(args.reports_dir) / 'simucompilebench.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
