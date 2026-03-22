from __future__ import annotations

import pytest

from ir.expression_nodes import NumberNode, SymbolNode
from latex_frontend.parser import Parser
from latex_frontend.symbols import UnsupportedSyntaxError
from latex_frontend.tokenizer import Token


def _parser(tokens: list[Token]) -> Parser:
    return Parser(tokens=tokens)


def test_parse_document_skips_newlines_before_eof() -> None:
    parser = _parser([Token("NEWLINE", "\n", 0), Token("EOF", "", 1)])
    assert parser.parse_document() == []


def test_parse_primary_handles_float_literals() -> None:
    parser = _parser([Token("NUMBER", "1.5", 0), Token("EOF", "", 3)])
    node = parser.parse_primary()
    assert isinstance(node, NumberNode)
    assert node.value == 1.5


def test_parse_primary_rejects_unknown_commands_and_unexpected_tokens() -> None:
    parser = _parser([Token("COMMAND", "mystery", 0), Token("EOF", "", 8)])
    with pytest.raises(UnsupportedSyntaxError, match="Unsupported command"):
        parser.parse_primary()

    parser = _parser([Token("EQUALS", "=", 0), Token("EOF", "", 1)])
    with pytest.raises(UnsupportedSyntaxError, match="Unexpected token EQUALS"):
        parser.parse_primary()


def test_parse_derivative_and_general_derivative_require_symbol_targets() -> None:
    parser = _parser(
        [
            Token("COMMAND", "dot", 0),
            Token("LBRACE", "{", 4),
            Token("NUMBER", "1", 5),
            Token("PLUS", "+", 6),
            Token("IDENT", "x", 7),
            Token("RBRACE", "}", 8),
            Token("EOF", "", 9),
        ]
    )
    with pytest.raises(UnsupportedSyntaxError, match="Derivative arguments must be single symbols"):
        parser.parse_derivative(order=1)

    parser = _parser(
        [
            Token("COMMAND", "deriv", 0),
            Token("LBRACE", "{", 6),
            Token("NUMBER", "1.5", 7),
            Token("RBRACE", "}", 10),
            Token("LBRACE", "{", 11),
            Token("IDENT", "x", 12),
            Token("RBRACE", "}", 13),
            Token("EOF", "", 14),
        ]
    )
    with pytest.raises(UnsupportedSyntaxError, match="explicit integer order"):
        parser.parse_general_derivative()

    parser = _parser(
        [
            Token("COMMAND", "deriv", 0),
            Token("LBRACE", "{", 6),
            Token("NUMBER", "2", 7),
            Token("RBRACE", "}", 8),
            Token("LBRACE", "{", 9),
            Token("IDENT", "x", 10),
            Token("PLUS", "+", 11),
            Token("IDENT", "y", 12),
            Token("RBRACE", "}", 13),
            Token("EOF", "", 14),
        ]
    )
    with pytest.raises(UnsupportedSyntaxError, match="Derivative arguments must be single symbols"):
        parser.parse_general_derivative()


def test_parse_group_or_symbol_and_group_error_paths() -> None:
    parser = _parser([Token("IDENT", "x", 0), Token("EOF", "", 1)])
    node = parser.parse_group_or_symbol()
    assert isinstance(node, SymbolNode)
    assert node.name == "x"

    parser = _parser([Token("NUMBER", "1", 0), Token("EOF", "", 1)])
    with pytest.raises(UnsupportedSyntaxError, match="Expected grouped expression"):
        parser.parse_group()


def test_expect_reports_mismatched_tokens() -> None:
    parser = _parser([Token("IDENT", "x", 0), Token("EOF", "", 1)])
    with pytest.raises(UnsupportedSyntaxError, match="Expected EQUALS"):
        parser.expect("EQUALS")
