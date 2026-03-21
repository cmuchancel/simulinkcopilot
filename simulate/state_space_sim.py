"""State-space simulation using the derived A/B/C/D model."""

from __future__ import annotations

import numpy as np
import sympy
from scipy.integrate import solve_ivp

from ir.equation_dict import matrix_from_dict
from simulate.ode_sim import InputFunction, constant_inputs


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
    independent_variable = state_space_system.get("independent_variable")
    input_function = input_function or constant_inputs({})

    parameter_symbols = [sympy.Symbol(name) for name in parameters]
    independent_symbols = [sympy.Symbol(str(independent_variable))] if independent_variable else []
    A_expr = matrix_from_dict(state_space_system["A"])  # type: ignore[arg-type]
    B_expr = matrix_from_dict(state_space_system["B"])  # type: ignore[arg-type]
    C_expr = matrix_from_dict(state_space_system["C"])  # type: ignore[arg-type]
    D_expr = matrix_from_dict(state_space_system["D"])  # type: ignore[arg-type]
    offset_expr = matrix_from_dict(state_space_system["offset"])  # type: ignore[arg-type]
    compiled_A = sympy.lambdify(independent_symbols + parameter_symbols, A_expr, "numpy")
    compiled_B = sympy.lambdify(independent_symbols + parameter_symbols, B_expr, "numpy")
    compiled_C = sympy.lambdify(independent_symbols + parameter_symbols, C_expr, "numpy")
    compiled_D = sympy.lambdify(independent_symbols + parameter_symbols, D_expr, "numpy")
    compiled_offset = sympy.lambdify(independent_symbols + parameter_symbols, offset_expr, "numpy")
    parameter_vector = [float(parameter_values[name]) for name in parameters]

    x0 = np.asarray([float(initial_conditions.get(state, 0.0)) for state in states], dtype=float)

    def _evaluate_matrix(compiled, t: float) -> np.ndarray:
        values = ([float(t)] if independent_symbols else []) + parameter_vector
        return np.asarray(compiled(*values), dtype=float)

    def rhs(t: float, x: np.ndarray) -> np.ndarray:
        input_values = input_function(t)
        u = np.asarray([float(input_values.get(name, 0.0)) for name in inputs], dtype=float)
        A = _evaluate_matrix(compiled_A, t)
        B = _evaluate_matrix(compiled_B, t)
        offset = _evaluate_matrix(compiled_offset, t).reshape(-1)
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
    output_columns: list[np.ndarray] = []
    for index, time in enumerate(solution.t):
        C = _evaluate_matrix(compiled_C, float(time))
        D = _evaluate_matrix(compiled_D, float(time))
        y = C @ solution.y[:, index]
        if inputs:
            y = y + (D @ input_samples[index])
        output_columns.append(np.asarray(y, dtype=float).reshape(-1))
    outputs = np.vstack(output_columns) if output_columns else np.zeros((solution.t.size, 0))

    return {
        "t": solution.t,
        "states": solution.y.T,
        "outputs": outputs,
        "state_names": states,
        "input_names": inputs,
        "inputs": input_samples,
    }
