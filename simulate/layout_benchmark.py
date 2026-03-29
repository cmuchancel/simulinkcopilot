"""Layout-focused benchmark harness for readable Simulink model appearance."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from backend.descriptor_to_simulink import descriptor_to_simulink_model
from backend.graph_to_simulink import graph_to_simulink_model
from backend.matlab_layout_renderer import render_backend_model_with_matlab
from backend.layout_metrics import measure_layout
from backend.layout_renderer import render_system_image
from backend.layout_visual_corrector import VisualRepairConfig
from pipeline.run_pipeline import run_pipeline
from repo_paths import WORKSPACE_ROOT
from simulate.dae_benchmark_suite import DAE_BENCHMARK_CASES
from simulink.engine import start_engine


@dataclass(frozen=True)
class LayoutBenchmarkCase:
    name: str
    category: str
    build_base_model: Callable[[], dict[str, object]]


def _simple_gain_model() -> dict[str, object]:
    return {
        "name": "simple_gain_chain",
        "blocks": {
            "src": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "system": "root",
                "name": "u",
                "params": {"Value": "1"},
                "metadata": {"layout_role": "source", "trace_expression": "u"},
            },
            "gain": {
                "type": "Gain",
                "lib_path": "simulink/Math Operations/Gain",
                "system": "root",
                "name": "gain_k",
                "params": {"Gain": "2"},
                "metadata": {"layout_role": "shared", "layer_hint": 0, "trace_expression": "2*u"},
            },
            "out": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "root",
                "name": "y",
                "params": {"Port": 1},
                "metadata": {"layout_role": "output", "trace_expression": "y"},
            },
        },
        "connections": [
            {"system": "root", "src_block": "src", "src_port": "1", "dst_block": "gain", "dst_port": "1", "label": "u"},
            {"system": "root", "src_block": "gain", "src_port": "1", "dst_block": "out", "dst_port": "1", "label": "2*u"},
        ],
        "outputs": [{"name": "y", "block": "out", "port": "1"}],
        "metadata": {"benchmark_case": "simple_gain_chain"},
    }


def _compile_example_model(example_name: str) -> dict[str, object]:
    result = run_pipeline(
        WORKSPACE_ROOT / "examples" / example_name,
        run_sim=False,
        validate_graph=True,
        run_simulink=False,
    )
    graph = result["graph"]
    runtime = result["runtime"]
    if graph is None:
        raise RuntimeError(f"Expected graph artifact for {example_name}.")
    extraction_inputs = {name: 0.0 for name in result["extraction"].inputs}
    extraction_inputs.update(runtime.get("input_values", {}))
    return graph_to_simulink_model(
        graph,
        name=example_name.replace(".tex", "_layout"),
        state_names=list(result["extraction"].states),
        parameter_values=runtime["parameter_values"],
        input_values=extraction_inputs,
        initial_conditions=runtime["initial_conditions"],
        model_params={},
        layout_mode="none",
    )


def _compile_dae_case(case_index: int) -> dict[str, object]:
    case = DAE_BENCHMARK_CASES[case_index]
    with tempfile.TemporaryDirectory() as temp_dir:
        case_path = Path(temp_dir) / f"{case.name}.tex"
        case_path.write_text(case.latex, encoding="utf-8")
        result = run_pipeline(
            case_path,
            run_sim=False,
            validate_graph=True,
            run_simulink=False,
            runtime_override={
                "parameter_values": dict(case.parameter_values),
                "initial_conditions": dict(case.initial_conditions),
                "input_values": dict(case.input_values),
                "t_span": case.t_span,
                "sample_count": case.sample_count,
            },
            classification_mode=case.classification_mode,
            symbol_config=case.symbol_config,
        )
    if case.simulink_lowering_kind == "descriptor":
        descriptor_system = result["descriptor_system"]
        if descriptor_system is None:
            raise RuntimeError(f"Expected descriptor artifact for {case.name}.")
        consistent = result["consistent_initialization"]
        dae_system = result["dae_system"]
        return descriptor_to_simulink_model(
            descriptor_system,
            name=f"{case.name}_layout",
            parameter_values=dict(case.parameter_values),
            input_values=dict(case.input_values),
            differential_initial_conditions=consistent.differential_initial_conditions,
            algebraic_initial_conditions=consistent.algebraic_initial_conditions,
            output_names=[*dae_system.differential_states, *dae_system.algebraic_variables],
            layout_mode="none",
        )
    graph = result["graph"]
    if graph is None:
        raise RuntimeError(f"Expected graph artifact for {case.name}.")
    consistent = result["consistent_initialization"]
    dae_system = result["dae_system"]
    return graph_to_simulink_model(
        graph,
        name=f"{case.name}_layout",
        state_names=[*dae_system.differential_states, *dae_system.algebraic_variables],
        parameter_values=dict(case.parameter_values),
        input_values=dict(case.input_values),
        initial_conditions=consistent.differential_initial_conditions,
        algebraic_initial_conditions=consistent.algebraic_initial_conditions,
        layout_mode="none",
    )


BENCHMARK_CASES: tuple[LayoutBenchmarkCase, ...] = (
    LayoutBenchmarkCase("simple_gain_chain", "Case 1 - Source / Gain / Outport", _simple_gain_model),
    LayoutBenchmarkCase("mass_spring_damper", "Case 2 - First-order ODE", lambda: _compile_example_model("mass_spring_damper.tex")),
    LayoutBenchmarkCase("third_order_system", "Case 3 - Explicit integrator chain", lambda: _compile_example_model("third_order_system.tex")),
    LayoutBenchmarkCase("coupled_system", "Case 4 - Branched feedforward", lambda: _compile_example_model("coupled_system.tex")),
    LayoutBenchmarkCase("driven_oscillator", "Case 5 - Simple feedback controller", lambda: _compile_example_model("driven_oscillator.tex")),
    LayoutBenchmarkCase("three_mass_coupled", "Case 6 - Nested subsystem / imports / exports", lambda: _compile_example_model("three_mass_coupled.tex")),
    LayoutBenchmarkCase("nonlinear_pendulum", "Case 7 - Multi-state coupled nonlinear system", lambda: _compile_example_model("nonlinear_pendulum.tex")),
    LayoutBenchmarkCase("nonlinear_preserved_cubic_constraint", "Case 8 - Preserved semi-explicit DAE", lambda: _compile_dae_case(2)),
    LayoutBenchmarkCase("linear_descriptor_capable_balance", "Case 9 - Descriptor-capable DAE", lambda: _compile_dae_case(1)),
    LayoutBenchmarkCase("two_mass_coupled", "Case 10 - Real repo example", lambda: _compile_example_model("two_mass_coupled.tex")),
)


def _render_case_layout(
    model: dict[str, object],
    *,
    case_dir: Path,
    variant: str,
    render_backend: Literal["matlab", "proxy"],
    matlab_engine=None,
) -> dict[str, object]:
    image_dir = case_dir / variant
    image_dir.mkdir(parents=True, exist_ok=True)
    if render_backend == "matlab":
        if matlab_engine is None:
            raise RuntimeError("MATLAB render backend requested without a MATLAB engine.")
        rendered_model = render_backend_model_with_matlab(
            matlab_engine,
            model,
            output_dir=image_dir,
        )
        return rendered_model.renders

    rendered: dict[str, object] = {}
    systems = ["root", *sorted(block_id for block_id, block_spec in model["blocks"].items() if block_spec["type"] == "Subsystem" and block_spec["system"] == "root")]
    for system in systems:
        image = render_system_image(
            model,
            system=system,
            output_path=image_dir / f"{system}.png",
            title=f"{case_dir.name}:{variant}:{system}",
        )
        rendered[system] = image.path
    return rendered


def run_layout_benchmark(
    *,
    output_dir: str | Path | None = None,
    visual_repair: bool = False,
    visual_repair_config: VisualRepairConfig | None = None,
    openai_client=None,
    render_backend: Literal["matlab", "proxy"] = "matlab",
    matlab_engine=None,
) -> dict[str, object]:
    """Generate readability benchmark artifacts for legacy, deterministic, and visual layouts."""
    benchmark_root = Path(output_dir or (WORKSPACE_ROOT / "layout_bench"))
    benchmark_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    owns_engine = False
    active_engine = matlab_engine

    from backend.layout import apply_deterministic_layout, apply_legacy_layout
    from backend.layout_visual_corrector import apply_visual_repair

    if render_backend == "matlab" and active_engine is None:
        active_engine = start_engine(retries=1, retry_delay_seconds=1.0)
        owns_engine = True

    try:
        for case in BENCHMARK_CASES:
            case_dir = benchmark_root / case.name
            case_dir.mkdir(parents=True, exist_ok=True)
            base_model = case.build_base_model()
            legacy_model = apply_legacy_layout(base_model)
            deterministic_model = apply_deterministic_layout(base_model)
            variants = {
                "legacy": legacy_model,
                "deterministic": deterministic_model,
            }
            if visual_repair:
                visual_model = apply_visual_repair(
                    deterministic_model,
                    config=visual_repair_config,
                    client=openai_client,
                )
                variants["deterministic_visual"] = visual_model
            for child in case_dir.iterdir():
                if child.is_dir() and child.name not in variants:
                    shutil.rmtree(child)
            case_payload = {"name": case.name, "category": case.category, "render_backend": render_backend, "variants": {}}
            for variant_name, variant_model in variants.items():
                metrics = measure_layout(variant_model).to_dict()
                rendered = _render_case_layout(
                    variant_model,
                    case_dir=case_dir,
                    variant=variant_name,
                    render_backend=render_backend,
                    matlab_engine=active_engine,
                )
                case_payload["variants"][variant_name] = {"metrics": metrics, "renders": rendered}
            (case_dir / "summary.json").write_text(json.dumps(case_payload, indent=2), encoding="utf-8")
            rows.append(case_payload)

        report = {"render_backend": render_backend, "cases": rows}
        (benchmark_root / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

        markdown_lines = ["# Layout Benchmark", "", f"Render backend: `{render_backend}`", ""]
        for case in rows:
            markdown_lines.append(f"## {case['name']}")
            markdown_lines.append(case["category"])
            for variant_name, variant_payload in case["variants"].items():
                metrics = variant_payload["metrics"]
                markdown_lines.append(
                    f"- `{variant_name}`: score={metrics['score']}, crossings={metrics['connection_crossing_count']}, "
                    f"reverse_flow={metrics['reverse_flow_edge_count']}, bends={metrics['bend_count']}, pages={metrics['estimated_page_count']}"
                )
            markdown_lines.append("")
        (benchmark_root / "summary.md").write_text("\n".join(markdown_lines), encoding="utf-8")
        return report
    finally:
        if owns_engine and active_engine is not None:
            active_engine.quit()
