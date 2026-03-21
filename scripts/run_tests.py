"""Canonical test runner for local and CI usage."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-matlab", action="store_true", help="Include MATLAB/Simulink-backed tests.")
    parser.add_argument("--run-slow", action="store_true", help="Include slower integration tests.")
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage reporting.")
    args = parser.parse_args()

    marker_expr = []
    if not args.run_matlab:
        marker_expr.append("not matlab")
    if not args.run_slow and not args.run_matlab:
        marker_expr.append("not slow")

    command = [sys.executable, "-m", "pytest"]
    if marker_expr:
        command.extend(["-m", " and ".join(marker_expr)])
    if not args.no_coverage:
        command.extend(
            [
                "--cov",
                "--cov-report=term-missing",
                "--cov-report=xml",
                "--cov-fail-under=80",
            ]
        )
    if args.run_matlab:
        command.append("--run-matlab")
    if args.run_slow:
        command.append("--run-slow")

    print("Running:", " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
