"""Verbose artifact generation for CLI pipeline runs."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import tempfile

_MPLCONFIGDIR = Path(tempfile.gettempdir()) / "simulinkcopilot_mplconfig"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))
_XDG_CACHE_HOME = Path(tempfile.gettempdir()) / "simulinkcopilot_cache"
_XDG_CACHE_HOME.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(_XDG_CACHE_HOME))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sympy

from ir.equation_dict import (
    equation_to_dict,
    equation_to_residual,
    equation_to_string,
    expression_from_dict,
    expression_to_sympy,
    matrix_from_dict,
    matrix_to_dict,
)
from ir.expression_nodes import (
    AddNode,
    DerivativeNode,
    DivNode,
    EquationNode,
    ExpressionNode,
    FunctionNode,
    MulNode,
    NegNode,
    NumberNode,
    PowNode,
    SymbolNode,
)
from latex_frontend.normalize import normalize_latex
from latex_frontend.tokenizer import Token, tokenize
from pipeline.run_pipeline import summarize_pipeline_results


def _matlab_string_literal(value: str) -> str:
    return value.replace("'", "''")


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _serialize_parse_node(node: EquationNode | ExpressionNode) -> dict[str, object]:
    """Serialize parser dataclasses while preserving node-type labels."""
    if isinstance(node, NumberNode):
        return {"type": "NumberNode", "value": node.value}
    if isinstance(node, SymbolNode):
        return {"type": "SymbolNode", "name": node.name}
    if isinstance(node, DerivativeNode):
        return {"type": "DerivativeNode", "base": node.base, "order": node.order}
    if isinstance(node, AddNode):
        return {"type": "AddNode", "args": [_serialize_parse_node(arg) for arg in node.args]}
    if isinstance(node, MulNode):
        return {"type": "MulNode", "args": [_serialize_parse_node(arg) for arg in node.args]}
    if isinstance(node, DivNode):
        return {
            "type": "DivNode",
            "numerator": _serialize_parse_node(node.numerator),
            "denominator": _serialize_parse_node(node.denominator),
        }
    if isinstance(node, PowNode):
        return {
            "type": "PowNode",
            "base": _serialize_parse_node(node.base),
            "exponent": _serialize_parse_node(node.exponent),
        }
    if isinstance(node, NegNode):
        return {"type": "NegNode", "operand": _serialize_parse_node(node.operand)}
    if isinstance(node, FunctionNode):
        payload: dict[str, object] = {
            "type": "FunctionNode",
            "function": node.function,
        }
        if len(node.args) == 1:
            payload["operand"] = _serialize_parse_node(node.operand)
        else:
            payload["args"] = [_serialize_parse_node(arg) for arg in node.args]
        return payload
    if isinstance(node, EquationNode):
        return {
            "type": "EquationNode",
            "lhs": _serialize_parse_node(node.lhs),
            "rhs": _serialize_parse_node(node.rhs),
        }
    raise TypeError(f"Unsupported parser node type: {type(node).__name__}")


def _serialize_tokens(tokens: list[Token]) -> list[dict[str, object]]:
    """Serialize the tokenizer output for verbose artifacts."""
    return [asdict(token) for token in tokens]


def _serialize_explicit_form(explicit_form: dict[str, object]) -> dict[str, object]:
    """Convert explicit-form metadata into a JSON-safe representation."""
    return {
        "form": explicit_form["form"],
        "states": list(explicit_form["states"]),  # type: ignore[arg-type]
        "inputs": list(explicit_form["inputs"]),  # type: ignore[arg-type]
        "parameters": list(explicit_form["parameters"]),  # type: ignore[arg-type]
        "rhs": {
            state: sympy.sstr(expr)
            for state, expr in explicit_form["rhs"].items()  # type: ignore[index]
        },
    }


def _serialize_linearity(linearity: dict[str, object]) -> dict[str, object]:
    """Convert linearity analysis into a JSON-safe representation."""
    return {
        "is_linear": bool(linearity["is_linear"]),
        "A": matrix_to_dict(linearity["A"]),  # type: ignore[arg-type]
        "B": matrix_to_dict(linearity["B"]),  # type: ignore[arg-type]
        "offset": matrix_to_dict(linearity["offset"]),  # type: ignore[arg-type]
        "offending_entries": list(linearity["offending_entries"]),  # type: ignore[arg-type]
    }


def _serialize_runtime(results: dict[str, object]) -> dict[str, object]:
    """Write the runtime inputs in a deterministic, inspectable form."""
    runtime = results["runtime"]
    input_names = list(results["first_order"]["inputs"])  # type: ignore[index]
    t_eval = runtime["t_eval"]  # type: ignore[index]
    input_function = runtime["input_function"]  # type: ignore[index]
    input_signals = {
        name: {
            "time": [float(time) for time in t_eval.tolist()],
            "values": [float(input_function(float(time)).get(name, 0.0)) for time in t_eval],
        }
        for name in input_names
    }
    return {
        "parameter_values": dict(runtime["parameter_values"]),  # type: ignore[arg-type]
        "initial_conditions": dict(runtime["initial_conditions"]),  # type: ignore[arg-type]
        "input_signals": input_signals,
        "t_span": [float(runtime["t_span"][0]), float(runtime["t_span"][1])],  # type: ignore[index]
        "t_eval": [float(time) for time in t_eval.tolist()],
        "sample_count": int(len(t_eval)),
        "expected_linear": bool(runtime["expected_linear"]),
    }


def _first_order_text(results: dict[str, object]) -> str:
    """Render the first-order system in a readable text form."""
    lines = [
        f"d/dt {entry['state']} = {expression_to_sympy(expression_from_dict(entry['rhs']))}"
        for entry in results["first_order"]["state_equations"]  # type: ignore[index]
    ]
    return "\n".join(lines) + "\n"


def _state_space_text(results: dict[str, object]) -> str:
    """Render the state-space matrices or a nonlinear note."""
    state_space = results["state_space"]
    if state_space is None:
        return "unavailable: nonlinear explicit system\n"
    return "\n".join(
        [
            f"A = {matrix_from_dict(state_space['A'])}",
            f"B = {matrix_from_dict(state_space['B'])}",
            f"C = {matrix_from_dict(state_space['C'])}",
            f"D = {matrix_from_dict(state_space['D'])}",
            f"offset = {matrix_from_dict(state_space['offset'])}",
        ]
    ) + "\n"


def _artifact_link(relative_path: str) -> str:
    """Render a local markdown link for an artifact inside the verbose bundle."""
    return f"[{relative_path}]({relative_path})"


def _code_block(language: str, content: str) -> str:
    """Wrap content in a fenced code block."""
    return f"```{language}\n{content.rstrip()}\n```\n"


def _walkthrough_markdown(
    *,
    title: str,
    source_text: str,
    normalized_text: str,
    parsed_equations: list[str],
    residuals: list[str],
    solved_derivatives: list[str],
    first_order_text: str,
    state_space_text: str,
    token_stream: list[dict[str, object]],
    parsed_trees: list[dict[str, object]],
    equation_dicts: list[dict[str, object]],
    extraction_dict: dict[str, object],
    explicit_form: dict[str, object],
    linearity: dict[str, object],
    runtime_payload: dict[str, object],
    graph: dict[str, object],
    simulink_model: dict[str, object] | None,
    comparison: dict[str, object] | None,
    simulink_validation: dict[str, object] | None,
    files: dict[str, str | None],
) -> str:
    """Generate a narrative markdown walkthrough for the verbose bundle."""
    graph_summary = {
        "node_count": len(graph["nodes"]),  # type: ignore[index]
        "edge_count": len(graph["edges"]),  # type: ignore[index]
        "ops": sorted({node["op"] for node in graph["nodes"]}),  # type: ignore[index]
    }
    lines = [
        f"# Pipeline Walkthrough: {title}",
        "",
        "This walkthrough follows the deterministic pipeline stage by stage.",
        "",
        "## 1. Input equations",
        f"This is what you inputted. Artifact: {_artifact_link(Path(files['input_equations']).name)}",
        "",
        _code_block("latex", source_text),
        "## 2. Normalized LaTeX",
        f"This is what we converted it to before tokenization. Artifact: {_artifact_link(Path(files['normalized_equations']).name)}",
        "",
        _code_block("latex", normalized_text),
        "## 3. Token stream",
        f"This is the flat token stream emitted by the tokenizer. Artifact: {_artifact_link(Path(files['token_stream']).name)}",
        "",
        _code_block("json", json.dumps(token_stream, indent=2)),
        "## 4. Parse tree",
        "This is the parser tree over the normalized equations.",
        f"Artifacts: {_artifact_link(Path(files['parsed_trees']).name)}, {_artifact_link(Path(files['parsed_equations']).name)}",
        "",
        _code_block("json", json.dumps(parsed_trees, indent=2)),
        "## 5. Parsed equations",
        "This is the deterministic SymPy-style rendering of the parsed equations.",
        "",
        _code_block("text", "\n".join(parsed_equations)),
        "## 6. Canonical equation dictionaries",
        f"This is the canonical dict IR. Artifact: {_artifact_link(Path(files['equation_dicts']).name)}",
        "",
        _code_block("json", json.dumps(equation_dicts, indent=2)),
        "## 7. Symbol extraction",
        f"This is how the compiler classified states, inputs, parameters, and derivative orders. Artifact: {_artifact_link(Path(files['extraction']).name)}",
        "",
        _code_block("json", json.dumps(extraction_dict, indent=2)),
        "## 8. Residual equations",
        f"This is the residual form `lhs - rhs = 0`. Artifact: {_artifact_link(Path(files['residual_equations']).name)}",
        "",
        _code_block("text", "\n".join(residuals)),
        "## 9. Solved highest derivatives",
        "This is what the algebra solver isolated as explicit highest-order derivative equations.",
        f"Artifacts: {_artifact_link(Path(files['solved_derivatives']).name)}, {_artifact_link(Path(files['solved_derivative_dicts']).name)}",
        "",
        _code_block("text", "\n".join(solved_derivatives)),
        "## 10. First-order system",
        "This is the first-order state evolution system derived from the solved equations.",
        f"Artifacts: {_artifact_link(Path(files['first_order']).name)}, {_artifact_link(Path(files['first_order_system']).name)}",
        "",
        _code_block("text", first_order_text),
        "## 11. Explicit system form",
        f"This is the explicit state-to-RHS map used downstream. Artifact: {_artifact_link(Path(files['explicit_form']).name)}",
        "",
        _code_block("json", json.dumps(explicit_form, indent=2)),
        "## 12. Linearity analysis",
        f"This records whether the first-order system is linear in states and inputs. Artifact: {_artifact_link(Path(files['linearity']).name)}",
        "",
        _code_block("json", json.dumps(linearity, indent=2)),
        "## 13. State-space form",
        f"This is the linear state-space form when available. Artifacts: {_artifact_link(Path(files['state_space']).name)}"
        + (
            f", {_artifact_link(Path(files['state_space_json']).name)}"
            if files["state_space_json"] is not None
            else ""
        ),
        "",
        _code_block("text", state_space_text),
        "## 14. Lowered graph",
        f"This is the deterministic graph lowered from the first-order system. Artifact: {_artifact_link(Path(files['graph']).name)}",
        "",
        _code_block("json", json.dumps(graph_summary, indent=2)),
        "## 15. Simulink model dictionary",
    ]

    if simulink_model is None or files["simulink_model_dict"] is None:
        lines.extend(
            [
                "Simulink model generation was not requested, so there is no Simulink model dictionary in this bundle.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"This is the Simulink-ready backend model dictionary. Artifact: {_artifact_link(Path(files['simulink_model_dict']).name)}",
                "",
                _code_block("json", json.dumps(simulink_model, indent=2)),
            ]
        )

    lines.extend(
        [
            "## 16. Runtime context",
            f"This is the runtime configuration used for simulation and validation. Artifact: {_artifact_link(Path(files['runtime']).name)}",
            "",
            _code_block("json", json.dumps(runtime_payload, indent=2)),
            "## 17. Validation outputs",
        ]
    )
    if comparison is not None and files["comparison"] is not None:
        lines.extend(
            [
                f"ODE/state-space comparison artifact: {_artifact_link(Path(files['comparison']).name)}",
                "",
                _code_block("json", json.dumps(comparison, indent=2)),
            ]
        )
    if simulink_validation is not None and files["simulink_validation"] is not None:
        lines.extend(
            [
                f"Simulink validation artifact: {_artifact_link(Path(files['simulink_validation']).name)}",
                "",
                _code_block("json", json.dumps(simulink_validation, indent=2)),
            ]
        )
    simulation_plot = files.get("simulation_plot")
    simulink_model_image = files.get("simulink_model_image")
    simulink_model_note = files.get("simulink_model_note")
    if simulation_plot is not None:
        lines.append(f"Simulation plot artifact: {_artifact_link(Path(simulation_plot).name)}")
    if simulink_model_image is not None:
        lines.append(f"Simulink model image artifact: {_artifact_link(Path(simulink_model_image).name)}")
    if simulink_model_note is not None:
        lines.append(f"Simulink model note artifact: {_artifact_link(Path(simulink_model_note).name)}")
    lines.extend(
        [
            "",
            "## 18. Summary",
            f"Final summary artifact: {_artifact_link(Path(files['summary']).name)}",
            "",
            "This is the compact machine-readable summary for the whole run.",
            "",
        ]
    )
    return "\n".join(lines)


def _simulation_series(results: dict[str, object]) -> list[tuple[str, dict[str, object], str]]:
    series: list[tuple[str, dict[str, object], str]] = []
    if results["ode_result"] is not None:
        series.append(("ODE", results["ode_result"], "-"))
    if results["state_space_result"] is not None:
        series.append(("State-space", results["state_space_result"], "--"))
    if results["simulink_result"] is not None:
        series.append(("Simulink", results["simulink_result"], ":"))
    return series


def _render_simulation_plot(results: dict[str, object], output_path: Path) -> str | None:
    series = _simulation_series(results)
    if not series:
        return None

    state_names = list(series[0][1]["state_names"])  # type: ignore[index]
    state_count = len(state_names)
    columns = 1 if state_count <= 2 else 2
    rows = math.ceil(state_count / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(10, 3.5 * rows), squeeze=False)

    for index, state_name in enumerate(state_names):
        axis = axes[index // columns][index % columns]
        for label, result, style in series:
            axis.plot(
                result["t"],  # type: ignore[index]
                result["states"][:, index],  # type: ignore[index]
                style,
                linewidth=1.5,
                label=label,
            )
        axis.set_title(state_name)
        axis.set_xlabel("t")
        axis.grid(True, alpha=0.3)
        axis.legend()

    for index in range(state_count, rows * columns):
        axes[index // columns][index % columns].axis("off")

    figure.tight_layout()
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def _render_simulink_model_image(eng, model_name: str, output_path: Path) -> str:
    escaped_model = _matlab_string_literal(model_name)
    escaped_output = _matlab_string_literal(str(output_path.resolve()))
    eng.open_system(model_name, nargout=0)
    eng.eval(f"set_param('{escaped_model}', 'ZoomFactor', 'FitSystem');", nargout=0)
    eng.eval(f"print('-s{escaped_model}', '-dpng', '{escaped_output}')", nargout=0)
    return str(output_path)


def write_verbose_artifacts(
    results: dict[str, object],
    output_dir: str | Path,
    *,
    matlab_engine=None,
) -> dict[str, object]:
    """Write a verbose artifact bundle for a pipeline run."""
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    source_path = Path(str(results["source_path"]))
    source_text = source_path.read_text(encoding="utf-8")
    normalized_text = normalize_latex(source_text)
    token_stream = tokenize(normalized_text)
    parsed_equations = [equation_to_string(equation) for equation in results["equations"]]  # type: ignore[index]
    parsed_trees = [_serialize_parse_node(equation) for equation in results["equations"]]  # type: ignore[index]
    equation_dicts = [equation_to_dict(equation) for equation in results["equations"]]  # type: ignore[index]
    residuals = [sympy.sstr(equation_to_residual(equation)) for equation in results["equations"]]  # type: ignore[index]
    extraction_dict = results["extraction"].to_dict()  # type: ignore[union-attr]
    solved_derivatives = [equation_to_string(item.equation) for item in results["solved_derivatives"]]  # type: ignore[index]
    solved_derivative_dicts = [item.to_dict() for item in results["solved_derivatives"]]  # type: ignore[index]
    first_order_text = _first_order_text(results)
    explicit_form = _serialize_explicit_form(results["explicit_form"])  # type: ignore[arg-type]
    linearity = _serialize_linearity(results["linearity"])  # type: ignore[arg-type]
    state_space_text = _state_space_text(results)
    runtime_payload = _serialize_runtime(results)

    intermediate_text = "\n".join(
        [
            "Normalized equations:",
            normalized_text,
            "",
            "Parsed equations:",
            *[f"  {entry}" for entry in parsed_equations],
            "",
            "Residual equations:",
            *[f"  {entry}" for entry in residuals],
            "",
            "Solved derivatives:",
            *[f"  {entry}" for entry in solved_derivatives],
            "",
            "First-order system:",
            first_order_text.rstrip(),
        ]
    ) + "\n"

    files: dict[str, str | None] = {}
    files["input_equations"] = _write_text(output_root / "input_equations.tex", source_text)
    files["normalized_equations"] = _write_text(output_root / "normalized_equations.tex", normalized_text + "\n")
    files["token_stream"] = _write_json(output_root / "token_stream.json", _serialize_tokens(token_stream))
    files["parsed_trees"] = _write_json(output_root / "parsed_trees.json", parsed_trees)
    files["parsed_equations"] = _write_text(output_root / "parsed_equations.txt", "\n".join(parsed_equations) + "\n")
    files["equation_dicts"] = _write_json(output_root / "equation_dicts.json", equation_dicts)
    files["extraction"] = _write_json(output_root / "extraction.json", extraction_dict)
    files["residual_equations"] = _write_text(output_root / "residual_equations.txt", "\n".join(residuals) + "\n")
    files["solved_derivatives"] = _write_text(output_root / "solved_derivatives.txt", "\n".join(solved_derivatives) + "\n")
    files["solved_derivative_dicts"] = _write_json(output_root / "solved_derivatives.json", solved_derivative_dicts)
    files["first_order"] = _write_text(output_root / "first_order_system.txt", first_order_text)
    files["first_order_system"] = _write_json(output_root / "first_order_system.json", results["first_order"])
    files["explicit_form"] = _write_json(output_root / "explicit_form.json", explicit_form)
    files["linearity"] = _write_json(output_root / "linearity.json", linearity)
    files["intermediate_equations"] = _write_text(output_root / "intermediate_equations.txt", intermediate_text)
    files["state_space_json"] = (
        _write_json(output_root / "state_space.json", results["state_space"])
        if results["state_space"] is not None
        else None
    )
    files["state_space"] = _write_text(output_root / "state_space.txt", state_space_text)
    files["graph"] = _write_json(output_root / "graph.json", results["graph"])
    files["runtime"] = _write_json(output_root / "runtime.json", runtime_payload)
    files["comparison"] = (
        _write_json(output_root / "comparison.json", results["comparison"])
        if results["comparison"] is not None
        else None
    )
    files["simulink_model_dict"] = (
        _write_json(output_root / "simulink_model.json", results["simulink_model"])
        if results["simulink_model"] is not None
        else None
    )
    files["simulink_validation"] = (
        _write_json(output_root / "simulink_validation.json", results["simulink_validation"])
        if results["simulink_validation"] is not None
        else None
    )
    files["summary"] = _write_json(output_root / "summary.json", summarize_pipeline_results(results))
    files["simulation_plot"] = _render_simulation_plot(results, output_root / "simulation_plot.png")

    files["simulink_model_image"] = None
    files["simulink_model_note"] = None

    simulink_result = results["simulink_result"]
    if simulink_result is not None and matlab_engine is not None:
        try:
            files["simulink_model_image"] = _render_simulink_model_image(
                matlab_engine,
                str(simulink_result["model_name"]),
                output_root / "simulink_model.png",
            )
            files["simulink_model_note"] = None
        except Exception as exc:  # pragma: no cover - environment dependent
            files["simulink_model_image"] = None
            files["simulink_model_note"] = _write_text(
                output_root / "simulink_model_note.txt",
                f"Failed to export Simulink model image: {exc}\n",
            )
    else:
        files["simulink_model_note"] = _write_text(
            output_root / "simulink_model_note.txt",
            "Simulink model image unavailable because the Simulink backend was not requested.\n",
        )

    section_specs = [
        ("input_equations", "Input equations"),
        ("normalized_equations", "Normalized LaTeX"),
        ("token_stream", "Token stream"),
        ("parsed_trees", "Parse tree"),
        ("parsed_equations", "Parsed equations"),
        ("equation_dicts", "Canonical equation dicts"),
        ("extraction", "Symbol extraction"),
        ("residual_equations", "Residual equations"),
        ("solved_derivatives", "Solved highest derivatives"),
        ("solved_derivative_dicts", "Solved derivative dicts"),
        ("first_order", "First-order system"),
        ("first_order_system", "First-order system JSON"),
        ("explicit_form", "Explicit system form"),
        ("linearity", "Linearity analysis"),
        ("state_space", "State-space text"),
        ("state_space_json", "State-space JSON"),
        ("graph", "Lowered graph"),
        ("simulink_model_dict", "Simulink model dictionary"),
        ("runtime", "Runtime context"),
        ("comparison", "Comparison metrics"),
        ("simulink_validation", "Simulink validation"),
        ("summary", "Summary"),
        ("simulation_plot", "Simulation plot"),
        ("simulink_model_image", "Simulink model image"),
        ("simulink_model_note", "Simulink model note"),
    ]
    section_order = [
        {
            "key": key,
            "title": title,
            "relative_path": Path(path).name,
        }
        for key, title in section_specs
        if (path := files.get(key)) is not None
    ]
    files["walkthrough"] = _write_text(
        output_root / "walkthrough.md",
        _walkthrough_markdown(
            title=source_path.stem,
            source_text=source_text,
            normalized_text=normalized_text,
            parsed_equations=parsed_equations,
            residuals=residuals,
            solved_derivatives=solved_derivatives,
            first_order_text=first_order_text,
            state_space_text=state_space_text,
            token_stream=_serialize_tokens(token_stream),
            parsed_trees=parsed_trees,
            equation_dicts=equation_dicts,
            extraction_dict=extraction_dict,
            explicit_form=explicit_form,
            linearity=linearity,
            runtime_payload=runtime_payload,
            graph=results["graph"],  # type: ignore[arg-type]
            simulink_model=results["simulink_model"],  # type: ignore[arg-type]
            comparison=results["comparison"],  # type: ignore[arg-type]
            simulink_validation=results["simulink_validation"],  # type: ignore[arg-type]
            files=files,
        ),
    )
    section_order.append(
        {
            "key": "walkthrough",
            "title": "Walkthrough markdown",
            "relative_path": Path(files["walkthrough"]).name,  # type: ignore[arg-type]
        }
    )

    manifest = {
        "output_dir": str(output_root),
        "files": files,
        "section_order": section_order,
    }
    _write_json(output_root / "artifact_manifest.json", manifest)
    return manifest
