from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from latex_frontend.translator import translate_latex
from pipeline import compilation as compilation_module
from states.extract_states import analyze_state_extraction


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


def test_compile_symbolic_system_from_analysis_wraps_solve_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = replace(analyze_state_extraction(translate_latex(r"\dot{x}=-ax")), solved_derivatives=None)
    monkeypatch.setattr(compilation_module, "solve_for_highest_derivatives", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("solve boom")))

    with pytest.raises(compilation_module.SymbolicCompilationStageError) as exc_info:
        compilation_module.compile_symbolic_system_from_analysis(
            analysis,
            equations=translate_latex(r"\dot{x}=-ax"),
            graph_name="decay",
        )

    assert exc_info.value.stage == "solve"
    assert exc_info.value.completed_stages == ("state_extraction",)


@pytest.mark.parametrize(
    ("target_name", "failing_stage", "expected_completed"),
    [
        ("build_first_order_system", "first_order", ("state_extraction", "solve")),
        ("analyze_first_order_linearity", "state_space", ("state_extraction", "solve", "first_order")),
        ("build_descriptor_system_from_first_order", "descriptor_system", ("state_extraction", "solve", "first_order", "state_space")),
        ("lower_first_order_system_graph", "graph_lowering", ("state_extraction", "solve", "first_order", "state_space")),
    ],
)
def test_compile_symbolic_system_from_analysis_wraps_downstream_stage_failures(
    monkeypatch: pytest.MonkeyPatch,
    target_name: str,
    failing_stage: str,
    expected_completed: tuple[str, ...],
) -> None:
    analysis = analyze_state_extraction(translate_latex(r"\dot{x}=-ax"))
    if target_name == "build_descriptor_system_from_first_order":
        analysis = replace(analysis, descriptor_system=None)
    monkeypatch.setattr(compilation_module, target_name, lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(f"{failing_stage} boom")))

    with pytest.raises(compilation_module.SymbolicCompilationStageError) as exc_info:
        compilation_module.compile_symbolic_system_from_analysis(
            analysis,
            equations=translate_latex(r"\dot{x}=-ax"),
            graph_name="decay",
        )

    assert exc_info.value.stage == failing_stage
    assert exc_info.value.completed_stages == expected_completed


def test_compile_descriptor_system_and_preserved_dae_wrap_state_extraction_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compilation_module,
        "analyze_state_extraction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad extraction")),
    )

    with pytest.raises(compilation_module.SymbolicCompilationStageError, match="bad extraction"):
        compilation_module.compile_descriptor_system(translate_latex(r"\dot{x}+y=u"))

    with pytest.raises(compilation_module.SymbolicCompilationStageError, match="bad extraction"):
        compilation_module.compile_preserved_dae_system(translate_latex(r"\dot{x}=-x+z" + "\n" + r"z^3+z-x=0"), graph_name="dae")


def test_compile_descriptor_system_from_analysis_requires_descriptor_artifact() -> None:
    analysis = replace(analyze_state_extraction(translate_latex(r"\dot{x}=-ax")), descriptor_system=None)

    with pytest.raises(compilation_module.SymbolicCompilationStageError) as exc_info:
        compilation_module.compile_descriptor_system_from_analysis(
            analysis,
            equations=translate_latex(r"\dot{x}=-ax"),
        )

    assert exc_info.value.stage == "descriptor_system"


def test_compile_descriptor_system_from_analysis_succeeds_for_descriptor_capable_system() -> None:
    equations = translate_latex(r"\dot{x}+y=u" + "\n" + "x+y=1")
    analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})

    result = compilation_module.compile_descriptor_system_from_analysis(analysis, equations=equations)

    assert result.descriptor_system is not None
    assert result.dae_system.classification.kind in {"reducible_semi_explicit_dae", "linear_descriptor_dae"}


def test_compile_preserved_dae_system_from_analysis_requires_preserved_form() -> None:
    analysis = analyze_state_extraction(translate_latex(r"\dot{x}=-ax"))

    with pytest.raises(compilation_module.SymbolicCompilationStageError) as exc_info:
        compilation_module.compile_preserved_dae_system_from_analysis(
            analysis,
            equations=translate_latex(r"\dot{x}=-ax"),
            graph_name="dae",
        )

    assert exc_info.value.stage == "preserved_dae"


def test_compile_preserved_dae_system_from_analysis_wraps_lowering_and_validation_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    equations = translate_latex(r"\dot{x}=-x+z" + "\n" + r"z^3+z-x=0")
    analysis = analyze_state_extraction(equations)

    monkeypatch.setattr(
        compilation_module,
        "lower_semi_explicit_dae_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("lower boom")),
    )
    with pytest.raises(compilation_module.SymbolicCompilationStageError) as lower_exc:
        compilation_module.compile_preserved_dae_system_from_analysis(
            analysis,
            equations=equations,
            graph_name="dae",
        )
    assert lower_exc.value.stage == "graph_lowering"

    monkeypatch.setattr(compilation_module, "lower_semi_explicit_dae_graph", lambda *args, **kwargs: {"nodes": []})
    monkeypatch.setattr(
        compilation_module,
        "validate_graph_dict",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("invalid preserved graph")),
    )
    with pytest.raises(compilation_module.SymbolicCompilationStageError) as validate_exc:
        compilation_module.compile_preserved_dae_system_from_analysis(
            analysis,
            equations=equations,
            graph_name="dae",
            validate_graph=True,
        )
    assert validate_exc.value.stage == "graph_validation"
