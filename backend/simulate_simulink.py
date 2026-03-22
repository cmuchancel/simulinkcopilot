"""Simulate backend-generated Simulink models and extract signals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import matlab
import numpy as np

from backend.builder import build_simulink_model
from backend.descriptor_to_simulink import descriptor_to_simulink_model
from backend.extract_signals import extract_simulink_signals
from backend.graph_to_simulink import graph_to_simulink_model
from backend.simulink_dict import BackendSimulinkModelDict, validate_simulink_model_dict
from backend.validate_simulink import compare_simulink_results


class SimulinkExecutionStageError(RuntimeError):
    """Wrap Simulink execution failures with the stage that produced them."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class SimulinkExecutionResult:
    """Shared Simulink execution artifacts for pipeline and benchmarks."""

    model: BackendSimulinkModelDict
    simulation: dict[str, object]
    validation: dict[str, object] | None
    build_time_sec: float
    simulation_time_sec: float

    @property
    def model_name(self) -> str:
        return str(self.simulation["model_name"])

    @property
    def model_file(self) -> str:
        return str(self.simulation["model_file"])

    @property
    def block_count(self) -> int:
        return len(self.model["blocks"])


def _run_built_model(
    eng,
    normalized_model: BackendSimulinkModelDict,
    *,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build a normalized model, run it, and extract logged signals."""
    build_info = build_simulink_model(
        eng,
        normalized_model,
        output_dir=output_dir,
        open_after_build=open_after_build,
    )
    prepare_workspace_variables(eng, normalized_model)
    sim_output = eng.sim(build_info["model_name"], "ReturnWorkspaceOutputs", "on", nargout=1)
    extracted = extract_simulink_signals(
        eng,
        sim_output,
        output_names=[entry["name"] for entry in normalized_model["outputs"]],
    )
    return build_info, extracted


def simulation_model_params(
    *,
    t_span: tuple[float, float],
    t_eval,
    solver: str = "ode45",
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-12,
) -> dict[str, object]:
    """Return deterministic model parameters for Simulink simulation."""
    t_eval = np.asarray(t_eval, dtype=float)
    max_step = float(np.min(np.diff(t_eval))) if t_eval.size > 1 else float(t_span[1] - t_span[0])
    return {
        "StartTime": str(float(t_span[0])),
        "StopTime": str(float(t_span[1])),
        "Solver": solver,
        "RelTol": repr(float(rel_tol)),
        "AbsTol": repr(float(abs_tol)),
        "MaxStep": repr(max_step),
        "OutputOption": "SpecifiedOutputTimes",
        "OutputTimes": [float(value) for value in t_eval.tolist()],
        "SaveOutput": "on",
        "OutputSaveName": "yout",
        "SaveFormat": "StructureWithTime",
    }


def prepare_workspace_variables(eng, model_dict: BackendSimulinkModelDict | dict[str, object]) -> None:
    """Populate MATLAB workspace variables required by a backend model dictionary."""
    normalized = validate_simulink_model_dict(model_dict)
    for name, value in normalized.get("workspace_variables", {}).items():
        if (
            isinstance(value, list)
            and value
            and all(isinstance(row, list) for row in value)
        ):
            eng.workspace[name] = matlab.double(value)
        else:
            eng.workspace[name] = value
        eng.eval(f"assignin('base', '{name}', {name});", nargout=0)


def simulate_simulink_model(
    eng,
    model_dict: BackendSimulinkModelDict | dict[str, object],
    *,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
) -> dict[str, object]:
    """Build, simulate, and extract a backend-generated Simulink model."""
    normalized = validate_simulink_model_dict(model_dict)
    build_info, extracted = _run_built_model(
        eng,
        normalized,
        output_dir=output_dir,
        open_after_build=open_after_build,
    )
    return {
        **build_info,
        **extracted,
    }


def _close_model_best_effort(eng, model_name: str | None, *, close_after_run: bool) -> None:
    """Close the generated model when requested, without masking the primary result."""
    if not close_after_run or model_name is None:
        return
    try:
        eng.close_system(model_name, 0, nargout=0)
    except Exception:  # pragma: no cover - cleanup best effort
        pass


def _execute_lowered_model(
    eng,
    *,
    model: BackendSimulinkModelDict,
    tolerance: float | None = None,
    ode_result: dict[str, object] | None = None,
    state_space_result: dict[str, object] | None = None,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
    close_after_run: bool = False,
    numeric_result_validator=None,
) -> SimulinkExecutionResult:
    """Build, simulate, and optionally compare a normalized Simulink model."""
    model_name: str | None = None
    try:
        try:
            build_start = time.perf_counter()
            build_info = build_simulink_model(
                eng,
                model,
                output_dir=output_dir,
                open_after_build=open_after_build,
            )
            build_time_sec = time.perf_counter() - build_start
            model_name = str(build_info["model_name"])
        except Exception as exc:
            raise SimulinkExecutionStageError("simulink_build", str(exc)) from exc

        try:
            prepare_workspace_variables(eng, model)
            simulation_start = time.perf_counter()
            sim_output = eng.sim(model_name, "ReturnWorkspaceOutputs", "on", nargout=1)
            extracted = extract_simulink_signals(
                eng,
                sim_output,
                output_names=[entry["name"] for entry in model["outputs"]],
            )
            simulation_time_sec = time.perf_counter() - simulation_start
            simulation = {
                **build_info,
                **extracted,
            }
        except Exception as exc:
            raise SimulinkExecutionStageError("simulink_simulation", str(exc)) from exc

        if numeric_result_validator is not None:
            try:
                numeric_result_validator("Simulink simulation", simulation)
            except Exception as exc:
                raise SimulinkExecutionStageError("simulink_simulation", str(exc)) from exc

        validation = None
        if tolerance is not None and ode_result is not None:
            try:
                validation = compare_simulink_results(
                    simulation,
                    ode_result,
                    state_space_result,
                    tolerance=tolerance,
                )
            except Exception as exc:
                raise SimulinkExecutionStageError("simulink_compare", str(exc)) from exc

        return SimulinkExecutionResult(
            model=model,
            simulation=simulation,
            validation=validation,
            build_time_sec=build_time_sec,
            simulation_time_sec=simulation_time_sec,
        )
    finally:
        _close_model_best_effort(eng, model_name, close_after_run=close_after_run)


def execute_simulink_graph(
    eng,
    *,
    graph: dict[str, object],
    name: str,
    state_names: list[str],
    parameter_values: dict[str, float],
    initial_conditions: dict[str, float],
    t_span: tuple[float, float],
    t_eval,
    input_values: dict[str, float] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    ode_result: dict[str, object] | None = None,
    state_space_result: dict[str, object] | None = None,
    tolerance: float | None = None,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
    close_after_run: bool = False,
    numeric_result_validator=None,
) -> SimulinkExecutionResult:
    """Lower a graph, build the Simulink model, simulate it, and optionally validate it."""
    model = graph_to_simulink_model(
        graph,
        name=name,
        state_names=state_names,
        parameter_values=parameter_values,
        input_values=input_values,
        input_signals=input_signals,
        initial_conditions=initial_conditions,
        model_params=simulation_model_params(t_span=t_span, t_eval=t_eval),
    )
    return _execute_lowered_model(
        eng,
        model=model,
        tolerance=tolerance,
        ode_result=ode_result,
        state_space_result=state_space_result,
        output_dir=output_dir,
        open_after_build=open_after_build,
        close_after_run=close_after_run,
        numeric_result_validator=numeric_result_validator,
    )


def execute_simulink_descriptor(
    eng,
    *,
    descriptor_system: dict[str, object],
    name: str,
    parameter_values: dict[str, float],
    differential_initial_conditions: dict[str, float],
    algebraic_initial_conditions: dict[str, float],
    t_span: tuple[float, float],
    t_eval,
    output_names: list[str] | None = None,
    input_values: dict[str, float] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
    close_after_run: bool = False,
    numeric_result_validator=None,
) -> SimulinkExecutionResult:
    """Build and simulate a linear descriptor-system model with preserved algebraic constraints."""
    model = descriptor_to_simulink_model(
        descriptor_system,
        name=name,
        parameter_values=parameter_values,
        input_values=input_values,
        input_signals=input_signals,
        differential_initial_conditions=differential_initial_conditions,
        algebraic_initial_conditions=algebraic_initial_conditions,
        output_names=output_names,
        model_params=simulation_model_params(t_span=t_span, t_eval=t_eval),
    )
    return _execute_lowered_model(
        eng,
        model=model,
        output_dir=output_dir,
        open_after_build=open_after_build,
        close_after_run=close_after_run,
        numeric_result_validator=numeric_result_validator,
    )


def execute_simulink_preserved_dae_graph(
    eng,
    *,
    graph: dict[str, object],
    name: str,
    output_names: list[str],
    parameter_values: dict[str, float],
    differential_initial_conditions: dict[str, float],
    algebraic_initial_conditions: dict[str, float],
    t_span: tuple[float, float],
    t_eval,
    input_values: dict[str, float] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
    close_after_run: bool = False,
    numeric_result_validator=None,
) -> SimulinkExecutionResult:
    """Lower and simulate a preserved semi-explicit DAE graph."""
    model = graph_to_simulink_model(
        graph,
        name=name,
        state_names=output_names,
        parameter_values=parameter_values,
        input_values=input_values,
        input_signals=input_signals,
        initial_conditions=differential_initial_conditions,
        algebraic_initial_conditions=algebraic_initial_conditions,
        model_params=simulation_model_params(t_span=t_span, t_eval=t_eval),
    )
    return _execute_lowered_model(
        eng,
        model=model,
        output_dir=output_dir,
        open_after_build=open_after_build,
        close_after_run=close_after_run,
        numeric_result_validator=numeric_result_validator,
    )
