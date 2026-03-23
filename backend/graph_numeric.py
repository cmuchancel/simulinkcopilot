"""Compile-time evaluation helpers for graph lowering."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

from latex_frontend.symbols import DeterministicCompileError


def safe_reciprocal(value: float) -> float:
    if math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-15):
        raise DeterministicCompileError("Reciprocal function encountered a zero denominator during constant folding.")
    return 1.0 / value


@dataclass
class GraphNumericEvaluator:
    """Evaluate graph subtrees that are fully known at compile time."""

    node_map: Mapping[str, Mapping[str, object]]
    symbol_values: Mapping[str, float] = field(default_factory=dict)
    cache: dict[str, float | None] = field(default_factory=dict)

    def value(self, node_id: str) -> float | None:
        if node_id in self.cache:
            return self.cache[node_id]

        node = self.node_map[node_id]
        op = str(node["op"])
        value: float | None
        if op == "constant":
            value = float(node["value"])
        elif op == "symbol_input":
            symbol_name = str(node["name"])
            symbol_role = str(node.get("symbol_role", ""))
            if symbol_role == "independent_variable":
                value = None
            else:
                value = float(self.symbol_values[symbol_name]) if symbol_name in self.symbol_values else None
        elif op in {"state_signal", "integrator"}:
            value = None
        else:
            child_values = [self.value(str(child_id)) for child_id in node.get("inputs", [])]
            if any(child is None for child in child_values):
                value = None
            else:
                value = self._evaluate_known_op(op, [float(child) for child in child_values])

        self.cache[node_id] = value
        return value

    def _evaluate_known_op(self, op: str, child_values: list[float]) -> float | None:
        if op in {"add", "sum"}:
            return float(sum(child_values))
        if op in {"mul", "gain"}:
            return float(math.prod(child_values))
        if op == "div":
            return float(child_values[0] / child_values[1])
        if op == "negate":
            return float(-child_values[0])
        if op == "pow":
            return float(child_values[0] ** child_values[1])
        if op == "sin":
            return float(math.sin(child_values[0]))
        if op == "cos":
            return float(math.cos(child_values[0]))
        if op == "tan":
            return float(math.tan(child_values[0]))
        if op == "sec":
            return float(safe_reciprocal(math.cos(child_values[0])))
        if op == "csc":
            return float(safe_reciprocal(math.sin(child_values[0])))
        if op == "cot":
            return float(safe_reciprocal(math.tan(child_values[0])))
        if op == "asin":
            return float(math.asin(child_values[0]))
        if op == "acos":
            return float(math.acos(child_values[0]))
        if op == "atan":
            return float(math.atan(child_values[0]))
        if op == "atan2":
            return float(math.atan2(child_values[0], child_values[1]))
        if op == "sinh":
            return float(math.sinh(child_values[0]))
        if op == "cosh":
            return float(math.cosh(child_values[0]))
        if op == "tanh":
            return float(math.tanh(child_values[0]))
        if op == "sech":
            return float(safe_reciprocal(math.cosh(child_values[0])))
        if op == "csch":
            return float(safe_reciprocal(math.sinh(child_values[0])))
        if op == "coth":
            return float(safe_reciprocal(math.tanh(child_values[0])))
        if op == "asinh":
            return float(math.asinh(child_values[0]))
        if op == "acosh":
            return float(math.acosh(child_values[0]))
        if op == "atanh":
            return float(math.atanh(child_values[0]))
        if op == "exp":
            return float(math.exp(child_values[0]))
        if op == "log":
            return float(math.log(child_values[0]))
        if op == "sqrt":
            return float(math.sqrt(child_values[0]))
        if op == "abs":
            return float(abs(child_values[0]))
        if op == "min":
            return float(min(child_values))
        if op == "max":
            return float(max(child_values))
        if op == "sat":
            return float(min(max(child_values[0], child_values[1]), child_values[2]))
        return None
