"""Python-side validation for supported preserved semi-explicit DAEs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import sympy
from scipy.integrate import solve_ivp
from scipy.optimize import root

from canonicalize.dae_system import SemiExplicitDaeSystem
from ir.equation_dict import equation_to_residual, expression_to_sympy
from latex_frontend.symbols import DeterministicCompileError
from simulate.compare import compare_simulations
from simulate.ode_sim import InputFunction, constant_inputs


@dataclass(frozen=True)
class DaeInitializationDiagnostics:
    """Initialization diagnostics for a supported preserved DAE."""

    success: bool
    differential_initial_conditions: dict[str, float]
    algebraic_initial_conditions: dict[str, float]
    provided_residual_norm: float
    solved_residual_norm: float
    message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "differential_initial_conditions": dict(self.differential_initial_conditions),
            "algebraic_initial_conditions": dict(self.algebraic_initial_conditions),
            "provided_residual_norm": self.provided_residual_norm,
            "solved_residual_norm": self.solved_residual_norm,
            "message": self.message,
        }


@dataclass(frozen=True)
class DaeValidationResult:
    """Numerical validation result for a preserved semi-explicit DAE."""

    classification: str
    initialization: DaeInitializationDiagnostics
    simulation_success: bool
    residual_norm_max: float
    residual_norm_final: float
    t: np.ndarray
    differential_states: np.ndarray
    algebraic_states: np.ndarray
    differential_state_names: list[str]
    algebraic_variable_names: list[str]
    comparison: dict[str, object] | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "initialization": self.initialization.to_dict(),
            "simulation_success": self.simulation_success,
            "residual_norm_max": self.residual_norm_max,
            "residual_norm_final": self.residual_norm_final,
            "t": self.t.tolist(),
            "differential_states": self.differential_states.tolist(),
            "algebraic_states": self.algebraic_states.tolist(),
            "differential_state_names": list(self.differential_state_names),
            "algebraic_variable_names": list(self.algebraic_variable_names),
            "comparison": self.comparison,
            "message": self.message,
        }


def validate_preserved_semi_explicit_dae(
    dae_system: SemiExplicitDaeSystem,
    *,
    parameter_values: dict[str, float],
    differential_initial_conditions: dict[str, float],
    algebraic_initial_conditions: dict[str, float] | None = None,
    input_function: InputFunction | None = None,
    t_span: tuple[float, float] = (0.0, 10.0),
    t_eval: np.ndarray | None = None,
    residual_tolerance: float = 1e-8,
    rtol: float = 1e-8,
    atol: float = 1e-10,
    expected_result: dict[str, object] | None = None,
    comparison_tolerance: float = 1e-6,
) -> DaeValidationResult:
    """Validate a preserved semi-explicit DAE by numerically solving algebraic variables."""
    compiled = _compile_preserved_functions(dae_system, parameter_values)
    initialization = initialize_preserved_dae(
        dae_system,
        parameter_values=parameter_values,
        differential_initial_conditions=differential_initial_conditions,
        algebraic_initial_conditions=algebraic_initial_conditions,
        input_function=input_function,
        t0=float(t_span[0]),
        residual_tolerance=residual_tolerance,
    )
    if not initialization.success:
        return DaeValidationResult(
            classification=dae_system.classification.kind,
            initialization=initialization,
            simulation_success=False,
            residual_norm_max=initialization.solved_residual_norm,
            residual_norm_final=initialization.solved_residual_norm,
            t=np.asarray([float(t_span[0])], dtype=float),
            differential_states=np.asarray(
                [[initialization.differential_initial_conditions[state] for state in dae_system.differential_states]],
                dtype=float,
            ),
            algebraic_states=np.asarray(
                [[initialization.algebraic_initial_conditions.get(name, 0.0) for name in dae_system.algebraic_variables]],
                dtype=float,
            ),
            differential_state_names=list(dae_system.differential_states),
            algebraic_variable_names=list(dae_system.algebraic_variables),
            message=initialization.message,
        )

    input_function = input_function or constant_inputs({})
    t_eval = np.asarray(t_eval if t_eval is not None else np.linspace(t_span[0], t_span[1], 101), dtype=float)
    x0 = np.asarray(
        [initialization.differential_initial_conditions[state] for state in dae_system.differential_states],
        dtype=float,
    )
    z_guess = np.asarray(
        [initialization.algebraic_initial_conditions[name] for name in dae_system.algebraic_variables],
        dtype=float,
    )

    current_guess = z_guess.copy()

    def rhs(time_value: float, differential_state_vector: np.ndarray) -> np.ndarray:
        nonlocal current_guess
        algebraic_vector, _ = _solve_algebraic_state(
            compiled,
            differential_state_vector,
            current_guess,
            input_function=input_function,
            time_value=time_value,
            residual_tolerance=residual_tolerance,
        )
        current_guess = algebraic_vector
        return compiled.evaluate_rhs(time_value, differential_state_vector, algebraic_vector, input_function(time_value))

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
        raise RuntimeError(f"DAE simulation failed: {solution.message}")

    algebraic_trajectory: list[np.ndarray] = []
    residual_norms: list[float] = []
    current_guess = z_guess.copy()
    for time_value, differential_state_vector in zip(solution.t, solution.y.T, strict=True):
        algebraic_vector, residual_norm = _solve_algebraic_state(
            compiled,
            differential_state_vector,
            current_guess,
            input_function=input_function,
            time_value=float(time_value),
            residual_tolerance=residual_tolerance,
        )
        current_guess = algebraic_vector
        algebraic_trajectory.append(algebraic_vector)
        residual_norms.append(residual_norm)

    algebraic_states = (
        np.vstack(algebraic_trajectory)
        if algebraic_trajectory
        else np.zeros((solution.t.size, 0), dtype=float)
    )
    comparison = None
    if expected_result is not None:
        comparison = compare_simulations(
            {
                "t": solution.t,
                "states": solution.y.T,
                "state_names": list(dae_system.differential_states),
            },
            expected_result,
            tolerance=comparison_tolerance,
        )

    return DaeValidationResult(
        classification=dae_system.classification.kind,
        initialization=initialization,
        simulation_success=True,
        residual_norm_max=max(residual_norms, default=initialization.solved_residual_norm),
        residual_norm_final=residual_norms[-1] if residual_norms else initialization.solved_residual_norm,
        t=np.asarray(solution.t, dtype=float),
        differential_states=np.asarray(solution.y.T, dtype=float),
        algebraic_states=algebraic_states,
        differential_state_names=list(dae_system.differential_states),
        algebraic_variable_names=list(dae_system.algebraic_variables),
        comparison=comparison,
    )


def initialize_preserved_dae(
    dae_system: SemiExplicitDaeSystem,
    *,
    parameter_values: dict[str, float],
    differential_initial_conditions: dict[str, float],
    algebraic_initial_conditions: dict[str, float] | None = None,
    input_function: InputFunction | None = None,
    t0: float = 0.0,
    residual_tolerance: float = 1e-8,
) -> DaeInitializationDiagnostics:
    """Compute or check consistent algebraic initial conditions for a preserved DAE."""
    compiled = _compile_preserved_functions(dae_system, parameter_values)
    input_function = input_function or constant_inputs({})
    differential_values = {
        state: float(differential_initial_conditions.get(state, 0.0))
        for state in dae_system.differential_states
    }
    provided_algebraic_values = {
        name: float((algebraic_initial_conditions or {}).get(name, 0.0))
        for name in dae_system.algebraic_variables
    }
    provided_guess = np.asarray(
        [provided_algebraic_values[name] for name in dae_system.algebraic_variables],
        dtype=float,
    )
    differential_vector = np.asarray(
        [differential_values[state] for state in dae_system.differential_states],
        dtype=float,
    )
    provided_residual = compiled.evaluate_residuals(
        t0,
        differential_vector,
        provided_guess,
        input_function(t0),
    )
    provided_norm = float(np.linalg.norm(provided_residual, ord=2))

    try:
        solved_algebraic_vector, solved_residual_norm = _solve_algebraic_state(
            compiled,
            differential_vector,
            provided_guess,
            input_function=input_function,
            time_value=t0,
            residual_tolerance=residual_tolerance,
        )
    except DeterministicCompileError as exc:
        return DaeInitializationDiagnostics(
            success=False,
            differential_initial_conditions=differential_values,
            algebraic_initial_conditions=provided_algebraic_values,
            provided_residual_norm=provided_norm,
            solved_residual_norm=provided_norm,
            message=str(exc),
        )

    return DaeInitializationDiagnostics(
        success=True,
        differential_initial_conditions=differential_values,
        algebraic_initial_conditions={
            name: float(solved_algebraic_vector[index])
            for index, name in enumerate(dae_system.algebraic_variables)
        },
        provided_residual_norm=provided_norm,
        solved_residual_norm=solved_residual_norm,
    )


@dataclass(frozen=True)
class _CompiledPreservedDaeFunctions:
    dae_system: SemiExplicitDaeSystem
    residual_function: object
    jacobian_function: object | None
    rhs_function: object

    def evaluate_residuals(
        self,
        time_value: float,
        differential_state_vector: np.ndarray,
        algebraic_vector: np.ndarray,
        input_values: dict[str, float],
    ) -> np.ndarray:
        values = _ordered_symbol_values(
            self.dae_system,
            time_value,
            differential_state_vector,
            algebraic_vector,
            input_values,
        )
        raw = self.residual_function(*values)
        return np.asarray(raw, dtype=float).reshape(-1)

    def evaluate_jacobian(
        self,
        time_value: float,
        differential_state_vector: np.ndarray,
        algebraic_vector: np.ndarray,
        input_values: dict[str, float],
    ) -> np.ndarray | None:
        if self.jacobian_function is None:
            return None
        values = _ordered_symbol_values(
            self.dae_system,
            time_value,
            differential_state_vector,
            algebraic_vector,
            input_values,
        )
        raw = self.jacobian_function(*values)
        return np.asarray(raw, dtype=float)

    def evaluate_rhs(
        self,
        time_value: float,
        differential_state_vector: np.ndarray,
        algebraic_vector: np.ndarray,
        input_values: dict[str, float],
    ) -> np.ndarray:
        values = _ordered_symbol_values(
            self.dae_system,
            time_value,
            differential_state_vector,
            algebraic_vector,
            input_values,
        )
        raw = self.rhs_function(*values)
        return np.asarray(raw, dtype=float).reshape(-1)


def _compile_preserved_functions(
    dae_system: SemiExplicitDaeSystem,
    parameter_values: dict[str, float],
) -> _CompiledPreservedDaeFunctions:
    if dae_system.preserved_form is None:
        raise DeterministicCompileError("DAE-native validation requires a preserved semi-explicit DAE form.")

    independent_symbols = [sympy.Symbol(str(dae_system.independent_variable))] if dae_system.independent_variable else []
    differential_symbols = [sympy.Symbol(name) for name in dae_system.differential_states]
    algebraic_symbols = [sympy.Symbol(name) for name in dae_system.algebraic_variables]
    input_symbols = [sympy.Symbol(name) for name in dae_system.inputs]

    substitutions = {
        sympy.Symbol(name): sympy.Float(float(value))
        for name, value in parameter_values.items()
    }
    differential_rhs = [
        sympy.simplify(expression_to_sympy(dae_system.preserved_form.differential_rhs[state].rhs).subs(substitutions, simultaneous=True))
        for state in dae_system.differential_states
    ]
    residuals = [
        sympy.simplify(equation_to_residual(equation).subs(substitutions, simultaneous=True))
        for equation in dae_system.preserved_form.algebraic_residuals
    ]
    residual_jacobian = (
        sympy.Matrix(residuals).jacobian(algebraic_symbols)
        if algebraic_symbols
        else sympy.Matrix.zeros(0, 0)
    )

    allowed_symbols = {
        *(symbol.name for symbol in independent_symbols),
        *(symbol.name for symbol in differential_symbols),
        *(symbol.name for symbol in algebraic_symbols),
        *(symbol.name for symbol in input_symbols),
    }
    for residual in residuals:
        unresolved = sorted(symbol.name for symbol in residual.free_symbols if symbol.name not in allowed_symbols)
        if unresolved:
            raise DeterministicCompileError(
                f"Preserved DAE residual retains unsupported symbolic coefficients: {unresolved}."
            )
    for expr in differential_rhs:
        unresolved = sorted(symbol.name for symbol in expr.free_symbols if symbol.name not in allowed_symbols)
        if unresolved:
            raise DeterministicCompileError(
                f"Preserved DAE RHS retains unsupported symbolic coefficients: {unresolved}."
            )

    ordered_symbols = independent_symbols + differential_symbols + algebraic_symbols + input_symbols
    residual_function = sympy.lambdify(ordered_symbols, residuals, "numpy")
    jacobian_function = sympy.lambdify(ordered_symbols, residual_jacobian, "numpy") if algebraic_symbols else None
    rhs_function = sympy.lambdify(ordered_symbols, differential_rhs, "numpy")
    return _CompiledPreservedDaeFunctions(
        dae_system=dae_system,
        residual_function=residual_function,
        jacobian_function=jacobian_function,
        rhs_function=rhs_function,
    )


def _ordered_symbol_values(
    dae_system: SemiExplicitDaeSystem,
    time_value: float,
    differential_state_vector: np.ndarray,
    algebraic_vector: np.ndarray,
    input_values: dict[str, float],
) -> list[float]:
    values: list[float] = []
    if dae_system.independent_variable is not None:
        values.append(float(time_value))
    values.extend(float(value) for value in differential_state_vector)
    values.extend(float(value) for value in algebraic_vector)
    values.extend(float(input_values.get(name, 0.0)) for name in dae_system.inputs)
    return values


def _solve_algebraic_state(
    compiled: _CompiledPreservedDaeFunctions,
    differential_state_vector: np.ndarray,
    algebraic_guess: np.ndarray,
    *,
    input_function: InputFunction,
    time_value: float,
    residual_tolerance: float,
) -> tuple[np.ndarray, float]:
    if not compiled.dae_system.algebraic_variables:
        return np.zeros((0,), dtype=float), 0.0

    input_values = input_function(time_value)

    def fun(algebraic_vector: np.ndarray) -> np.ndarray:
        return compiled.evaluate_residuals(time_value, differential_state_vector, algebraic_vector, input_values)

    def jac(algebraic_vector: np.ndarray) -> np.ndarray | None:
        return compiled.evaluate_jacobian(time_value, differential_state_vector, algebraic_vector, input_values)

    jacobian = jac(algebraic_guess)
    if jacobian is not None and jacobian.shape[0] != jacobian.shape[1]:
        raise DeterministicCompileError("Algebraic subsystem Jacobian is non-square; preserved DAE support requires a square subsystem.")

    result = root(fun, algebraic_guess, jac=jac if jacobian is not None else None)
    residual_norm = float(np.linalg.norm(fun(np.asarray(result.x, dtype=float)), ord=2))
    if not result.success or residual_norm > residual_tolerance:
        raise DeterministicCompileError(
            "Failed to compute consistent algebraic variables for the preserved DAE "
            f"(success={result.success}, residual_norm={residual_norm:.3e})."
        )
    return np.asarray(result.x, dtype=float), residual_norm
