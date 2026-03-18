"""Generate the comprehensive deterministic compiler benchmark report."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulate.benchmark_suite import write_full_system_benchmark_reports


def main() -> int:
    report = write_full_system_benchmark_reports()
    print(
        f"Generated full benchmark with {report['passed_cases']}/{report['generated_cases']} passing cases."
    )
    return 0 if report["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
