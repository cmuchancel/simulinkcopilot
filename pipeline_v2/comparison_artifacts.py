"""Artifact generation for side-by-side v1 vs v2 pipeline comparisons."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

from pipeline.run_pipeline import run_pipeline as run_pipeline_v1
from pipeline.verbose_artifacts import write_verbose_artifacts as write_verbose_artifacts_v1
from pipeline_v2.run_pipeline import run_pipeline as run_pipeline_v2
from pipeline_v2.verbose_artifacts import write_verbose_artifacts as write_verbose_artifacts_v2


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _combine_images(left_path: Path, right_path: Path, output_path: Path) -> str:
    left = mpimg.imread(left_path)
    right = mpimg.imread(right_path)
    figure, axes = plt.subplots(1, 2, figsize=(16, 8))
    axes[0].imshow(left)
    axes[0].set_title("v1")
    axes[1].imshow(right)
    axes[1].set_title("v2")
    for axis in axes:
        axis.axis("off")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def write_v1_v2_comparison_artifacts(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    matlab_engine=None,
) -> dict[str, object]:
    """Write v1/v2 verbose bundles plus a side-by-side model comparison."""
    source_path = Path(input_path).resolve()
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    results_v1 = run_pipeline_v1(source_path, run_simulink=True, matlab_engine=matlab_engine)
    results_v2 = run_pipeline_v2(source_path, run_simulink=True, matlab_engine=matlab_engine)

    v1_dir = output_root / "v1"
    v2_dir = output_root / "v2"
    v1_manifest = write_verbose_artifacts_v1(results_v1, v1_dir, matlab_engine=matlab_engine)
    v2_manifest = write_verbose_artifacts_v2(results_v2, v2_dir, matlab_engine=matlab_engine)

    comparison = {
        "input_path": str(source_path),
        "v1_vs_v2_ode_rmse": float(
            np.sqrt(np.mean((results_v1["ode_result"]["states"] - results_v2["ode_result"]["states"]) ** 2))
        ),
        "v1_vs_v2_simulink_rmse": float(
            np.sqrt(
                np.mean(
                    (results_v1["simulink_result"]["states"] - results_v2["simulink_result"]["states"]) ** 2
                )
            )
        ),
        "v1_manifest": v1_manifest,
        "v2_manifest": v2_manifest,
    }

    files: dict[str, str | None] = {
        "comparison_json": _write_json(output_root / "comparison.json", comparison),
        "v1_expression_labeled_diagram": str(v1_dir / "simulink_model.png")
        if (v1_dir / "simulink_model.png").exists()
        else None,
        "v2_expression_labeled_diagram": str(v2_dir / "simulink_model.png")
        if (v2_dir / "simulink_model.png").exists()
        else None,
    }
    if files["v1_expression_labeled_diagram"] and files["v2_expression_labeled_diagram"]:
        files["model_comparison"] = _combine_images(
            Path(str(files["v1_expression_labeled_diagram"])),
            Path(str(files["v2_expression_labeled_diagram"])),
            output_root / "model_comparison.png",
        )
    else:
        files["model_comparison"] = None

    manifest = {
        "output_dir": str(output_root),
        "files": files,
        "comparison": comparison,
    }
    _write_json(output_root / "artifact_manifest.json", manifest)
    return manifest
