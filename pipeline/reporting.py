"""Reporting helpers for pipeline results and CLI output."""

from __future__ import annotations

import json

import sympy

from ir.equation_dict import (
    equation_to_string,
    expression_from_dict,
    expression_to_sympy,
    matrix_from_dict,
)


def summarize_pipeline_results(results: dict[str, object]) -> dict[str, object]:
    """Return a JSON-serializable summary for reporting and CLI output."""
    state_space = results["state_space"]
    comparison = results["comparison"]
    graph = results["graph"]
    simulink_result = results["simulink_result"]
    simulink_validation = results["simulink_validation"]
    explicit_form = results["explicit_form"]
    normalized_problem = results.get("normalized_problem")
    return {
        "source_path": results["source_path"],
        "source_type": results.get("source_type", "latex"),
        "normalized_problem": None if normalized_problem is None else normalized_problem.to_dict(),  # type: ignore[union-attr]
        "equations": [equation_to_string(equation) for equation in results["equations"]],  # type: ignore[index]
        "equation_dicts": results["equation_dicts"],
        "extraction": results["extraction"].to_dict(),  # type: ignore[union-attr]
        "solved_derivatives": [item.to_dict() for item in results["solved_derivatives"]],  # type: ignore[index]
        "dae_classification": results["dae_classification"],
        "dae_system": results["dae_system"].to_dict(),  # type: ignore[union-attr]
        "descriptor_system": results["descriptor_system"],
        "consistent_initialization": results["consistent_initialization"].to_dict(),  # type: ignore[union-attr]
        "dae_validation": results["dae_validation"],
        "first_order": results["first_order"],
        "explicit_form": None if explicit_form is None else {
            "form": explicit_form["form"],  # type: ignore[index]
            "rhs": {
                state: sympy.sstr(expr)
                for state, expr in explicit_form["rhs"].items()  # type: ignore[index]
            },
        },
        "linearity": {
            "is_linear": results["linearity"]["is_linear"],  # type: ignore[index]
            "offending_entries": results["linearity"]["offending_entries"],  # type: ignore[index]
        },
        "state_space": state_space,
        "graph": None if graph is None else {
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


def print_results(
    results: dict[str, object],
    *,
    show_ir: bool = False,
    show_first_order: bool = False,
    show_state_space: bool = False,
    show_graph_validation: bool = False,
) -> None:
    """Print a human-readable pipeline summary for CLI use."""
    equations = results["equations"]
    extraction = results["extraction"]
    solved_derivatives = results["solved_derivatives"]
    dae_classification = results["dae_classification"]
    first_order = results["first_order"]
    state_space = results["state_space"]
    descriptor_system = results["descriptor_system"]
    comparison = results["comparison"]
    graph = results["graph"]
    simulink_result = results["simulink_result"]
    simulink_validation = results["simulink_validation"]
    dae_validation = results["dae_validation"]

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

    print("DAE classification:")
    print(json.dumps(dae_classification, indent=2))

    print("First-order system:")
    if first_order is None:
        print("  unavailable: descriptor-only Simulink path")
    else:
        for entry in first_order["state_equations"]:  # type: ignore[index]
            rhs = sympy.sstr(expression_to_sympy(expression_from_dict(entry["rhs"])))
            print(f"  d/dt {entry['state']} = {rhs}")

    print("Linearity:")
    print(f"  is_linear: {results['linearity']['is_linear']}")  # type: ignore[index]

    if state_space is not None:
        print("State-space matrices:")
        for name in ["A", "B", "offset"]:
            print(f"  {name} = {matrix_from_dict(state_space[name])}")  # type: ignore[index]
    else:
        print("State-space matrices:")
        print("  unavailable: nonlinear explicit system")

    print("Descriptor system:")
    if descriptor_system is None:
        print("  unavailable: descriptor form unavailable for this system")
    else:
        for name in ["E", "A", "B", "offset"]:
            print(f"  {name} = {matrix_from_dict(descriptor_system[name])}")  # type: ignore[index]

    print("Graph summary:")
    if graph is None:
        print("  unavailable: descriptor-only Simulink path")
    else:
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
        if simulink_validation is None:
            print("  validation: unavailable")
        else:
            if "vs_ode" in simulink_validation:
                print(f"  vs_ode_rmse: {simulink_validation['vs_ode']['rmse']}")
                print(f"  vs_ode_max_abs_error: {simulink_validation['vs_ode']['max_abs_error']}")
                if simulink_validation["vs_state_space"] is not None:
                    print(f"  vs_state_space_rmse: {simulink_validation['vs_state_space']['rmse']}")
                    print(f"  vs_state_space_max_abs_error: {simulink_validation['vs_state_space']['max_abs_error']}")
            if "vs_dae_python" in simulink_validation:
                print(f"  vs_dae_python_rmse: {simulink_validation['vs_dae_python']['rmse']}")
                print(f"  vs_dae_python_max_abs_error: {simulink_validation['vs_dae_python']['max_abs_error']}")
            print(f"  passes: {simulink_validation['passes']}")

    if dae_validation is not None:
        print("DAE validation:")
        print(json.dumps(dae_validation, indent=2))


# Backward-compatible alias for the long-standing CLI helper name.
_print_results = print_results
