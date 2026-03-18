"""Direct ODE simulation from first-order state equations."""

from __future__ import annotations

from typing import Callable

import numpy as np
import sympy
from scipy.integrate import solve_ivp

from canonicalize.first_order import first_order_rhs_sympy


InputFunction = Callable[[float], dict[str, float]]


def constant_inputs(values: dict[str, float]) -> InputFunction:
    """Return a time-invariant input function."""
    def _constant(_: float) -> dict[str, float]:
        return dict(values)

    return _constant


def _initial_state_vector(states: list[str], initial_conditions: dict[str, float]) -> np.ndarray:
    return np.asarray([float(initial_conditions.get(state, 0.0)) for state in states], dtype=float)


def simulate_ode_system(
    first_order_system: dict[str, object],
    parameter_values: dict[str, float],
    initial_conditions: dict[str, float],
    input_function: InputFunction | None = None,
    t_span: tuple[float, float] = (0.0, 10.0),
    t_eval: np.ndarray | None = None,
    rtol: float = 1e-9,
    atol: float = 1e-12,
) -> dict[str, object]:
    """Simulate the direct ODE system using solve_ivp."""
    states = list(first_order_system["states"])  # type: ignore[index]
    inputs = list(first_order_system["inputs"])  # type: ignore[index]
    parameters = list(first_order_system["parameters"])  # type: ignore[index]
    input_function = input_function or constant_inputs({})

    state_symbols = [sympy.Symbol(name) for name in states]
    input_symbols = [sympy.Symbol(name) for name in inputs]
    parameter_symbols = [sympy.Symbol(name) for name in parameters]
    rhs_exprs = first_order_rhs_sympy(first_order_system)
    compiled_rhs = sympy.lambdify(state_symbols + input_symbols + parameter_symbols, rhs_exprs, "numpy")

    parameter_vector = [float(parameter_values[name]) for name in parameters]

    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        input_values = input_function(t)
        input_vector = [float(input_values.get(name, 0.0)) for name in inputs]
        raw = compiled_rhs(*list(y), *input_vector, *parameter_vector)
        return np.asarray(raw, dtype=float).reshape(-1)

    y0 = _initial_state_vector(states, initial_conditions)
    solution = solve_ivp(
        rhs,
        t_span=t_span,
        y0=y0,
        t_eval=t_eval,
        dense_output=False,
        rtol=rtol,
        atol=atol,
    )
    if not solution.success:
        raise RuntimeError(f"ODE simulation failed: {solution.message}")

    input_samples = np.asarray(
        [[float(input_function(time).get(name, 0.0)) for name in inputs] for time in solution.t],
        dtype=float,
    ) if inputs else np.zeros((solution.t.size, 0))

    return {
        "t": solution.t,
        "states": solution.y.T,
        "state_names": states,
        "input_names": inputs,
        "inputs": input_samples,
    }
