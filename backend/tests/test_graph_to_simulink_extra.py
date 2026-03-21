from __future__ import annotations

import math

import pytest

from backend.graph_partition import _graph_layer
from backend.graph_to_simulink import GraphToSimulinkLowerer, _safe_reciprocal, graph_to_simulink_model
from latex_frontend.symbols import DeterministicCompileError


def _graph(rhs_node: dict[str, object], *other_nodes: dict[str, object]) -> dict[str, object]:
    nodes = [
        *other_nodes,
        rhs_node,
        {"id": "s_int", "op": "integrator", "inputs": [rhs_node["id"]], "state": "x"},
        {"id": "t_sig", "op": "state_signal", "inputs": ["s_int"], "state": "x"},
    ]
    nodes = sorted(nodes, key=lambda node: str(node["id"]))
    edges = sorted(
        (
            {"src": input_id, "dst": node["id"], "dst_port": index}
            for node in nodes
            for index, input_id in enumerate(node.get("inputs", []))
        ),
        key=lambda edge: (edge["src"], edge["dst"], edge["dst_port"]),
    )
    return {
        "name": "demo_graph",
        "nodes": nodes,
        "edges": edges,
        "state_chains": [{"state": "x", "signal": "t_sig", "integrator": "s_int", "rhs": rhs_node["id"]}],
        "outputs": {"x": "t_sig"},
    }


def _unary_graph(op: str, value: float) -> dict[str, object]:
    return _graph(
        {"id": "n_rhs", "op": op, "inputs": ["a_const"]},
        {"id": "a_const", "op": "constant", "value": value, "inputs": []},
    )


def _pow_graph(*, exponent_node: dict[str, object], base_node: dict[str, object] | None = None) -> dict[str, object]:
    return _graph(
        {"id": "n_rhs", "op": "pow", "inputs": ["a_base", exponent_node["id"]]},
        base_node or {"id": "a_base", "op": "symbol_input", "name": "u", "inputs": []},
        exponent_node,
    )


@pytest.mark.parametrize(
    ("op", "value", "expected"),
    [
        ("add", None, 3.0),
        ("sum", None, 3.0),
        ("mul", None, 6.0),
        ("gain", None, 6.0),
        ("div", None, 3.0),
        ("negate", -2.0, 2.0),
        ("pow", None, 8.0),
        ("sin", 0.3, math.sin(0.3)),
        ("cos", 0.3, math.cos(0.3)),
        ("tan", 0.3, math.tan(0.3)),
        ("sec", 0.3, 1.0 / math.cos(0.3)),
        ("csc", 0.3, 1.0 / math.sin(0.3)),
        ("cot", 0.3, 1.0 / math.tan(0.3)),
        ("asin", 0.3, math.asin(0.3)),
        ("acos", 0.3, math.acos(0.3)),
        ("atan", 0.3, math.atan(0.3)),
        ("sinh", 0.3, math.sinh(0.3)),
        ("cosh", 0.3, math.cosh(0.3)),
        ("tanh", 0.3, math.tanh(0.3)),
        ("sech", 0.3, 1.0 / math.cosh(0.3)),
        ("csch", 0.3, 1.0 / math.sinh(0.3)),
        ("coth", 0.3, 1.0 / math.tanh(0.3)),
        ("asinh", 0.3, math.asinh(0.3)),
        ("acosh", 1.3, math.acosh(1.3)),
        ("atanh", 0.3, math.atanh(0.3)),
        ("exp", 0.3, math.exp(0.3)),
        ("log", 1.3, math.log(1.3)),
        ("sqrt", 1.3, math.sqrt(1.3)),
        ("abs", -2.5, 2.5),
    ],
)
def test_numeric_value_constant_folding_covers_supported_ops(op: str, value: float | None, expected: float) -> None:
    if op in {"add", "sum"}:
        graph = _graph(
            {"id": "n_rhs", "op": op, "inputs": ["a", "b"]},
            {"id": "a", "op": "constant", "value": 1.0, "inputs": []},
            {"id": "b", "op": "constant", "value": 2.0, "inputs": []},
        )
    elif op in {"mul", "gain"}:
        graph = _graph(
            {"id": "n_rhs", "op": op, "inputs": ["a", "b"]},
            {"id": "a", "op": "constant", "value": 2.0, "inputs": []},
            {"id": "b", "op": "constant", "value": 3.0, "inputs": []},
        )
    elif op == "div":
        graph = _graph(
            {"id": "n_rhs", "op": "div", "inputs": ["a", "b"]},
            {"id": "a", "op": "constant", "value": 6.0, "inputs": []},
            {"id": "b", "op": "constant", "value": 2.0, "inputs": []},
        )
    elif op == "pow":
        graph = _graph(
            {"id": "n_rhs", "op": "pow", "inputs": ["a", "b"]},
            {"id": "a", "op": "constant", "value": 2.0, "inputs": []},
            {"id": "b", "op": "constant", "value": 3.0, "inputs": []},
        )
    else:
        graph = _unary_graph(op, float(value))
    lowerer = GraphToSimulinkLowerer(graph=graph, model_name="demo_model")
    assert lowerer.numeric_value("n_rhs") == pytest.approx(expected)


def test_graph_layer_short_circuits_active_recursion_and_safe_reciprocal_rejects_zero() -> None:
    lowerer = GraphToSimulinkLowerer(graph=_unary_graph("sin", 0.2), model_name="demo_model")
    assert _graph_layer(lowerer.node_map, "n_rhs", {"n_rhs"}) == 0
    with pytest.raises(DeterministicCompileError, match="zero denominator"):
        _safe_reciprocal(0.0)


def test_graph_to_simulink_model_covers_symbol_input_modes_and_output_validation() -> None:
    symbol_graph = _graph({"id": "n_rhs", "op": "symbol_input", "name": "u", "inputs": []})
    inport_model = graph_to_simulink_model(symbol_graph, input_mode="inport")
    assert {spec["type"] for spec in inport_model["blocks"].values()} >= {"Inport", "Integrator"}

    with pytest.raises(DeterministicCompileError, match="mismatched time/value lengths"):
        graph_to_simulink_model(
            symbol_graph,
            input_signals={"u": {"time": [0.0], "values": [0.0, 1.0]}},
        )

    with pytest.raises(DeterministicCompileError, match="No numeric value or input signal provided"):
        graph_to_simulink_model(symbol_graph)

    lowerer = GraphToSimulinkLowerer(graph=symbol_graph, model_name="demo_model")
    with pytest.raises(DeterministicCompileError, match="Requested Simulink output 'missing' not found"):
        lowerer.lower(state_names=["missing"])


def test_graph_to_simulink_model_covers_negate_reciprocal_and_math_function_blocks() -> None:
    negate_model = graph_to_simulink_model(_graph({"id": "n_rhs", "op": "negate", "inputs": ["t_sig"]}))
    negate_gains = [spec for spec in negate_model["blocks"].values() if spec["type"] == "Gain"]
    assert any(spec["params"].get("Gain") == "-1" for spec in negate_gains)

    sec_model = graph_to_simulink_model(_graph({"id": "n_rhs", "op": "sec", "inputs": ["t_sig"]}))
    assert {spec["type"] for spec in sec_model["blocks"].values()} >= {"Divide", "TrigonometricFunction"}

    exp_model = graph_to_simulink_model(_graph({"id": "n_rhs", "op": "exp", "inputs": ["t_sig"]}))
    assert any(spec["type"] == "MathFunction" and spec["params"].get("Operator") == "exp" for spec in exp_model["blocks"].values())


def test_graph_to_simulink_model_covers_power_special_cases() -> None:
    zero_model = graph_to_simulink_model(
        _pow_graph(
            exponent_node={"id": "b_exp", "op": "constant", "value": 0.0, "inputs": []},
            base_node={"id": "a_base", "op": "state_signal", "inputs": ["s_int"], "state": "x"},
        ),
    )
    assert any(spec["type"] == "Constant" and spec["params"].get("Value") == "1" for spec in zero_model["blocks"].values())

    one_model = graph_to_simulink_model(
        _pow_graph(
            exponent_node={"id": "b_exp", "op": "constant", "value": 1.0, "inputs": []},
            base_node={"id": "a_base", "op": "state_signal", "inputs": ["s_int"], "state": "x"},
        ),
    )
    assert not any(block_id.startswith("prod_n_rhs") for block_id in one_model["blocks"])

    negative_model = graph_to_simulink_model(
        _pow_graph(
            exponent_node={"id": "b_exp", "op": "constant", "value": -2.0, "inputs": []},
            base_node={"id": "a_base", "op": "state_signal", "inputs": ["s_int"], "state": "x"},
        ),
    )
    assert any(block_id.startswith("pow_recip_") for block_id in negative_model["blocks"])

    fractional_model = graph_to_simulink_model(
        _pow_graph(
            exponent_node={"id": "b_exp", "op": "constant", "value": 0.5, "inputs": []},
            base_node={"id": "a_base", "op": "state_signal", "inputs": ["s_int"], "state": "x"},
        ),
    )
    operators = {
        spec["params"].get("Operator")
        for spec in fractional_model["blocks"].values()
        if spec["type"] == "MathFunction"
    }
    assert {"log", "exp"}.issubset(operators)

    with pytest.raises(DeterministicCompileError, match="requires a numeric exponent"):
        graph_to_simulink_model(
            _pow_graph(
                exponent_node={"id": "b_exp", "op": "symbol_input", "name": "p", "inputs": []},
                base_node={"id": "a_base", "op": "state_signal", "inputs": ["s_int"], "state": "x"},
            ),
        )
