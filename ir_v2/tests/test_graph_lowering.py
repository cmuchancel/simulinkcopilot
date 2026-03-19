from __future__ import annotations

import unittest

from canonicalize_v2.first_order import build_first_order_system
from ir_v2.equation_dict import expression_to_dict
from ir_v2.expression_nodes import AddNode, MulNode, NegNode, NumberNode, PowNode, SymbolNode
from ir_v2.graph_lowering import lower_expression_graph, lower_first_order_system_graph
from ir_v2.graph_validate import validate_graph_dict
from latex_frontend_v2.symbols import DeterministicCompileError
from latex_frontend_v2.translator import translate_latex


class GraphLoweringTests(unittest.TestCase):
    def test_mass_spring_first_order_graph_contains_integrators(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u"))
        graph = lower_first_order_system_graph(first_order, name="mass_spring")
        ops = {node["op"] for node in graph["nodes"]}
        self.assertIn("integrator", ops)
        self.assertIn("state_signal", ops)
        self.assertIn("div", ops)

    def test_expression_graph_reuses_shared_subexpressions(self) -> None:
        shared = AddNode((SymbolNode("x"), SymbolNode("y")))
        expression = expression_to_dict(
            AddNode(
                (
                    PowNode(shared, NumberNode(2)),
                    PowNode(shared, NumberNode(3)),
                )
            )
        )
        graph = lower_expression_graph(expression, state_names={"x", "y"})
        fanout = {
            node["id"]: len([edge for edge in graph["edges"] if edge["src"] == node["id"]])
            for node in graph["nodes"]
            if node["op"] == "add"
        }
        self.assertEqual(sorted(fanout.values()), [0, 2])

    def test_lowering_is_repeatable(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u"))
        graph_a = lower_first_order_system_graph(first_order, name="repeatable")
        graph_b = lower_first_order_system_graph(first_order, name="repeatable")
        self.assertEqual(graph_a, graph_b)

    def test_node_type_coverage_expression_graph(self) -> None:
        expression = expression_to_dict(
            NegNode(
                MulNode(
                    (
                        SymbolNode("k"),
                        AddNode(
                            (
                                PowNode(SymbolNode("x"), NumberNode(2)),
                                MulNode((NumberNode(2), SymbolNode("u"))),
                            )
                        ),
                    )
                )
            )
        )
        graph = lower_expression_graph(
            expression,
            state_names={"x"},
            input_names={"u"},
            parameter_names={"k"},
            name="coverage",
        )
        ops = {node["op"] for node in graph["nodes"]}
        self.assertTrue({"constant", "state_signal", "symbol_input", "negate", "pow", "gain", "add"}.issubset(ops))

    def test_function_expression_graph_contains_function_nodes(self) -> None:
        graph = lower_expression_graph(
            expression_to_dict(translate_latex(r"\dot{x}=\cos(x)+\exp(u)+\ln(v)+\sec(w)")[0].rhs),
            state_names={"x"},
            input_names={"u", "v", "w"},
            name="sine_graph",
        )
        ops = {node["op"] for node in graph["nodes"]}
        self.assertTrue({"cos", "exp", "log", "sec"}.issubset(ops))

    def test_graph_validation_rejects_missing_dependency(self) -> None:
        graph = {
            "kind": "expression_graph",
            "name": "bad",
            "nodes": [{"id": "expr_0001", "op": "negate", "inputs": ["missing"]}],
            "edges": [{"src": "missing", "dst": "expr_0001", "dst_port": 0}],
            "outputs": {"result": "expr_0001"},
        }
        with self.assertRaises(DeterministicCompileError):
            validate_graph_dict(graph)

    def test_graph_validation_accepts_good_graph(self) -> None:
        expression = expression_to_dict(AddNode((SymbolNode("u"), SymbolNode("v"))))
        graph = lower_expression_graph(expression, input_names={"u", "v"})
        validated = validate_graph_dict(graph)
        self.assertEqual(validated["name"], "expression_graph")


if __name__ == "__main__":
    unittest.main()
