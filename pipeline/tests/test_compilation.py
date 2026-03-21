from __future__ import annotations

import pytest

from latex_frontend.translator import translate_latex
from pipeline import compilation as compilation_module


def test_compile_symbolic_system_builds_shared_backend_artifacts() -> None:
    result = compilation_module.compile_symbolic_system(
        translate_latex(r"\dot{x}=-ax"),
        graph_name="decay",
        validate_graph=True,
    )

    assert result.extraction.states == ("x",)
    assert result.equation_dicts
    assert result.first_order["states"] == ["x"]
    assert result.state_space is not None
    assert result.graph["nodes"]
    assert result.validated_graph is not None


def test_compile_symbolic_system_wraps_state_extraction_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        compilation_module,
        "analyze_state_extraction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad extraction")),
    )

    with pytest.raises(compilation_module.SymbolicCompilationStageError) as exc_info:
        compilation_module.compile_symbolic_system(
            translate_latex(r"\dot{x}=-ax"),
            graph_name="decay",
        )

    assert exc_info.value.stage == "state_extraction"
    assert exc_info.value.completed_stages == ()


def test_compile_symbolic_system_carries_stage_context_for_graph_validation_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compilation_module,
        "validate_graph_dict",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("invalid graph")),
    )

    with pytest.raises(compilation_module.SymbolicCompilationStageError) as exc_info:
        compilation_module.compile_symbolic_system(
            translate_latex(r"\dot{x}=-ax"),
            graph_name="decay",
            validate_graph=True,
        )

    assert exc_info.value.stage == "graph_validation"
    assert exc_info.value.completed_stages == (
        "state_extraction",
        "solve",
        "first_order",
        "state_space",
        "graph_lowering",
    )
    assert exc_info.value.linearity is not None
    assert exc_info.value.linearity["is_linear"] is True
