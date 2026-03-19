from __future__ import annotations

import unittest

from ir_v2.equation_dict import equation_from_dict, equation_to_dict
from ir_v2.expression_nodes import (
    AddNode,
    DerivativeNode,
    DivNode,
    EquationNode,
    FunctionNode,
    MulNode,
    NegNode,
    NumberNode,
    PowNode,
    SymbolNode,
)
from ir_v2.operation_catalog import OPERATION_CATALOG, node_operation_name, validate_operation_dict
from latex_frontend_v2.symbols import DeterministicCompileError


class OperationCatalogTests(unittest.TestCase):
    def test_every_supported_node_maps_to_known_operation(self) -> None:
        nodes = [
            NumberNode(1),
            SymbolNode("x"),
            DerivativeNode("x", 1),
            AddNode((NumberNode(1), SymbolNode("x"))),
            MulNode((NumberNode(2), SymbolNode("x"))),
            DivNode(SymbolNode("u"), SymbolNode("m")),
            PowNode(SymbolNode("x"), NumberNode(2)),
            NegNode(SymbolNode("x")),
            FunctionNode("cos", SymbolNode("x")),
            FunctionNode("exp", SymbolNode("x")),
            EquationNode(SymbolNode("x"), NumberNode(1)),
        ]
        for node in nodes:
            self.assertIn(node_operation_name(node), OPERATION_CATALOG)

    def test_invalid_operation_dict_raises(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            validate_operation_dict({"op": "unknown"})

    def test_equation_round_trip(self) -> None:
        equation = EquationNode(
            lhs=DerivativeNode("x", 1),
            rhs=DivNode(
                AddNode((SymbolNode("u"), NegNode(MulNode((SymbolNode("k"), SymbolNode("x")))))),
                SymbolNode("m"),
            ),
        )
        self.assertEqual(equation_to_dict(equation), equation_to_dict(equation_from_dict(equation_to_dict(equation))))


if __name__ == "__main__":
    unittest.main()
