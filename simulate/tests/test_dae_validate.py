from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from canonicalize import dae_system as dae_system_module
from ir.expression_nodes import EquationNode, NumberNode, SymbolNode
from latex_frontend.translator import translate_latex
from latex_frontend.symbols import DeterministicCompileError
from simulate import dae_validate as dae_validate_module
from simulate.dae_validate import initialize_preserved_dae, validate_preserved_semi_explicit_dae
from simulate.ode_sim import constant_inputs
from states.extract_states import analyze_state_extraction


def test_initialize_preserved_dae_solves_algebraic_initial_conditions() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    initialized = initialize_preserved_dae(
        analysis.dae_system,
        parameter_values={},
        differential_initial_conditions={"x": 0.2},
        algebraic_initial_conditions={"z": 0.2},
        input_function=constant_inputs({}),
    )

    assert initialized.success is True
    assert initialized.solved_residual_norm < 1e-8


def test_validate_preserved_semi_explicit_dae_simulates_supported_system() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    validation = validate_preserved_semi_explicit_dae(
        analysis.dae_system,
        parameter_values={},
        differential_initial_conditions={"x": 0.2},
        algebraic_initial_conditions={"z": 0.2},
        input_function=constant_inputs({}),
        t_span=(0.0, 0.5),
        t_eval=np.linspace(0.0, 0.5, 6),
    )

    assert validation.simulation_success is True
    assert validation.residual_norm_max < 1e-8
    assert validation.differential_state_names == ["x"]
    assert validation.algebraic_variable_names == ["z"]


def test_validate_preserved_semi_explicit_dae_reports_unsatisfied_initialization() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=z", r"z^2+1=0"])),
        mode="strict",
    )

    validation = validate_preserved_semi_explicit_dae(
        analysis.dae_system,
        parameter_values={},
        differential_initial_conditions={"x": 0.0},
        algebraic_initial_conditions={"z": 0.0},
        input_function=constant_inputs({}),
        t_span=(0.0, 0.1),
        t_eval=np.linspace(0.0, 0.1, 3),
    )

    assert validation.simulation_success is False
    assert validation.initialization.success is False


def test_dae_validate_helper_paths_cover_to_dict_and_expected_comparison() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    validation = validate_preserved_semi_explicit_dae(
        analysis.dae_system,
        parameter_values={},
        differential_initial_conditions={"x": 0.2},
        algebraic_initial_conditions={"z": 0.2},
        input_function=constant_inputs({}),
        t_span=(0.0, 0.2),
        t_eval=np.linspace(0.0, 0.2, 3),
        expected_result={
            "t": np.linspace(0.0, 0.2, 3),
            "states": np.zeros((3, 1)),
            "state_names": ["x"],
        },
    )

    payload = validation.to_dict()
    assert payload["classification"] == "nonlinear_preserved_semi_explicit_dae"
    assert payload["comparison"] is not None
    assert validation.initialization.to_dict()["success"] is True


def test_validate_preserved_semi_explicit_dae_raises_on_solver_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    class _FailedSolution:
        success = False
        message = "solver broke"

    monkeypatch.setattr(dae_validate_module, "solve_ivp", lambda *args, **kwargs: _FailedSolution())

    with pytest.raises(RuntimeError, match="DAE simulation failed"):
        dae_validate_module.validate_preserved_semi_explicit_dae(
            analysis.dae_system,
            parameter_values={},
            differential_initial_conditions={"x": 0.2},
            algebraic_initial_conditions={"z": 0.2},
            input_function=constant_inputs({}),
            t_span=(0.0, 0.1),
            t_eval=np.linspace(0.0, 0.1, 3),
            residual_tolerance=1e-8,
            rtol=1e-8,
            atol=1e-10,
            expected_result=None,
            comparison_tolerance=1e-6,
        )


def test_dae_validate_internal_helpers_cover_no_preserved_form_and_symbol_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    with pytest.raises(DeterministicCompileError, match="requires a preserved semi-explicit DAE form"):
        dae_validate_module._compile_preserved_functions(
            replace(analysis.dae_system, preserved_form=None),
            {},
        )

    bad_residual_system = replace(
        analysis.dae_system,
        preserved_form=dae_system_module.PreservedSemiExplicitDaeForm(
            differential_rhs=analysis.dae_system.preserved_form.differential_rhs,
            algebraic_residuals=(EquationNode(lhs=NumberNode(0), rhs=SymbolNode("k")),),
            algebraic_constraint_map={"z": EquationNode(lhs=NumberNode(0), rhs=SymbolNode("k"))},
        ),
    )
    with pytest.raises(DeterministicCompileError, match="residual retains unsupported symbolic coefficients"):
        dae_validate_module._compile_preserved_functions(bad_residual_system, {})

    bad_rhs_system = replace(
        analysis.dae_system,
        preserved_form=dae_system_module.PreservedSemiExplicitDaeForm(
            differential_rhs={"x": EquationNode(lhs=analysis.dae_system.preserved_form.differential_rhs["x"].lhs, rhs=SymbolNode("k"))},
            algebraic_residuals=analysis.dae_system.preserved_form.algebraic_residuals,
            algebraic_constraint_map=analysis.dae_system.preserved_form.algebraic_constraint_map,
        ),
    )
    with pytest.raises(DeterministicCompileError, match="RHS retains unsupported symbolic coefficients"):
        dae_validate_module._compile_preserved_functions(bad_rhs_system, {})


def test_dae_validate_internal_helpers_cover_jacobian_none_and_ordered_values() -> None:
    analysis = analyze_state_extraction(
        translate_latex(r"\dot{x}=-x"),
        mode="strict",
    )
    preserved = dae_system_module.PreservedSemiExplicitDaeForm(
        differential_rhs={"x": EquationNode(lhs=NumberNode(0), rhs=SymbolNode("x"))},
        algebraic_residuals=(),
        algebraic_constraint_map={},
    )
    explicit_preserved = replace(
        analysis.dae_system,
        algebraic_variables=(),
        preserved_form=preserved,
    )
    compiled = dae_validate_module._compile_preserved_functions(explicit_preserved, {})
    assert compiled.evaluate_jacobian(0.0, np.asarray([1.0]), np.asarray([]), {}) is None
    assert dae_validate_module._ordered_symbol_values(explicit_preserved, 1.5, np.asarray([2.0]), np.asarray([]), {}) == [2.0]
    timed_preserved = replace(explicit_preserved, independent_variable="t")
    assert dae_validate_module._ordered_symbol_values(timed_preserved, 1.5, np.asarray([2.0]), np.asarray([]), {}) == [1.5, 2.0]
    algebraic_state, residual_norm = dae_validate_module._solve_algebraic_state(
        compiled,
        np.asarray([1.0]),
        np.asarray([]),
        input_function=constant_inputs({}),
        time_value=0.0,
        residual_tolerance=1e-8,
    )
    assert algebraic_state.shape == (0,)
    assert residual_norm == 0.0


def test_dae_validate_internal_helpers_reject_non_square_jacobian() -> None:
    class _Compiled:
        dae_system = type("D", (), {"algebraic_variables": ("z",)})()

        @staticmethod
        def evaluate_residuals(*_args, **_kwargs):
            return np.asarray([0.0, 0.0])

        @staticmethod
        def evaluate_jacobian(*_args, **_kwargs):
            return np.asarray([[1.0, 0.0]])

    with pytest.raises(DeterministicCompileError, match="Jacobian is non-square"):
        dae_validate_module._solve_algebraic_state(
            _Compiled(),
            np.asarray([0.0]),
            np.asarray([0.0]),
            input_function=constant_inputs({}),
            time_value=0.0,
            residual_tolerance=1e-8,
        )
