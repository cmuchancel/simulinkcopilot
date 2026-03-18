"""Generate the Phase 3 regression reports."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulate.regression_suite import write_regression_reports


def main() -> int:
    report = write_regression_reports(Path(__file__).resolve().parent)
    print(
        "Generated reports with "
        f"{report['passed_examples']}/{report['generated_examples']} passing examples."
    )
    return 0 if report["failed_examples"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
