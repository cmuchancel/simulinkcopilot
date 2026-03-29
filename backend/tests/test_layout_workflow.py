from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend import layout_workflow as module
from latex_frontend.symbols import DeterministicCompileError


def test_apply_layout_workflow_dispatches_legacy_and_records_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = {"name": "demo", "metadata": {}}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(module, "validate_simulink_model_dict", lambda value: value)
    monkeypatch.setattr(
        module,
        "apply_legacy_layout",
        lambda value: calls.append(("legacy", value)) or {"name": "legacy", "metadata": {}},
    )
    monkeypatch.setattr(
        module,
        "measure_layout",
        lambda value: calls.append(("measure", value)) or SimpleNamespace(to_dict=lambda: {"score": 1.0}),
    )

    result = module.apply_layout_workflow(model, layout_mode="legacy")

    assert calls[0] == ("legacy", model)
    assert calls[1][0] == "measure"
    assert result["metadata"]["layout_metrics"] == {"score": 1.0}


def test_apply_layout_workflow_runs_visual_repair_after_deterministic_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = {"name": "demo", "metadata": {}}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(module, "validate_simulink_model_dict", lambda value: value)
    monkeypatch.setattr(
        module,
        "apply_deterministic_layout",
        lambda value: calls.append(("deterministic", value)) or {"name": "laid_out", "metadata": {}},
    )
    monkeypatch.setattr(
        module,
        "apply_visual_repair",
        lambda value, **kwargs: calls.append(("visual", value)) or {"name": "repaired", "metadata": {}},
    )
    monkeypatch.setattr(module, "measure_layout", lambda value: SimpleNamespace(to_dict=lambda: {"score": 2.0}))

    result = module.apply_layout_workflow(model, layout_mode="deterministic+visual")

    assert calls == [
        ("deterministic", model),
        ("visual", {"name": "laid_out", "metadata": {}}),
    ]
    assert result["metadata"]["layout_metrics"] == {"score": 2.0}


def test_apply_layout_workflow_rejects_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "validate_simulink_model_dict", lambda value: value)

    with pytest.raises(DeterministicCompileError, match="Unsupported layout mode"):
        module.apply_layout_workflow({"name": "demo"}, layout_mode="mystery")  # type: ignore[arg-type]
