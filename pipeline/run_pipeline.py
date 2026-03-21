"""Run the deterministic LaTeX-to-simulation pipeline."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import sympy

from latex_frontend.symbols import DeterministicCompileError
from ir.equation_dict import (
    equation_to_string,
    expression_from_dict,
    expression_to_sympy,
    matrix_from_dict,
)
from latex_frontend.translator import translate_file
from pipeline.compilation import compile_symbolic_system
from simulate.compare import DEFAULT_TOLERANCE, compare_simulations
from simulate.input_sources import resolve_input_sources
from simulate.ode_sim import constant_inputs, simulate_ode_system
from simulate.state_space_sim import simulate_state_space_system
from states.classify_symbols import CONFIGURABLE_ROLES
from pipeline.runtime_catalog import runtime_context_for_example
from pipeline.gui_export import DEFAULT_GUI_REPORT_ROOT, export_results_to_gui_run
from repo_paths import BEDILLION_DEMO_ROOT, REPORTS_ROOT

DEFAULT_SIMULINK_OUTPUT_DIR = BEDILLION_DEMO_ROOT


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


def _parse_assignment(argument_name: str, *, value_type=float, allowed_values: set[str] | None = None):
    """Build an argparse parser for NAME=VALUE assignments."""

    def _inner(raw: str) -> tuple[str, object]:
        if "=" not in raw:
            raise argparse.ArgumentTypeError(f"{argument_name} must use NAME=VALUE syntax.")
        name, value = raw.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise argparse.ArgumentTypeError(f"{argument_name} requires a non-empty name before '='.")
        if not value:
            raise argparse.ArgumentTypeError(f"{argument_name} requires a non-empty value after '='.")
        if value_type is str:
            parsed_value = value
        else:
            try:
                parsed_value = value_type(value)
            except ValueError as exc:
                raise argparse.ArgumentTypeError(
                    f"{argument_name} value for {name!r} must parse as {value_type.__name__}."
                ) from exc
        if allowed_values is not None and parsed_value not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise argparse.ArgumentTypeError(
                f"{argument_name} value for {name!r} must be one of: {allowed}."
            )
        return name, parsed_value

    return _inner


def _merge_assignment_group(
    target: dict[str, object] | None,
    field: str,
    entries: list[tuple[str, object]],
) -> dict[str, object] | None:
    """Merge repeated NAME=VALUE arguments into a runtime-override mapping."""
    if not entries:
        return target
    merged = dict(target or {})
    current = dict(merged.get(field, {}))  # type: ignore[arg-type]
    current.update(dict(entries))
    merged[field] = current
    return merged


def _validate_expected_states(actual_states: tuple[str, ...], expected_states: list[str]) -> None:
    """Ensure CLI-declared states match the inferred state list."""
    if not expected_states:
        return
    unique_expected = tuple(dict.fromkeys(expected_states))
    if len(unique_expected) != len(actual_states) or set(unique_expected) != set(actual_states):
        raise DeterministicCompileError(
            "CLI-declared states do not match inferred states. "
            f"Expected {list(unique_expected)}, inferred {list(actual_states)}."
        )


def _resolved_simulink_output_dir(path: str | Path | None) -> Path:
    """Resolve the default Simulink output directory for CLI and API calls."""
    return Path(path).resolve() if path is not None else DEFAULT_SIMULINK_OUTPUT_DIR.resolve()


def run_pipeline(
    path: str | Path,
    tolerance: float = DEFAULT_TOLERANCE,
    *,
    run_sim: bool = True,
    validate_graph: bool = True,
    run_simulink: bool = False,
    runtime_override: dict[str, object] | None = None,
    classification_mode: str | None = None,
    symbol_config: str | Path | dict[str, object] | None = None,
    matlab_engine=None,
    simulink_output_dir: str | Path | None = None,
) -> dict[str, object]:
    """Run the full deterministic pipeline and return structured results."""
    source_path = Path(path)
    equations = translate_file(source_path)
    resolved_mode = classification_mode or ("configured" if symbol_config is not None else "strict")
    compilation = compile_symbolic_system(
        equations,
        graph_name=source_path.stem,
        classification_mode=resolved_mode,
        symbol_config=symbol_config,
        validate_graph=validate_graph,
    )
    extraction = compilation.extraction
    solved_derivatives = compilation.solved_derivatives
    first_order = compilation.first_order
    explicit_form = compilation.explicit_form
    linearity = compilation.linearity
    state_space = compilation.state_space
    validated_graph = compilation.validated_graph or compilation.graph
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
        from backend.simulate_simulink import execute_simulink_graph
        from simulink.engine import start_engine

        input_names = list(first_order["inputs"])  # type: ignore[index]
        resolved_inputs = resolve_input_sources(
            runtime["input_function"],  # type: ignore[arg-type]
            input_names,
            t_span=runtime["t_span"],  # type: ignore[arg-type]
            t_eval=runtime["t_eval"],  # type: ignore[arg-type]
        )
        owns_engine = matlab_engine is None
        eng = matlab_engine or start_engine(retries=1, retry_delay_seconds=1.0)
        try:
            execution = execute_simulink_graph(
                eng,
                graph=validated_graph,
                name=f"{source_path.stem}_simulink",
                state_names=list(first_order["states"]),  # type: ignore[index]
                parameter_values=runtime["parameter_values"],  # type: ignore[arg-type]
                initial_conditions=runtime["initial_conditions"],  # type: ignore[arg-type]
                t_span=runtime["t_span"],  # type: ignore[arg-type]
                t_eval=runtime["t_eval"],  # type: ignore[arg-type]
                input_values=resolved_inputs.constant_values,
                input_signals=resolved_inputs.signal_samples,
                ode_result=ode_result,
                state_space_result=state_space_result,
                tolerance=tolerance,
                output_dir=_resolved_simulink_output_dir(simulink_output_dir),
            )
            simulink_model = execution.model
            simulink_result = execution.simulation
            simulink_validation = execution.validation
        finally:
            if owns_engine:
                eng.quit()
        if simulink_validation is None:
            raise DeterministicCompileError("Simulink validation requires the direct ODE simulation result.")

    return {
        "source_path": str(source_path),
        "equations": compilation.equations,
        "equation_dicts": compilation.equation_dicts,
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
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input", help="Path to a LaTeX equation file.")
    source_group.add_argument("--equations", help="Raw LaTeX equations passed directly on the command line.")
    parser.add_argument(
        "--equations-name",
        default="inline_equations",
        help="Synthetic stem to use when --equations is provided. Controls report/model naming.",
    )
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="Validation tolerance.")
    parser.add_argument(
        "--classification-mode",
        choices=("strict", "configured"),
        help="Symbol-classification mode. Defaults to configured when symbol roles are provided.",
    )
    parser.add_argument(
        "--symbol-role",
        action="append",
        default=[],
        type=_parse_assignment("--symbol-role", value_type=str, allowed_values=CONFIGURABLE_ROLES),
        metavar="NAME=ROLE",
        help="Declare symbol metadata inline, for example m=parameter or u=input.",
    )
    parser.add_argument(
        "--state",
        action="append",
        default=[],
        metavar="NAME",
        help="Assert that the inferred state list includes exactly these states. Repeat for each state.",
    )
    parser.add_argument(
        "--parameter",
        action="append",
        default=[],
        type=_parse_assignment("--parameter"),
        metavar="NAME=VALUE",
        help="Override a parameter value inline.",
    )
    parser.add_argument(
        "--initial",
        action="append",
        default=[],
        type=_parse_assignment("--initial"),
        metavar="NAME=VALUE",
        help="Override an initial-condition value inline.",
    )
    parser.add_argument(
        "--input-value",
        action="append",
        default=[],
        type=_parse_assignment("--input-value"),
        metavar="NAME=VALUE",
        help="Override a constant input value inline.",
    )
    parser.add_argument(
        "--t-span",
        nargs=2,
        type=float,
        metavar=("START", "STOP"),
        help="Override the simulation time span inline.",
    )
    parser.add_argument("--sample-count", type=int, help="Override the simulation sample count inline.")
    parser.add_argument(
        "--expected-linear",
        dest="expected_linear",
        action="store_true",
        help="Override the runtime expectation to linear.",
    )
    parser.add_argument(
        "--expected-nonlinear",
        dest="expected_linear",
        action="store_false",
        help="Override the runtime expectation to nonlinear.",
    )
    parser.add_argument("--verbose", action="store_true", help="Write a verbose artifact bundle for this run.")
    parser.add_argument("--verbose-output-dir", help="Directory for verbose artifact outputs.")
    parser.add_argument("--show-ir", action="store_true", help="Print canonical equation dictionaries.")
    parser.add_argument("--show-first-order", action="store_true", help="Print the first-order system.")
    parser.add_argument("--show-state-space", action="store_true", help="Print the state-space system when available.")
    parser.add_argument("--write-graph-json", help="Write the lowered graph dictionary to a JSON file.")
    parser.add_argument("--validate-graph", action="store_true", help="Print graph-validation status.")
    parser.add_argument("--run-sim", dest="run_sim", action="store_true", help="Run simulation stages.")
    parser.add_argument("--skip-sim", dest="run_sim", action="store_false", help="Skip simulation stages.")
    parser.add_argument(
        "--simulink",
        dest="simulink",
        action="store_true",
        help="Build and validate a Simulink model from the lowered graph. Enabled by default.",
    )
    parser.add_argument(
        "--no-simulink",
        dest="simulink",
        action="store_false",
        help="Disable Simulink model generation for parser-only or non-MATLAB runs.",
    )
    parser.add_argument(
        "--simulink-output-dir",
        help=f"Directory for generated Simulink models. Defaults to {DEFAULT_SIMULINK_OUTPUT_DIR}.",
    )
    parser.add_argument("--runtime-json", help="Path to a JSON file overriding parameter values, initial conditions, and time settings.")
    parser.add_argument("--report-json", help="Write a JSON pipeline summary to a file.")
    parser.add_argument(
        "--export-gui-run",
        action="store_true",
        help=f"Export the completed run into {DEFAULT_GUI_REPORT_ROOT} so it can be reopened from the web app.",
    )
    parser.add_argument(
        "--gui-report-root",
        help=f"Directory for saved GUI runs. Defaults to {DEFAULT_GUI_REPORT_ROOT}.",
    )
    parser.set_defaults(run_sim=True)
    parser.set_defaults(expected_linear=None)
    parser.set_defaults(simulink=True)
    args = parser.parse_args()

    input_stem = Path(args.input).stem if args.input else args.equations_name
    verbose_requested = args.verbose or args.verbose_output_dir is not None
    verbose_output_dir = (
        Path(args.verbose_output_dir)
        if args.verbose_output_dir
        else REPORTS_ROOT / "verbose" / input_stem
    )

    engine = None
    temp_equation_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        input_path = args.input
        if args.equations is not None:
            temp_equation_dir = tempfile.TemporaryDirectory(prefix="simulinkcopilot_cli_")
            input_path = str(Path(temp_equation_dir.name) / f"{args.equations_name}.tex")
            Path(input_path).write_text(args.equations, encoding="utf-8")

        runtime_override = None
        if args.runtime_json:
            runtime_override = json.loads(Path(args.runtime_json).read_text(encoding="utf-8"))
        runtime_override = _merge_assignment_group(runtime_override, "parameter_values", args.parameter)
        runtime_override = _merge_assignment_group(runtime_override, "initial_conditions", args.initial)
        runtime_override = _merge_assignment_group(runtime_override, "input_values", args.input_value)
        if args.t_span is not None:
            runtime_override = dict(runtime_override or {})
            runtime_override["t_span"] = [float(args.t_span[0]), float(args.t_span[1])]
        if args.sample_count is not None:
            runtime_override = dict(runtime_override or {})
            runtime_override["sample_count"] = int(args.sample_count)
        if args.expected_linear is not None:
            runtime_override = dict(runtime_override or {})
            runtime_override["expected_linear"] = bool(args.expected_linear)

        if args.sample_count is not None and args.sample_count < 2:
            parser.error("--sample-count must be at least 2.")
        if args.simulink and not args.run_sim:
            parser.error("--skip-sim cannot be combined with default Simulink generation. Use --no-simulink if needed.")
        if args.export_gui_run and not args.simulink:
            parser.error("--export-gui-run requires Simulink generation to be enabled.")

        symbol_config = dict(args.symbol_role)
        classification_mode = args.classification_mode
        if symbol_config and classification_mode == "strict":
            parser.error("--classification-mode strict cannot be combined with --symbol-role.")
        if symbol_config and classification_mode is None:
            classification_mode = "configured"

        if args.simulink and verbose_requested:
            from simulink.engine import start_engine

            engine = start_engine(retries=1, retry_delay_seconds=1.0)

        results = run_pipeline(
            input_path,
            tolerance=args.tolerance,
            run_sim=args.run_sim,
            validate_graph=True,
            run_simulink=args.simulink,
            runtime_override=runtime_override,
            classification_mode=classification_mode,
            symbol_config=symbol_config or None,
            matlab_engine=engine,
            simulink_output_dir=_resolved_simulink_output_dir(args.simulink_output_dir),
        )
        _validate_expected_states(results["extraction"].states, args.state)
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
            from pipeline.verbose_artifacts import write_verbose_artifacts

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

        if args.export_gui_run:
            raw_latex = Path(input_path).read_text(encoding="utf-8")
            gui_export = export_results_to_gui_run(
                results,
                raw_latex=raw_latex,
                gui_report_root=args.gui_report_root,
                symbol_config=symbol_config or None,
                input_values=dict((runtime_override or {}).get("input_values", {})),  # type: ignore[arg-type]
            )
            print("GUI run export:")
            print(f"  run_name: {gui_export['run_name']}")
            print(f"  artifact_dir: {gui_export['artifact_dir']}")
            print(f"  load_url: /?run={gui_export['run_name']}")

        comparison = results["comparison"]
        if args.simulink and results["simulink_validation"] is not None:
            return 0 if results["simulink_validation"]["passes"] else 1
        if comparison is None:
            return 0
        return 0 if comparison["passes"] else 1
    finally:
        if engine is not None:
            engine.quit()
        if temp_equation_dir is not None:
            temp_equation_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
