"""Generate the cross-front-door benchmark dataset and reports."""

from __future__ import annotations

import argparse

from repo_paths import DATA_ROOT, REPORTS_ROOT
from simulate.frontdoor_benchmark import (
    render_frontdoor_benchmark_markdown,
    write_frontdoor_benchmark_outputs,
)
from simulate.synthetic_benchmark import DEFAULT_SYNTHETIC_SEED, DEFAULT_SYNTHETIC_SYSTEM_COUNT


def _progress(index: int, total: int, summary: dict[str, object]) -> None:
    status = "PASS" if summary["all_frontdoors_passed"] else "FAIL"
    print(f"[{index}/{total}] {summary['system_id']}: {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the latex/matlab_symbolic/matlab_equation_text benchmark.")
    parser.add_argument("--count", type=int, default=DEFAULT_SYNTHETIC_SYSTEM_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SYNTHETIC_SEED)
    parser.add_argument("--output-dir", default=str(REPORTS_ROOT))
    parser.add_argument("--data-dir", default=str(DATA_ROOT))
    parser.add_argument("--simulink", action="store_true")
    args = parser.parse_args()

    report = write_frontdoor_benchmark_outputs(
        output_dir=args.output_dir,
        data_dir=args.data_dir,
        count=args.count,
        seed=args.seed,
        run_simulink=args.simulink,
        progress_callback=_progress,
    )
    print(render_frontdoor_benchmark_markdown(report))
    return 0 if report["all_frontdoors_passed_systems"] == report["generated_systems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
