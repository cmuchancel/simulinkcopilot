"""Canonical graph-dictionary helpers for deterministic block lowering."""

from __future__ import annotations

from copy import deepcopy

from latex_frontend.symbols import SUPPORTED_FUNCTION_NAMES


ALLOWED_GRAPH_OPS = {
    "constant",
    "symbol_input",
    "state_signal",
    "add",
    "sum",
    "mul",
    "gain",
    "div",
    "pow",
    "negate",
    "integrator",
}
ALLOWED_GRAPH_OPS.update(SUPPORTED_FUNCTION_NAMES)


def canonicalize_graph_dict(graph: dict[str, object]) -> dict[str, object]:
    """Return a deterministically ordered graph dictionary."""
    normalized = deepcopy(graph)
    normalized["nodes"] = sorted(normalized.get("nodes", []), key=lambda node: node["id"])
    normalized["edges"] = sorted(
        normalized.get("edges", []),
        key=lambda edge: (edge["src"], edge["dst"], edge["dst_port"]),
    )
    if "state_chains" in normalized:
        normalized["state_chains"] = sorted(normalized["state_chains"], key=lambda entry: entry["state"])
    if "algebraic_chains" in normalized:
        normalized["algebraic_chains"] = sorted(normalized["algebraic_chains"], key=lambda entry: entry["variable"])
    if "outputs" in normalized:
        normalized["outputs"] = {
            key: normalized["outputs"][key]
            for key in sorted(normalized["outputs"])
        }
    return normalized
