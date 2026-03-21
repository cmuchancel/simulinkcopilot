from __future__ import annotations

import numpy as np

from latex_frontend.translator import translate_latex
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
