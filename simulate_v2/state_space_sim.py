"""State-space simulation using the derived A/B/C/D model."""

from __future__ import annotations

import numpy as np
import sympy
from scipy.integrate import solve_ivp

from ir_v2.equation_dict import matrix_from_dict
from simulate_v2.ode_sim import InputFunction, constant_inputs


def simulate_state_space_system(
    state_space_system: dict[str, object],
    parameter_values: dict[str, float],
    initial_conditions: dict[str, float],
    input_function: InputFunction | None = None,
    t_span: tuple[float, float] = (0.0, 10.0),
    t_eval: np.ndarray | None = None,
    rtol: float = 1e-9,
    atol: float = 1e-12,
) -> dict[str, object]:
    """Simulate the linear state-space system using solve_ivp."""
    states = list(state_space_system["states"])  # type: ignore[index]
    inputs = list(state_space_system["inputs"])  # type: ignore[index]
    parameters = list(state_space_system["parameters"])  # type: ignore[index]
    input_function = input_function or constant_inputs({})

    substitutions = {sympy.Symbol(name): float(parameter_values[name]) for name in parameters}
    A = np.asarray(matrix_from_dict(state_space_system["A"]).subs(substitutions), dtype=float)  # type: ignore[arg-type]
    B = np.asarray(matrix_from_dict(state_space_system["B"]).subs(substitutions), dtype=float)  # type: ignore[arg-type]
    C = np.asarray(matrix_from_dict(state_space_system["C"]).subs(substitutions), dtype=float)  # type: ignore[arg-type]
    D = np.asarray(matrix_from_dict(state_space_system["D"]).subs(substitutions), dtype=float)  # type: ignore[arg-type]
    offset = np.asarray(matrix_from_dict(state_space_system["offset"]).subs(substitutions), dtype=float).reshape(-1)  # type: ignore[arg-type]

    x0 = np.asarray([float(initial_conditions.get(state, 0.0)) for state in states], dtype=float)

    def rhs(t: float, x: np.ndarray) -> np.ndarray:
        input_values = input_function(t)
        u = np.asarray([float(input_values.get(name, 0.0)) for name in inputs], dtype=float)
        return A @ x + (B @ u if inputs else 0.0) + offset

    solution = solve_ivp(
        rhs,
        t_span=t_span,
        y0=x0,
        t_eval=t_eval,
        dense_output=False,
        rtol=rtol,
        atol=atol,
    )
    if not solution.success:
        raise RuntimeError(f"State-space simulation failed: {solution.message}")

    input_samples = np.asarray(
        [[float(input_function(time).get(name, 0.0)) for name in inputs] for time in solution.t],
        dtype=float,
    ) if inputs else np.zeros((solution.t.size, 0))
    outputs = (C @ solution.y).T
    if inputs:
        outputs = outputs + (input_samples @ D.T)

    return {
        "t": solution.t,
        "states": solution.y.T,
        "outputs": outputs,
        "state_names": states,
        "input_names": inputs,
        "inputs": input_samples,
    }
