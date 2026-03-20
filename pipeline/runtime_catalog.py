"""Bundled runtime metadata for the canonical pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from repo_paths import EXAMPLES_ROOT
from simulate.ode_sim import constant_inputs


@dataclass(frozen=True)
class ExampleSpec:
    name: str
    expected_linear: bool
    parameter_values: dict[str, float]
    input_values: dict[str, float]
    initial_conditions: dict[str, float]
    t_span: tuple[float, float] = (0.0, 10.0)
    sample_count: int = 400


EXAMPLE_SPECS: dict[str, ExampleSpec] = {
    "mass_spring_damper": ExampleSpec(
        name="mass_spring_damper",
        expected_linear=True,
        parameter_values={"m": 1.0, "c": 0.4, "k": 2.0},
        input_values={"u": 1.0},
        initial_conditions={"x": 0.0, "x_dot": 0.0},
    ),
    "coupled_system": ExampleSpec(
        name="coupled_system",
        expected_linear=True,
        parameter_values={"a": 2.0, "b": 0.5},
        input_values={"u": 1.0},
        initial_conditions={"x": 0.0, "y": 0.0},
    ),
    "two_mass_coupled": ExampleSpec(
        name="two_mass_coupled",
        expected_linear=True,
        parameter_values={"m_1": 1.0, "m_2": 1.5, "c": 0.3, "k": 2.0},
        input_values={"u": 1.0},
        initial_conditions={"x_1": 0.0, "x_1_dot": 0.0, "x_2": 0.0, "x_2_dot": 0.0},
    ),
    "three_mass_coupled": ExampleSpec(
        name="three_mass_coupled",
        expected_linear=True,
        parameter_values={"m_1": 1.0, "m_2": 1.2, "m_3": 0.9, "c": 0.25, "k": 1.8},
        input_values={"u": 1.0},
        initial_conditions={
            "x_1": 0.0,
            "x_1_dot": 0.0,
            "x_2": 0.0,
            "x_2_dot": 0.0,
            "x_3": 0.0,
            "x_3_dot": 0.0,
        },
    ),
    "damped_forced_system": ExampleSpec(
        name="damped_forced_system",
        expected_linear=True,
        parameter_values={"z": 0.4, "w_0": 1.6},
        input_values={"u": 1.0},
        initial_conditions={"x": 0.0, "v": 0.0},
    ),
    "driven_oscillator": ExampleSpec(
        name="driven_oscillator",
        expected_linear=True,
        parameter_values={"w_0": 1.4},
        input_values={"u": 1.0},
        initial_conditions={"x": 0.0, "v": 0.0},
    ),
    "nonlinear_pendulum": ExampleSpec(
        name="nonlinear_pendulum",
        expected_linear=False,
        parameter_values={"d": 0.15, "k": 1.0, "a_3": 0.2},
        input_values={"u": 0.0},
        initial_conditions={"q": 0.4, "w": 0.0},
    ),
    "third_order_system": ExampleSpec(
        name="third_order_system",
        expected_linear=True,
        parameter_values={"a": 1.0, "b": 0.5, "c": 0.4, "k": 1.2},
        input_values={"u": 1.0},
        initial_conditions={"x": 0.0, "x_dot": 0.0, "x_ddot": 0.0},
    ),
    "mixed_parameter_forms": ExampleSpec(
        name="mixed_parameter_forms",
        expected_linear=True,
        parameter_values={"m_1": 1.0, "m_2": 1.1, "c_1": 0.2, "c_2": 0.25, "k_12": 1.7},
        input_values={"u": 1.0},
        initial_conditions={"x_1": 0.0, "v_1": 0.0, "x_2": 0.0, "v_2": 0.0},
    ),
}


def example_paths() -> list[Path]:
    """Return bundled example files in deterministic order."""
    return [EXAMPLES_ROOT / f"{name}.tex" for name in sorted(EXAMPLE_SPECS)]


def runtime_context_for_example(stem: str, first_order_system: dict[str, object]) -> dict[str, object]:
    """Return deterministic runtime defaults for a bundled example."""
    spec = EXAMPLE_SPECS.get(stem)
    parameters = list(first_order_system["parameters"])  # type: ignore[index]
    inputs = list(first_order_system["inputs"])  # type: ignore[index]
    states = list(first_order_system["states"])  # type: ignore[index]

    parameter_values = {name: 1.0 for name in parameters}
    input_values = {name: 0.0 for name in inputs}
    initial_conditions = {name: 0.0 for name in states}
    t_span = (0.0, 10.0)
    sample_count = 400
    expected_linear = True

    if spec is not None:
        parameter_values.update(spec.parameter_values)
        input_values.update(spec.input_values)
        initial_conditions.update(spec.initial_conditions)
        t_span = spec.t_span
        sample_count = spec.sample_count
        expected_linear = spec.expected_linear

    return {
        "parameter_values": parameter_values,
        "input_function": constant_inputs(input_values),
        "initial_conditions": initial_conditions,
        "t_span": t_span,
        "t_eval": np.linspace(t_span[0], t_span[1], sample_count),
        "expected_linear": expected_linear,
    }
