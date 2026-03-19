"""Run the deterministic LaTeX-to-simulation pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import sympy

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonicalize_v2.linearity_check import analyze_first_order_linearity
from canonicalize_v2.nonlinear_forms import build_explicit_system_form
from canonicalize_v2.first_order import build_first_order_system
from canonicalize_v2.solve_for_derivatives import solve_for_highest_derivatives
from canonicalize_v2.state_space import build_state_space_system
from latex_frontend_v2.symbols import DeterministicCompileError
from ir_v2.equation_dict import (
    equation_to_dict,
    equation_to_string,
    expression_from_dict,
    expression_to_sympy,
    matrix_from_dict,
)
from ir_v2.graph_lowering import lower_first_order_system_graph
from ir_v2.graph_validate import validate_graph_dict
from latex_frontend_v2.translator import translate_file
from simulate_v2.compare import DEFAULT_TOLERANCE, compare_simulations
from simulate_v2.ode_sim import constant_inputs, simulate_ode_system
from simulate_v2.state_space_sim import simulate_state_space_system
from states_v2.extract_states import extract_states
from pipeline_v2.runtime_catalog import runtime_context_for_example


def default_runtime_context(stem: str, first_order_system: dict[str, object]) -> dict[str, object]:
    """Provide deterministic runtime defaults for the bundled examples."""
    return runtime_context_for_example(stem, first_order_system)


def apply_runtime_override(
    runtime: dict[str, object],
    override: dict[str, object] | None,
) -> dict[str, object]:
    """Apply deterministic runtime overrides for ad hoc pipeline runs."""
    if override is None:
        return runtime

    allowed_keys = {
        "parameter_values",
        "initial_conditions",
        "input_values",
        "t_span",
        "sample_count",
        "t_eval",
        "expected_linear",
    }
    unknown = sorted(set(override) - allowed_keys)
    if unknown:
        raise DeterministicCompileError(f"Unsupported runtime override keys: {', '.join(unknown)}")

    merged = {
        "parameter_values": dict(runtime["parameter_values"]),  # type: ignore[arg-type]
        "initial_conditions": dict(runtime["initial_conditions"]),  # type: ignore[arg-type]
        "input_function": runtime["input_function"],
        "t_span": tuple(runtime["t_span"]),  # type: ignore[arg-type]
        "t_eval": np.asarray(runtime["t_eval"], dtype=float),  # type: ignore[arg-type]
        "expected_linear": bool(runtime["expected_linear"]),
    }

    if "parameter_values" in override:
        merged["parameter_values"].update(dict(override["parameter_values"]))  # type: ignore[arg-type]
    if "initial_conditions" in override:
        merged["initial_conditions"].update(dict(override["initial_conditions"]))  # type: ignore[arg-type]
    if "input_values" in override:
        merged["input_function"] = constant_inputs(dict(override["input_values"]))  # type: ignore[arg-type]
    if "expected_linear" in override:
        merged["expected_linear"] = bool(override["expected_linear"])

    if "t_eval" in override:
        t_eval = np.asarray(override["t_eval"], dtype=float)  # type: ignore[arg-type]
        if t_eval.ndim != 1 or t_eval.size < 2:
            raise DeterministicCompileError("Runtime override t_eval must be a 1D array with at least two entries.")
        merged["t_eval"] = t_eval
        merged["t_span"] = (float(t_eval[0]), float(t_eval[-1]))
    else:
        t_span = merged["t_span"]
        if "t_span" in override:
            raw_t_span = override["t_span"]  # type: ignore[assignment]
            if not isinstance(raw_t_span, (list, tuple)) or len(raw_t_span) != 2:
                raise DeterministicCompileError("Runtime override t_span must be a two-item list or tuple.")
            t_span = (float(raw_t_span[0]), float(raw_t_span[1]))
            merged["t_span"] = t_span
        sample_count = int(len(merged["t_eval"]))
        if "sample_count" in override:
            sample_count = int(override["sample_count"])
            if sample_count < 2:
                raise DeterministicCompileError("Runtime override sample_count must be at least 2.")
        merged["t_eval"] = np.linspace(t_span[0], t_span[1], sample_count)

    return merged


def _constant_input_values(runtime: dict[str, object], input_names: list[str]) -> dict[str, float]:
    """Resolve a deterministic constant input vector from the runtime input function."""
    input_function = runtime["input_function"]
    start, stop = runtime["t_span"]  # type: ignore[index]
    sample_times = [float(start), float((start + stop) / 2.0), float(stop)]
    baseline = {
        name: float(input_function(sample_times[0]).get(name, 0.0))  # type: ignore[operator]
        for name in input_names
    }
    for time in sample_times[1:]:
        sample = {
            name: float(input_function(time).get(name, 0.0))  # type: ignore[operator]
            for name in input_names
        }
        if any(abs(sample[name] - baseline[name]) > 1e-12 for name in input_names):
            raise DeterministicCompileError(
                "The Simulink backend currently supports constant input functions only."
            )
    return baseline


def _input_signal_samples(runtime: dict[str, object], input_names: list[str]) -> dict[str, dict[str, list[float]]]:
    """Sample deterministic input signals on the runtime evaluation grid."""
    input_function = runtime["input_function"]
    t_eval = np.asarray(runtime["t_eval"], dtype=float)
    return {
        name: {
            "time": [float(time) for time in t_eval.tolist()],
            "values": [float(input_function(float(time)).get(name, 0.0)) for time in t_eval],
        }
        for name in input_names
    }


def run_pipeline(
    path: str | Path,
    tolerance: float = DEFAULT_TOLERANCE,
    *,
    run_sim: bool = True,
    validate_graph: bool = True,
    run_simulink: bool = False,
    runtime_override: dict[str, object] | None = None,
    matlab_engine=None,
    simulink_output_dir: str | Path | None = None,
) -> dict[str, object]:
    """Run the full deterministic pipeline and return structured results."""
    source_path = Path(path)
    equations = translate_file(source_path)
    equation_dicts = [equation_to_dict(equation) for equation in equations]
    extraction = extract_states(equations)
    solved_derivatives = solve_for_highest_derivatives(equations)
    first_order = build_first_order_system(equations, extraction=extraction, solved_derivatives=solved_derivatives)
    explicit_form = build_explicit_system_form(first_order)
    linearity = analyze_first_order_linearity(first_order)
    state_space = build_state_space_system(first_order) if linearity["is_linear"] else None
    graph = lower_first_order_system_graph(first_order, name=source_path.stem)
    validated_graph = validate_graph_dict(graph) if validate_graph else graph
    runtime = apply_runtime_override(default_runtime_context(source_path.stem, first_order), runtime_override)

    ode_result = None
    state_space_result = None
    comparison = None
    simulink_model = None
    simulink_result = None
    simulink_validation = None
    if run_sim:
        ode_result = simulate_ode_system(
            first_order,
            parameter_values=runtime["parameter_values"],  # type: ignore[arg-type]
            initial_conditions=runtime["initial_conditions"],  # type: ignore[arg-type]
            input_function=runtime["input_function"],  # type: ignore[arg-type]
            t_span=runtime["t_span"],  # type: ignore[arg-type]
            t_eval=runtime["t_eval"],  # type: ignore[arg-type]
        )
        if state_space is not None:
            state_space_result = simulate_state_space_system(
                state_space,
                parameter_values=runtime["parameter_values"],  # type: ignore[arg-type]
                initial_conditions=runtime["initial_conditions"],  # type: ignore[arg-type]
                input_function=runtime["input_function"],  # type: ignore[arg-type]
                t_span=runtime["t_span"],  # type: ignore[arg-type]
                t_eval=runtime["t_eval"],  # type: ignore[arg-type]
            )
            comparison = compare_simulations(ode_result, state_space_result, tolerance=tolerance)

    if run_simulink:
        from backend_v2.graph_to_simulink import graph_to_simulink_model
        from backend_v2.simulate_simulink import simulation_model_params, simulate_simulink_model
        from backend_v2.validate_simulink import compare_simulink_results
        from simulink_v2.engine import start_engine

        input_names = list(first_order["inputs"])  # type: ignore[index]
        input_values = None
        input_signals = None
        try:
            input_values = _constant_input_values(runtime, input_names)
        except DeterministicCompileError:
            input_signals = _input_signal_samples(runtime, input_names)
        model_params = simulation_model_params(
            t_span=runtime["t_span"],  # type: ignore[arg-type]
            t_eval=runtime["t_eval"],  # type: ignore[arg-type]
        )
        simulink_model = graph_to_simulink_model(
            validated_graph,
            name=f"{source_path.stem}_simulink",
            state_names=list(first_order["states"]),  # type: ignore[index]
            parameter_values=runtime["parameter_values"],  # type: ignore[arg-type]
            input_values=input_values,
            input_signals=input_signals,
            initial_conditions=runtime["initial_conditions"],  # type: ignore[arg-type]
            model_params=model_params,
        )
        owns_engine = matlab_engine is None
        eng = matlab_engine or start_engine(retries=1, retry_delay_seconds=1.0)
        try:
            simulink_result = simulate_simulink_model(
                eng,
                simulink_model,
                output_dir=simulink_output_dir or Path("generated_models") / "backend_models",
            )
        finally:
            if owns_engine:
                eng.quit()
        if ode_result is None:
            raise DeterministicCompileError("Simulink validation requires the direct ODE simulation result.")
        simulink_validation = compare_simulink_results(
            simulink_result,
            ode_result,
            state_space_result,
            tolerance=tolerance,
        )

    return {
        "source_path": str(source_path),
        "equations": equations,
        "equation_dicts": equation_dicts,
        "extraction": extraction,
        "solved_derivatives": solved_derivatives,
        "first_order": first_order,
        "explicit_form": explicit_form,
        "linearity": linearity,
        "state_space": state_space,
        "graph": validated_graph,
        "ode_result": ode_result,
        "state_space_result": state_space_result,
        "comparison": comparison,
        "simulink_model": simulink_model,
        "simulink_result": simulink_result,
        "simulink_validation": simulink_validation,
        "runtime": runtime,
    }


def summarize_pipeline_results(results: dict[str, object]) -> dict[str, object]:
    """Return a JSON-serializable summary for reporting and CLI output."""
    state_space = results["state_space"]
    comparison = results["comparison"]
    graph = results["graph"]
    simulink_result = results["simulink_result"]
    simulink_validation = results["simulink_validation"]
    return {
        "source_path": results["source_path"],
        "equations": [equation_to_string(equation) for equation in results["equations"]],  # type: ignore[index]
        "equation_dicts": results["equation_dicts"],
        "extraction": results["extraction"].to_dict(),  # type: ignore[union-attr]
        "solved_derivatives": [item.to_dict() for item in results["solved_derivatives"]],  # type: ignore[index]
        "first_order": results["first_order"],
        "explicit_form": {
            "form": results["explicit_form"]["form"],  # type: ignore[index]
            "rhs": {
                state: sympy.sstr(expr)
                for state, expr in results["explicit_form"]["rhs"].items()  # type: ignore[index]
            },
        },
        "linearity": {
            "is_linear": results["linearity"]["is_linear"],  # type: ignore[index]
            "offending_entries": results["linearity"]["offending_entries"],  # type: ignore[index]
        },
        "state_space": state_space,
        "graph": {
            "node_count": len(graph["nodes"]),  # type: ignore[index]
            "edge_count": len(graph["edges"]),  # type: ignore[index]
            "ops": sorted({node["op"] for node in graph["nodes"]}),  # type: ignore[index]
        },
        "comparison": comparison,
        "simulink": {
            "enabled": simulink_result is not None,
            "model_name": simulink_result["model_name"] if simulink_result is not None else None,
            "model_file": simulink_result["model_file"] if simulink_result is not None else None,
            "validation": simulink_validation,
        },
        "runtime": {
            "parameter_values": results["runtime"]["parameter_values"],  # type: ignore[index]
            "initial_conditions": results["runtime"]["initial_conditions"],  # type: ignore[index]
            "expected_linear": results["runtime"]["expected_linear"],  # type: ignore[index]
        },
    }


def _print_results(
    results: dict[str, object],
    *,
    show_ir: bool = False,
    show_first_order: bool = False,
    show_state_space: bool = False,
    show_graph_validation: bool = False,
) -> None:
    equations = results["equations"]
    extraction = results["extraction"]
    solved_derivatives = results["solved_derivatives"]
    first_order = results["first_order"]
    state_space = results["state_space"]
    comparison = results["comparison"]
    graph = results["graph"]
    simulink_result = results["simulink_result"]
    simulink_validation = results["simulink_validation"]

    print("Parsed equations:")
    for equation in equations:  # type: ignore[assignment]
        print(f"  {equation_to_string(equation)}")

    if show_ir:
        print("Canonical equation dicts:")
        for entry in results["equation_dicts"]:  # type: ignore[index]
            print(f"  {entry}")

    print("Extracted states:")
    print(f"  states: {list(extraction.states)}")  # type: ignore[attr-defined]
    print(f"  inputs: {list(extraction.inputs)}")  # type: ignore[attr-defined]
    print(f"  parameters: {list(extraction.parameters)}")  # type: ignore[attr-defined]

    print("Solved derivatives:")
    for item in solved_derivatives:  # type: ignore[assignment]
        print(f"  {equation_to_string(item.equation)}")

    if show_first_order or True:
        print("First-order system:")
        for entry in first_order["state_equations"]:  # type: ignore[index]
            rhs = sympy.sstr(expression_to_sympy(expression_from_dict(entry["rhs"])))
            print(f"  d/dt {entry['state']} = {rhs}")

    print("Linearity:")
    print(f"  is_linear: {results['linearity']['is_linear']}")  # type: ignore[index]

    if state_space is not None and (show_state_space or True):
        print("State-space matrices:")
        for name in ["A", "B", "offset"]:
            print(f"  {name} = {matrix_from_dict(state_space[name])}")  # type: ignore[index]
    else:
        print("State-space matrices:")
        print("  unavailable: nonlinear explicit system")

    print("Graph summary:")
    print(f"  nodes: {len(graph['nodes'])}")  # type: ignore[index]
    print(f"  edges: {len(graph['edges'])}")  # type: ignore[index]
    print(f"  ops: {sorted({node['op'] for node in graph['nodes']})}")  # type: ignore[index]

    if show_graph_validation:
        print("Graph validation:")
        print("  passes: True")

    print("Comparison metrics:")
    if comparison is None:
        print("  unavailable: state-space comparison skipped")
    else:
        print(f"  rmse: {comparison['rmse']}")
        print(f"  max_abs_error: {comparison['max_abs_error']}")
        print(f"  tolerance: {comparison['tolerance']}")
        print(f"  passes: {comparison['passes']}")

    print("Simulink backend:")
    if simulink_result is None:
        print("  unavailable: Simulink backend not requested")
    else:
        print(f"  model_name: {simulink_result['model_name']}")
        print(f"  model_file: {simulink_result['model_file']}")
        print(f"  vs_ode_rmse: {simulink_validation['vs_ode']['rmse']}")
        print(f"  vs_ode_max_abs_error: {simulink_validation['vs_ode']['max_abs_error']}")
        if simulink_validation["vs_state_space"] is not None:
            print(f"  vs_state_space_rmse: {simulink_validation['vs_state_space']['rmse']}")
            print(f"  vs_state_space_max_abs_error: {simulink_validation['vs_state_space']['max_abs_error']}")
        print(f"  passes: {simulink_validation['passes']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic LaTeX ODE pipeline.")
    parser.add_argument("--input", required=True, help="Path to a LaTeX equation file.")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="Validation tolerance.")
    parser.add_argument("--verbose", action="store_true", help="Write a verbose artifact bundle for this run.")
    parser.add_argument("--verbose-output-dir", help="Directory for verbose artifact outputs.")
    parser.add_argument("--show-ir", action="store_true", help="Print canonical equation dictionaries.")
    parser.add_argument("--show-first-order", action="store_true", help="Print the first-order system.")
    parser.add_argument("--show-state-space", action="store_true", help="Print the state-space system when available.")
    parser.add_argument("--write-graph-json", help="Write the lowered graph dictionary to a JSON file.")
    parser.add_argument("--validate-graph", action="store_true", help="Print graph-validation status.")
    parser.add_argument("--run-sim", dest="run_sim", action="store_true", help="Run simulation stages.")
    parser.add_argument("--skip-sim", dest="run_sim", action="store_false", help="Skip simulation stages.")
    parser.add_argument("--simulink", action="store_true", help="Build and validate a Simulink model from the lowered graph.")
    parser.add_argument("--simulink-output-dir", help="Directory for generated Simulink models.")
    parser.add_argument("--runtime-json", help="Path to a JSON file overriding parameter values, initial conditions, and time settings.")
    parser.add_argument("--report-json", help="Write a JSON pipeline summary to a file.")
    parser.set_defaults(run_sim=True)
    args = parser.parse_args()

    verbose_requested = args.verbose or args.verbose_output_dir is not None
    verbose_output_dir = (
        Path(args.verbose_output_dir)
        if args.verbose_output_dir
        else Path("reports") / "verbose" / Path(args.input).stem
    )

    engine = None
    try:
        runtime_override = None
        if args.runtime_json:
            runtime_override = json.loads(Path(args.runtime_json).read_text(encoding="utf-8"))

        if args.simulink and verbose_requested:
            from simulink_v2.engine import start_engine

            engine = start_engine(retries=1, retry_delay_seconds=1.0)

        results = run_pipeline(
            args.input,
            tolerance=args.tolerance,
            run_sim=args.run_sim,
            validate_graph=True,
            run_simulink=args.simulink,
            runtime_override=runtime_override,
            matlab_engine=engine,
            simulink_output_dir=args.simulink_output_dir,
        )
        _print_results(
            results,
            show_ir=args.show_ir,
            show_first_order=args.show_first_order,
            show_state_space=args.show_state_space,
            show_graph_validation=args.validate_graph,
        )

        if args.write_graph_json:
            Path(args.write_graph_json).write_text(json.dumps(results["graph"], indent=2), encoding="utf-8")

        if args.report_json:
            Path(args.report_json).write_text(json.dumps(summarize_pipeline_results(results), indent=2), encoding="utf-8")

        if verbose_requested:
            from pipeline_v2.verbose_artifacts import write_verbose_artifacts

            manifest = write_verbose_artifacts(
                results,
                verbose_output_dir,
                matlab_engine=engine,
            )
            print("Verbose artifacts:")
            print(f"  output_dir: {manifest['output_dir']}")
            for key, value in manifest["files"].items():
                if value is not None:
                    print(f"  {key}: {value}")

        comparison = results["comparison"]
        if args.simulink and results["simulink_validation"] is not None:
            return 0 if results["simulink_validation"]["passes"] else 1
        if comparison is None:
            return 0
        return 0 if comparison["passes"] else 1
    finally:
        if engine is not None:
            engine.quit()


if __name__ == "__main__":
    raise SystemExit(main())
