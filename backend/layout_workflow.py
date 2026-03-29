"""Shared layout workflow for Simulink model dictionaries."""

from __future__ import annotations

from typing import Any, Literal

from backend.layout import apply_deterministic_layout, apply_legacy_layout
from backend.layout_metrics import measure_layout
from backend.layout_visual_corrector import VisualRepairConfig, apply_visual_repair
from backend.simulink_dict import BackendSimulinkModelDict, validate_simulink_model_dict
from latex_frontend.symbols import DeterministicCompileError

LayoutMode = Literal["none", "legacy", "deterministic", "deterministic+visual"]


def apply_layout_workflow(
    model: BackendSimulinkModelDict | dict[str, object],
    *,
    layout_mode: LayoutMode = "deterministic",
    visual_repair_config: VisualRepairConfig | None = None,
    openai_client: Any = None,
) -> BackendSimulinkModelDict:
    """Apply the requested layout workflow and attach layout metrics when relevant."""
    validated = validate_simulink_model_dict(model)
    if layout_mode == "none":
        return validated
    if layout_mode == "legacy":
        return _finalize_layout(apply_legacy_layout(validated))
    if layout_mode == "deterministic":
        return _finalize_layout(apply_deterministic_layout(validated))
    if layout_mode == "deterministic+visual":
        laid_out = validate_simulink_model_dict(apply_deterministic_layout(validated))
        repaired = apply_visual_repair(
            laid_out,
            config=visual_repair_config,
            client=openai_client,
        )
        return _finalize_layout(repaired)
    raise DeterministicCompileError(f"Unsupported layout mode {layout_mode!r}.")


def _finalize_layout(model: BackendSimulinkModelDict | dict[str, object]) -> BackendSimulinkModelDict:
    finalized = validate_simulink_model_dict(model)
    finalized.setdefault("metadata", {})
    finalized["metadata"]["layout_metrics"] = measure_layout(finalized).to_dict()
    return finalized
