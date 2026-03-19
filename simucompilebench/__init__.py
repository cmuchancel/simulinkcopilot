"""Research-grade benchmark harness for the deterministic Simulink compiler."""

from .baseline import compare_legacy_report_to_baseline, summarize_legacy_benchmark_report
from .catalog import build_simucompilebench_specs, write_benchmark_dataset
from .runner import (
    render_simucompilebench_markdown,
    run_extended_benchmark,
    write_simucompilebench_reports,
)

__all__ = [
    "build_simucompilebench_specs",
    "compare_legacy_report_to_baseline",
    "render_simucompilebench_markdown",
    "run_extended_benchmark",
    "summarize_legacy_benchmark_report",
    "write_benchmark_dataset",
    "write_simucompilebench_reports",
]
