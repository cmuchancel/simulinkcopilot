"""Generate the synthetic dynamical-system benchmark dataset and reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulate.synthetic_benchmark import (
    DEFAULT_SYNTHETIC_SEED,
    DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    write_synthetic_benchmark_outputs,
)


def _progress(index: int, total: int, result: dict[str, object]) -> None:
    status = "PASS" if result["overall_pass"] else "FAIL"
    print(f"[{index}/{total}] {result['system_id']}: {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic compiler benchmark dataset and reports.")
    parser.add_argument("--count", type=int, default=DEFAULT_SYNTHETIC_SYSTEM_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SYNTHETIC_SEED)
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--no-simulink", action="store_true")
    args = parser.parse_args()

    report = write_synthetic_benchmark_outputs(
        output_dir=args.output_dir,
        data_dir=args.data_dir,
        count=args.count,
        seed=args.seed,
        run_simulink=not args.no_simulink,
        progress_callback=_progress,
    )
    print(
        f"Benchmark complete: {report['passed_systems']}/{report['evaluated_systems']} systems passed."
    )
    return 0 if report["failed_systems"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
