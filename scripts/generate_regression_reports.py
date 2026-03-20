"""Generate the regression-report bundle for the canonical examples."""

from __future__ import annotations

from repo_paths import REPORTS_ROOT
from simulate.regression_suite import write_regression_reports


def main() -> int:
    report = write_regression_reports(REPORTS_ROOT)
    print(
        "Generated regression reports with "
        f"{report['passed_examples']}/{report['generated_examples']} passing examples."
    )
    return 0 if report["failed_examples"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
