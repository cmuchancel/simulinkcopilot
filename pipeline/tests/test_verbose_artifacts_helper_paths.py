from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ir.expression_nodes import AddNode, DivNode, FunctionNode, NegNode, NumberNode, PowNode, SymbolNode
from pipeline import verbose_artifacts as verbose_module


class _FakeMatlabEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def open_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("open_system", name, nargout))

    def eval(self, expression: str, nargout: int = 0) -> None:
        self.calls.append(("eval", expression, nargout))


def test_verbose_artifact_helper_serializers_cover_remaining_node_types() -> None:
    assert verbose_module._matlab_string_literal("a'b") == "a''b"
    assert verbose_module._serialize_parse_node(NumberNode(2)) == {"type": "NumberNode", "value": 2}
    assert verbose_module._serialize_parse_node(SymbolNode("x")) == {"type": "SymbolNode", "name": "x"}
    assert verbose_module._serialize_parse_node(
        DivNode(SymbolNode("u"), SymbolNode("m"))
    ) == {
        "type": "DivNode",
        "numerator": {"type": "SymbolNode", "name": "u"},
        "denominator": {"type": "SymbolNode", "name": "m"},
    }
    assert verbose_module._serialize_parse_node(
        PowNode(SymbolNode("x"), NumberNode(2))
    ) == {
        "type": "PowNode",
        "base": {"type": "SymbolNode", "name": "x"},
        "exponent": {"type": "NumberNode", "value": 2},
    }
    assert verbose_module._serialize_parse_node(
        NegNode(SymbolNode("x"))
    ) == {
        "type": "NegNode",
        "operand": {"type": "SymbolNode", "name": "x"},
    }
    assert verbose_module._serialize_parse_node(
        FunctionNode("sin", SymbolNode("x"))
    ) == {
        "type": "FunctionNode",
        "function": "sin",
        "operand": {"type": "SymbolNode", "name": "x"},
    }
    with pytest.raises(TypeError, match="Unsupported parser node type"):
        verbose_module._serialize_parse_node(object())  # type: ignore[arg-type]


def test_verbose_artifact_text_and_walkthrough_helpers_cover_optional_sections() -> None:
    assert verbose_module._state_space_text({"state_space": None}) == "unavailable: nonlinear explicit system\n"

    markdown = verbose_module._walkthrough_markdown(
        title="demo",
        source_text="xdot = -x",
        normalized_text="xdot=-x",
        parsed_equations=["D1_x = -x"],
        residuals=["D1_x + x"],
        solved_derivatives=["D1_x = -x"],
        first_order_text="d/dt x = -x\n",
        state_space_text="A = Matrix([[-1]])\n",
        token_stream=[{"kind": "IDENT", "value": "x"}],
        parsed_trees=[{"type": "EquationNode"}],
        equation_dicts=[{"op": "equation"}],
        extraction_dict={"states": ["x"]},
        explicit_form={"form": "explicit_ode"},
        linearity={"is_linear": True},
        runtime_payload={"t_eval": [0.0, 1.0]},
        graph={"nodes": [{"op": "integrator"}], "edges": []},
        simulink_model={"name": "demo_model"},
        comparison={"passes": True},
        simulink_validation={"passes": True},
        files={
            "input_equations": "input_equations.tex",
            "normalized_equations": "normalized_equations.tex",
            "token_stream": "token_stream.json",
            "parsed_trees": "parsed_trees.json",
            "parsed_equations": "parsed_equations.txt",
            "equation_dicts": "equation_dicts.json",
            "extraction": "extraction.json",
            "residual_equations": "residual_equations.txt",
            "solved_derivatives": "solved_derivatives.txt",
            "solved_derivative_dicts": "solved_derivative_dicts.json",
            "first_order": "first_order.txt",
            "first_order_system": "first_order_system.json",
            "explicit_form": "explicit_form.json",
            "linearity": "linearity.json",
            "state_space": "state_space.txt",
            "state_space_json": "state_space.json",
            "graph": "graph.json",
            "simulink_model_dict": "simulink_model.json",
            "runtime": "runtime.json",
            "comparison": "comparison.json",
            "simulink_validation": "simulink_validation.json",
            "summary": "summary.json",
            "simulation_plot": "simulation_plot.png",
            "simulink_model_image": "simulink_model.png",
            "simulink_model_note": "simulink_model_note.txt",
        },
    )

    assert "This is the Simulink-ready backend model dictionary." in markdown
    assert "ODE/state-space comparison artifact" in markdown
    assert "Simulink validation artifact" in markdown
    assert "Simulation plot artifact" in markdown
    assert "Simulink model image artifact" in markdown
    assert "Simulink model note artifact" in markdown

    no_optional_markdown = verbose_module._walkthrough_markdown(
        title="demo",
        source_text="xdot = -x",
        normalized_text="xdot=-x",
        parsed_equations=["D1_x = -x"],
        residuals=["D1_x + x"],
        solved_derivatives=["D1_x = -x"],
        first_order_text="d/dt x = -x\n",
        state_space_text="A = Matrix([[-1]])\n",
        token_stream=[{"kind": "IDENT", "value": "x"}],
        parsed_trees=[{"type": "EquationNode"}],
        equation_dicts=[{"op": "equation"}],
        extraction_dict={"states": ["x"]},
        explicit_form={"form": "explicit_ode"},
        linearity={"is_linear": True},
        runtime_payload={"t_eval": [0.0, 1.0]},
        graph={"nodes": [{"op": "integrator"}], "edges": []},
        simulink_model=None,
        comparison=None,
        simulink_validation={"passes": True},
        files={
            "input_equations": "input_equations.tex",
            "normalized_equations": "normalized_equations.tex",
            "token_stream": "token_stream.json",
            "parsed_trees": "parsed_trees.json",
            "parsed_equations": "parsed_equations.txt",
            "equation_dicts": "equation_dicts.json",
            "extraction": "extraction.json",
            "residual_equations": "residual_equations.txt",
            "solved_derivatives": "solved_derivatives.txt",
            "solved_derivative_dicts": "solved_derivative_dicts.json",
            "first_order": "first_order.txt",
            "first_order_system": "first_order_system.json",
            "explicit_form": "explicit_form.json",
            "linearity": "linearity.json",
            "state_space": "state_space.txt",
            "state_space_json": None,
            "graph": "graph.json",
            "simulink_model_dict": None,
            "runtime": "runtime.json",
            "comparison": None,
            "simulink_validation": "simulink_validation.json",
            "summary": "summary.json",
            "simulation_plot": None,
            "simulink_model_image": "simulink_model.png",
            "simulink_model_note": None,
        },
    )
    assert "there is no Simulink model dictionary" in no_optional_markdown


def test_verbose_artifact_plot_helpers_cover_empty_series_and_extra_axes(tmp_path: Path) -> None:
    assert verbose_module._render_simulation_plot(
        {
            "ode_result": None,
            "state_space_result": None,
            "simulink_result": None,
        },
        tmp_path / "empty.png",
    ) is None

    plot_path = tmp_path / "simulation.png"
    rendered = verbose_module._render_simulation_plot(
        {
            "ode_result": {
                "t": np.asarray([0.0, 0.5, 1.0]),
                "states": np.asarray(
                    [
                        [1.0, 0.0, -1.0],
                        [0.5, 0.1, -0.5],
                        [0.0, 0.2, 0.0],
                    ]
                ),
                "state_names": ["x", "y", "z"],
            },
            "state_space_result": None,
            "simulink_result": None,
        },
        plot_path,
    )

    assert rendered == str(plot_path)
    assert plot_path.exists()


def test_verbose_artifact_simulink_image_renderer_writes_expected_commands(tmp_path: Path) -> None:
    engine = _FakeMatlabEngine()
    output_path = tmp_path / "model.png"

    rendered = verbose_module._render_simulink_model_image(engine, "demo'model", output_path)

    assert rendered == str(output_path)
    assert engine.calls[0] == ("open_system", "demo'model", 0)
    assert "ZoomFactor" in engine.calls[1][1]
    assert "print" in engine.calls[2][1]
