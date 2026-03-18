"""Run the bundled deterministic compiler examples."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.catalog import example_paths
from pipeline.run_pipeline import run_pipeline


def main() -> int:
    for path in example_paths():
        results = run_pipeline(path)
        comparison = results["comparison"]
        if comparison is not None and not comparison["passes"]:
            raise SystemExit(f"Validation failed for {path}")
        if comparison is None:
            print(f"{path.name}: ode-only path, nonlinear state-space comparison skipped")
        else:
            print(
                f"{path.name}: rmse={comparison['rmse']:.3e}, "
                f"max_abs={comparison['max_abs_error']:.3e}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
