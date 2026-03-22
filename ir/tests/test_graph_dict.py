from __future__ import annotations

from ir.graph_dict import canonicalize_graph_dict


def test_canonicalize_graph_dict_orders_outputs_and_optional_sections() -> None:
    graph = {
        "nodes": [{"id": "b"}, {"id": "a"}],
        "edges": [{"src": "b", "dst": "a", "dst_port": "2"}, {"src": "a", "dst": "b", "dst_port": "1"}],
        "state_chains": [{"state": "x_dot"}, {"state": "x"}],
        "algebraic_chains": [{"variable": "z2"}, {"variable": "z1"}],
        "outputs": {"y": "b", "x": "a"},
    }

    normalized = canonicalize_graph_dict(graph)

    assert [node["id"] for node in normalized["nodes"]] == ["a", "b"]
    assert list(normalized["outputs"]) == ["x", "y"]
    assert [entry["state"] for entry in normalized["state_chains"]] == ["x", "x_dot"]
    assert [entry["variable"] for entry in normalized["algebraic_chains"]] == ["z1", "z2"]


def test_canonicalize_graph_dict_handles_missing_outputs_section() -> None:
    normalized = canonicalize_graph_dict({"nodes": [], "edges": []})
    assert "outputs" not in normalized
