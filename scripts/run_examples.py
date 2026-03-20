"""Run the bundled deterministic compiler examples."""

from __future__ import annotations

from pipeline.run_pipeline import run_pipeline
from pipeline.runtime_catalog import example_paths


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
