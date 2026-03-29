from __future__ import annotations

import pytest

from canonicalize.dae_reduction import reduce_semi_explicit_dae
from canonicalize.dae_system import build_semi_explicit_dae_system
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex
from simulate import dae_init as dae_init_module
from simulate.dae_init import consistent_initialize_dae
from states.extract_states import extract_states


def test_consistent_initialize_dae_solves_reduced_algebraic_values() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "y-kx=0",
                r"\dot{x}=-y",
            ]
        )
    )
    extraction = extract_states(equations)
    reduction = reduce_semi_explicit_dae(equations)
    dae_system = build_semi_explicit_dae_system(extraction, reduction)

    initialized = consistent_initialize_dae(
        dae_system,
        parameter_values={"k": 3.0},
        differential_initial_conditions={"x": 2.0},
    )

    assert initialized.differential_initial_conditions == {"x": 2.0}
    assert initialized.algebraic_initial_conditions == {"y": 6.0}
    assert initialized.reduced_to_explicit is True


def test_consistent_initialize_dae_rejects_unresolved_constraints() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "y^2-x=0",
                r"\dot{x}=y",
            ]
        )
    )
    extraction = extract_states(equations)
    reduction = reduce_semi_explicit_dae(equations)
    dae_system = build_semi_explicit_dae_system(extraction, reduction)

    with pytest.raises(DeterministicCompileError, match="reducible semi-explicit DAE system"):
        consistent_initialize_dae(
            dae_system,
            parameter_values={},
            differential_initial_conditions={"x": 1.0},
        )


def test_consistent_initialize_dae_to_dict_no_algebraics_and_independent_variable_paths() -> None:
    equations = translate_latex(r"\dot{x}=-x")
    extraction = extract_states(equations)
    reduction = reduce_semi_explicit_dae(equations)
    dae_system = build_semi_explicit_dae_system(extraction, reduction)

    initialized = consistent_initialize_dae(
        dae_system,
        parameter_values={},
        differential_initial_conditions={"x": 1.5},
        independent_variable="t",
        t0=2.0,
    )

    assert initialized.to_dict() == {
        "differential_initial_conditions": {"x": 1.5},
        "algebraic_initial_conditions": {},
        "reduced_to_explicit": True,
    }


def test_consistent_initialize_dae_reports_missing_symbol_values() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}=-y",
                "y-u=0",
            ]
        )
    )
    extraction = extract_states(equations, mode="configured", symbol_config={"u": "input", "t": "independent_variable"})
    reduction = reduce_semi_explicit_dae(equations, protected_symbols={"u", "t"})
    dae_system = build_semi_explicit_dae_system(extraction, reduction)

    with pytest.raises(DeterministicCompileError, match="missing values for \\['u'\\]"):
        dae_init_module.consistent_initialize_dae(
            dae_system,
            parameter_values={},
            differential_initial_conditions={"x": 0.0},
            input_function=lambda _time: {},
        )


def test_consistent_initialize_dae_substitutes_independent_variable_into_algebraics() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}=y",
                "y-t=0",
            ]
        )
    )
    extraction = extract_states(
        equations,
        mode="configured",
        symbol_config={"t": "independent_variable"},
    )
    reduction = reduce_semi_explicit_dae(equations, protected_symbols={"t"})
    dae_system = build_semi_explicit_dae_system(extraction, reduction)

    initialized = consistent_initialize_dae(
        dae_system,
        parameter_values={},
        differential_initial_conditions={"x": 0.0},
        independent_variable="t",
        t0=2.5,
    )

    assert initialized.algebraic_initial_conditions == {"y": 2.5}
