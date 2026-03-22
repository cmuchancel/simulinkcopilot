from __future__ import annotations

import pytest

from ir.graph_validate import validate_graph_dict
from latex_frontend.symbols import DeterministicCompileError


def _valid_graph() -> dict[str, object]:
    return {
        "nodes": [
            {"id": "n1", "op": "constant", "value": 1.0, "inputs": []},
            {"id": "n2", "op": "integrator", "inputs": ["n1"], "state": "x"},
            {"id": "n3", "op": "state_signal", "inputs": ["n2"], "state": "x"},
        ],
        "edges": [
            {"src": "n1", "dst": "n2", "dst_port": 0},
            {"src": "n2", "dst": "n3", "dst_port": 0},
        ],
        "state_chains": [{"state": "x", "signal": "n3", "integrator": "n2", "rhs": "n1"}],
        "outputs": {"x": "n3"},
    }


def test_validate_graph_dict_accepts_valid_graph() -> None:
    validated = validate_graph_dict(_valid_graph())
    assert [node["id"] for node in validated["nodes"]] == ["n1", "n2", "n3"]


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (lambda graph: graph["nodes"].append({"id": "n3", "op": "constant", "value": 0.0, "inputs": []}), "duplicate node IDs"),
        (lambda graph: graph["nodes"].__setitem__(0, {"id": "n1", "op": "mystery", "inputs": []}), "invalid op"),
        (lambda graph: graph["nodes"].__setitem__(0, {"id": "n1", "op": "constant", "value": 1.0, "inputs": ["n2"]}), "invalid arity"),
        (lambda graph: graph["nodes"].__setitem__(2, {"id": "n3", "op": "state_signal", "inputs": ["missing"], "state": "x"}), "depends on missing node"),
        (lambda graph: graph["edges"].append({"src": "n1", "dst": "n3", "dst_port": 1}), "edge list does not match"),
        (lambda graph: graph["state_chains"].__setitem__(0, {"state": "x", "signal": "n1", "integrator": "n2", "rhs": "n1"}), "is not a state_signal"),
        (lambda graph: graph["outputs"].__setitem__("x", "missing"), "references missing node"),
    ],
)
def test_validate_graph_dict_rejects_invalid_graph_shapes(mutator, pattern) -> None:
    graph = _valid_graph()
    mutator(graph)
    with pytest.raises(DeterministicCompileError, match=pattern):
        validate_graph_dict(graph)


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (
            lambda graph: graph["state_chains"].__setitem__(0, {"state": "x", "signal": "n3", "integrator": "missing", "rhs": "n1"}),
            "references missing nodes",
        ),
        (
            lambda graph: graph["state_chains"].__setitem__(0, {"state": "x", "signal": "n3", "integrator": "n1", "rhs": "n1"}),
            "is not an integrator",
        ),
        (
            lambda graph: graph["nodes"].__setitem__(1, {"id": "n2", "op": "integrator", "inputs": ["n1"], "state": "y"}),
            "is inconsistent",
        ),
        (
            lambda graph: (
                graph["nodes"].__setitem__(2, {"id": "n3", "op": "state_signal", "inputs": ["n1"], "state": "x"}),
                graph["edges"].__setitem__(1, {"src": "n1", "dst": "n3", "dst_port": 0}),
            ),
            "must point to its owning integrator",
        ),
        (
            lambda graph: (
                graph["nodes"].__setitem__(1, {"id": "n2", "op": "integrator", "inputs": ["n3"], "state": "x"}),
                graph["edges"].__setitem__(0, {"src": "n3", "dst": "n2", "dst_port": 0}),
            ),
            "must point to the RHS node",
        ),
    ],
)
def test_validate_graph_dict_rejects_state_chain_invariants(mutator, pattern) -> None:
    graph = _valid_graph()
    mutator(graph)
    with pytest.raises(DeterministicCompileError, match=pattern):
        validate_graph_dict(graph)


def test_validate_graph_dict_rejects_nondeterministic_node_order(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _valid_graph()
    graph["nodes"].reverse()
    monkeypatch.setattr("ir.graph_validate.canonicalize_graph_dict", lambda graph: graph)

    with pytest.raises(DeterministicCompileError, match="deterministic ID order"):
        validate_graph_dict(graph)


def test_validate_graph_dict_rejects_invalid_algebraic_chain_shapes() -> None:
    graph = {
        "nodes": [
            {"id": "n1", "op": "constant", "value": 1.0, "inputs": []},
            {"id": "n2", "op": "symbol_input", "name": "z", "symbol_role": "algebraic_variable", "inputs": []},
        ],
        "edges": [],
        "algebraic_chains": [{"variable": "z", "signal": "n2", "residual": "missing"}],
        "outputs": {},
    }
    with pytest.raises(DeterministicCompileError, match="references missing nodes"):
        validate_graph_dict(graph)

    graph["nodes"].append({"id": "n3", "op": "constant", "value": 0.0, "inputs": []})
    graph["algebraic_chains"][0]["residual"] = "n3"
    graph["nodes"][1]["symbol_role"] = "input"
    with pytest.raises(DeterministicCompileError, match="is not an algebraic-variable source"):
        validate_graph_dict(graph)

    graph["nodes"][1]["symbol_role"] = "algebraic_variable"
    graph["nodes"][1]["name"] = "y"
    with pytest.raises(DeterministicCompileError, match="is inconsistent"):
        validate_graph_dict(graph)
