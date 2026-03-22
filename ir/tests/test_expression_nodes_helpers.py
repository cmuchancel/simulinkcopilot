from __future__ import annotations

from ir.expression_nodes import (
    AddNode,
    FunctionNode,
    MulNode,
    NumberNode,
    SymbolNode,
    flatten_add,
    flatten_mul,
    walk_expression,
)


def test_expression_node_helpers_cover_flattening_and_function_walks() -> None:
    assert flatten_add((SymbolNode("x"), AddNode((SymbolNode("y"), NumberNode(1))))) == (
        SymbolNode("x"),
        SymbolNode("y"),
        NumberNode(1),
    )
    assert flatten_mul((SymbolNode("x"), MulNode((SymbolNode("y"), NumberNode(2))))) == (
        SymbolNode("x"),
        SymbolNode("y"),
        NumberNode(2),
    )

    walked = walk_expression(FunctionNode("sin", AddNode((SymbolNode("x"), NumberNode(3)))))
    assert [type(node).__name__ for node in walked] == ["FunctionNode", "AddNode", "SymbolNode", "NumberNode"]

