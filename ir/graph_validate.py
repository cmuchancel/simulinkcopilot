"""Static validation for deterministic graph dictionaries."""

from __future__ import annotations

from ir.graph_dict import ALLOWED_GRAPH_OPS, canonicalize_graph_dict
from latex_frontend.symbols import DeterministicCompileError, SUPPORTED_FUNCTION_NAMES


ARITY_RULES: dict[str, tuple[int, int | None]] = {
    "constant": (0, 0),
    "symbol_input": (0, 0),
    "state_signal": (1, 1),
    "add": (2, 2),
    "sum": (2, None),
    "mul": (2, None),
    "gain": (2, 2),
    "div": (2, 2),
    "pow": (2, 2),
    "negate": (1, 1),
    "integrator": (1, 1),
}
ARITY_RULES.update({name: (1, 1) for name in SUPPORTED_FUNCTION_NAMES})


def validate_graph_dict(graph: dict[str, object]) -> dict[str, object]:
    """Validate a graph dictionary and return its canonicalized form."""
    normalized = canonicalize_graph_dict(graph)
    nodes = normalized.get("nodes", [])
    edges = normalized.get("edges", [])
    node_ids = [node["id"] for node in nodes]

    if len(node_ids) != len(set(node_ids)):
        raise DeterministicCompileError("Graph contains duplicate node IDs.")
    if node_ids != sorted(node_ids):
        raise DeterministicCompileError("Graph nodes are not serialized in deterministic ID order.")

    node_map = {node["id"]: node for node in nodes}
    for node in nodes:
        op = node.get("op")
        if op not in ALLOWED_GRAPH_OPS:
            raise DeterministicCompileError(f"Graph node {node['id']!r} has invalid op {op!r}.")
        inputs = node.get("inputs", [])
        min_arity, max_arity = ARITY_RULES[op]
        if len(inputs) < min_arity or (max_arity is not None and len(inputs) > max_arity):
            raise DeterministicCompileError(
                f"Graph node {node['id']!r} with op {op!r} has invalid arity {len(inputs)}."
            )
        for input_id in inputs:
            if input_id not in node_map:
                raise DeterministicCompileError(
                    f"Graph node {node['id']!r} depends on missing node {input_id!r}."
                )

    expected_edges = sorted(
        (
            {"src": input_id, "dst": node["id"], "dst_port": index}
            for node in nodes
            for index, input_id in enumerate(node.get("inputs", []))
        ),
        key=lambda edge: (edge["src"], edge["dst"], edge["dst_port"]),
    )
    if edges != expected_edges:
        raise DeterministicCompileError("Graph edge list does not match node input dependencies.")

    for entry in normalized.get("state_chains", []):
        signal_id = entry["signal"]
        integrator_id = entry["integrator"]
        rhs_id = entry["rhs"]
        if signal_id not in node_map or integrator_id not in node_map or rhs_id not in node_map:
            raise DeterministicCompileError(f"State chain for {entry['state']!r} references missing nodes.")
        if node_map[signal_id]["op"] != "state_signal":
            raise DeterministicCompileError(f"State chain signal {signal_id!r} is not a state_signal node.")
        if node_map[integrator_id]["op"] != "integrator":
            raise DeterministicCompileError(f"State chain integrator {integrator_id!r} is not an integrator node.")
        if node_map[signal_id].get("state") != entry["state"] or node_map[integrator_id].get("state") != entry["state"]:
            raise DeterministicCompileError(f"State chain for {entry['state']!r} is inconsistent.")
        if node_map[signal_id].get("inputs") != [integrator_id]:
            raise DeterministicCompileError(
                f"State signal {signal_id!r} must point to its owning integrator {integrator_id!r}."
            )
        if node_map[integrator_id].get("inputs") != [rhs_id]:
            raise DeterministicCompileError(
                f"Integrator {integrator_id!r} must point to the RHS node {rhs_id!r}."
            )

    for output_name, output_id in normalized.get("outputs", {}).items():
        if output_id not in node_map:
            raise DeterministicCompileError(
                f"Graph output {output_name!r} references missing node {output_id!r}."
            )

    return normalized
