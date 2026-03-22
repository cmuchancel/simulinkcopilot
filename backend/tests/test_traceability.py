from __future__ import annotations

import pytest

from backend import traceability


def test_state_name_helpers_cover_canonical_suffixes() -> None:
    assert traceability.state_base_name("x_ddot") == "x"
    assert traceability.state_base_name("theta_dot") == "theta"
    assert traceability.state_base_name("q_d3") == "q"
    assert traceability.state_base_name("plain") == "plain"

    assert traceability.state_order("x_ddot") == 2
    assert traceability.state_order("theta_dot") == 1
    assert traceability.state_order("q_d3") == 3
    assert traceability.state_order("plain") == 0


def test_traceability_format_helpers_cover_atomic_and_composite_cases() -> None:
    assert traceability._numeric_literal(2.0) == "2"
    assert traceability._numeric_literal(2.5) == "2.5"
    assert traceability._is_atomic("x_1") is True
    assert traceability._is_atomic("x + y") is False
    assert traceability._maybe_parenthesize("x") == "x"
    assert traceability._maybe_parenthesize("x + y") == "(x + y)"
    assert traceability._flatten_add(["", "x", "-y", "z"]) == "x - y + z"
    assert traceability._flatten_add(["", " "]) == "0"
    assert traceability._format_mul([]) == "1"
    assert traceability._format_mul(["-1", "x + y"]) == "-(x + y)"
    assert traceability._format_mul(["-1", "x", "y"]) == "-(x * y)"
    assert traceability._format_mul(["1", "x", "y"]) == "x * y"


def test_build_node_expressions_covers_all_supported_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = {
        "nodes": [
            {"id": "c1", "op": "constant", "value": 2.0, "inputs": []},
            {"id": "u", "op": "symbol_input", "name": "u", "inputs": []},
            {"id": "int", "op": "integrator", "state": "x", "inputs": ["sum"]},
            {"id": "sig", "op": "state_signal", "state": "x", "inputs": ["int"]},
            {"id": "add", "op": "add", "inputs": ["sig", "u"]},
            {"id": "mul", "op": "mul", "inputs": ["c1", "add"]},
            {"id": "div", "op": "div", "inputs": ["mul", "c1"]},
            {"id": "pow", "op": "pow", "inputs": ["sig", "c1"]},
            {"id": "neg", "op": "negate", "inputs": ["add"]},
            {"id": "sin", "op": "sin", "inputs": ["sig"]},
            {"id": "sum", "op": "sum", "inputs": ["neg", "sin"]},
            {"id": "gain", "op": "gain", "inputs": ["u"]},
        ],
        "edges": [],
        "state_chains": [{"state": "x", "signal": "sig", "integrator": "int", "rhs": "sum"}],
        "outputs": {"x": "sig"},
    }
    monkeypatch.setattr(traceability, "validate_graph_dict", lambda payload: payload)

    expressions = traceability.build_node_expressions(graph)

    assert expressions["c1"] == "2"
    assert expressions["u"] == "u"
    assert expressions["int"] == "x"
    assert expressions["sig"] == "x"
    assert expressions["add"] == "x + u"
    assert expressions["mul"] == "2 * (x + u)"
    assert expressions["div"] == "(2 * (x + u)) / 2"
    assert expressions["pow"] == "x^2"
    assert expressions["neg"] == "-(x + u)"
    assert expressions["sin"] == "sin(x)"
    assert expressions["sum"] == "-(x + u) + sin(x)"
    assert expressions["gain"] == "u"
