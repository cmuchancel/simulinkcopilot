"""Canonical lint runner for local and CI usage."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Apply safe Ruff fixes where available.")
    args = parser.parse_args()

    command = [sys.executable, "-m", "ruff", "check", "."]
    if args.fix:
        command.append("--fix")

    print("Running:", " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
