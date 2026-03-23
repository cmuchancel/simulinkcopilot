"""Deterministic symbolic signal labels for graph-backed Simulink models."""

from __future__ import annotations

import re

from ir.graph_validate import validate_graph_dict


_ATOMIC_PATTERN = re.compile(r"^[A-Za-z0-9_.]+$")
_STATE_DERIVATIVE_PATTERN = re.compile(r"^(?P<base>.+)_d(?P<order>\d+)$")


def state_base_name(state: str) -> str:
    """Return the base state name shared by a derivative chain."""
    if state.endswith("_ddot"):
        return state[:-5]
    if state.endswith("_dot"):
        return state[:-4]
    match = _STATE_DERIVATIVE_PATTERN.match(state)
    if match:
        return match.group("base")
    return state


def state_order(state: str) -> int:
    """Return the derivative order encoded in a canonical state name."""
    if state.endswith("_ddot"):
        return 2
    if state.endswith("_dot"):
        return 1
    match = _STATE_DERIVATIVE_PATTERN.match(state)
    if match:
        return int(match.group("order"))
    return 0


def _numeric_literal(value: object) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(round(number)))
    return repr(number)


def _is_atomic(text: str) -> bool:
    return bool(_ATOMIC_PATTERN.match(text))


def _maybe_parenthesize(text: str) -> str:
    return text if _is_atomic(text) else f"({text})"


def _flatten_add(terms: list[str]) -> str:
    pieces: list[str] = []
    for term in terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        if cleaned.startswith("-"):
            if pieces:
                pieces.append("- " + cleaned[1:].lstrip())
            else:
                pieces.append(cleaned)
        else:
            if pieces:
                pieces.append("+ " + cleaned)
            else:
                pieces.append(cleaned)
    return " ".join(pieces) if pieces else "0"


def _format_mul(factors: list[str]) -> str:
    if not factors:
        return "1"
    if factors[0] == "-1" and len(factors) > 1:
        rest = _format_mul(factors[1:])
        if _is_atomic(rest) or (rest.startswith("(") and rest.endswith(")")):
            return f"-{rest}"
        return f"-{_maybe_parenthesize(rest)}"
    if factors[0] == "1" and len(factors) > 1:
        return _format_mul(factors[1:])
    return " * ".join(_maybe_parenthesize(factor) for factor in factors)


def build_node_expressions(graph: dict[str, object]) -> dict[str, str]:
    """Return a deterministic symbolic expression label for every graph node."""
    validated = validate_graph_dict(graph)
    node_map = {node["id"]: node for node in validated["nodes"]}  # type: ignore[index]
    memo: dict[str, str] = {}

    def render(node_id: str) -> str:
        if node_id in memo:
            return memo[node_id]

        node = node_map[node_id]
        op = node["op"]
        if op == "constant":
            label = _numeric_literal(node["value"])
        elif op == "symbol_input":
            label = str(node["name"])
        elif op in {"state_signal", "integrator"}:
            label = str(node["state"])
        elif op in {"add", "sum"}:
            label = _flatten_add([render(child_id) for child_id in node["inputs"]])
        elif op in {"mul", "gain"}:
            label = _format_mul([render(child_id) for child_id in node["inputs"]])
        elif op == "div":
            numerator, denominator = node["inputs"]
            label = f"{_maybe_parenthesize(render(numerator))} / {_maybe_parenthesize(render(denominator))}"
        elif op == "pow":
            base_id, exponent_id = node["inputs"]
            label = f"{_maybe_parenthesize(render(base_id))}^{_maybe_parenthesize(render(exponent_id))}"
        elif op == "negate":
            child = render(node["inputs"][0])
            label = f"-{_maybe_parenthesize(child)}" if not _is_atomic(child) else f"-{child}"
        elif op == "atan2":
            y_id, x_id = node["inputs"]
            label = f"atan2({_maybe_parenthesize(render(y_id))}, {_maybe_parenthesize(render(x_id))})"
        elif op in {"min", "max", "sat"}:
            rendered = ", ".join(_maybe_parenthesize(render(child_id)) for child_id in node["inputs"])
            label = f"{op}({rendered})"
        else:
            rendered = ", ".join(
                _maybe_parenthesize(render(child_id)) if not _is_atomic(render(child_id)) else render(child_id)
                for child_id in node["inputs"]
            )
            label = f"{op}({rendered})"

        memo[node_id] = label
        return label

    for node_id in node_map:
        render(node_id)
    return memo
