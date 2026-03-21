"""Rule-based helpers for deterministic state extraction."""

from __future__ import annotations

from dataclasses import dataclass

from ir.expression_nodes import DerivativeNode, EquationNode, walk_expression
from latex_frontend.symbols import state_name
from states.classify_symbols import SymbolMetadata


@dataclass(frozen=True)
class ExtractionResult:
    """Canonical output of state extraction."""

    states: tuple[str, ...]
    inputs: tuple[str, ...]
    parameters: tuple[str, ...]
    independent_variable: str | None
    derivative_orders: dict[str, int]
    symbol_metadata: dict[str, SymbolMetadata]

    def to_dict(self) -> dict[str, object]:
        return {
            "states": list(self.states),
            "inputs": list(self.inputs),
            "parameters": list(self.parameters),
            "independent_variable": self.independent_variable,
            "derivative_orders": dict(self.derivative_orders),
            "symbol_metadata": {
                name: metadata.to_dict()
                for name, metadata in self.symbol_metadata.items()
            },
        }


def collect_derivative_orders(equations: list[EquationNode]) -> dict[str, int]:
    """Collect the highest derivative order referenced for each base symbol."""
    derivative_orders: dict[str, int] = {}
    for equation in equations:
        for node in walk_expression(equation.lhs):
            if isinstance(node, DerivativeNode):
                derivative_orders[node.base] = max(derivative_orders.get(node.base, 0), node.order)
        for node in walk_expression(equation.rhs):
            if isinstance(node, DerivativeNode):
                derivative_orders[node.base] = max(derivative_orders.get(node.base, 0), node.order)
    return dict(sorted(derivative_orders.items()))


def derive_state_list(derivative_orders: dict[str, int]) -> tuple[str, ...]:
    """Create the canonical ordered list of state names."""
    states: list[str] = []
    for base, order in sorted(derivative_orders.items()):
        for derivative_order in range(order):
            states.append(state_name(base, derivative_order))
    return tuple(states)
