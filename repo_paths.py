"""Canonical repo and workspace path helpers."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = REPO_ROOT / "workspace"

BENCHMARK_ROOT = WORKSPACE_ROOT / "benchmark"
DATA_ROOT = WORKSPACE_ROOT / "data"
DOCS_ROOT = WORKSPACE_ROOT / "docs"
EXAMPLES_ROOT = WORKSPACE_ROOT / "examples"
GENERATED_MODELS_ROOT = WORKSPACE_ROOT / "generated_models"
BEDILLION_DEMO_ROOT = WORKSPACE_ROOT / "bedillion_demo"
REPORTS_ROOT = WORKSPACE_ROOT / "reports"
PAPER_ROOT = WORKSPACE_ROOT / "paper"
BASELINE_METRICS_PATH = REPORTS_ROOT / "baseline_metrics.json"
GUI_RUNS_ROOT = REPORTS_ROOT / "gui_runs"
GUI_DEBUG_ROOT = REPORTS_ROOT / "gui_debug"


def workspace_path(*parts: str) -> Path:
    """Return a path rooted under the repo workspace directory."""
    return WORKSPACE_ROOT.joinpath(*parts)
