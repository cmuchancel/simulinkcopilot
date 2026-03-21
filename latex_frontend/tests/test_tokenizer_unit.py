from __future__ import annotations

import pytest

from latex_frontend.symbols import UnsupportedSyntaxError
from latex_frontend.tokenizer import Token, _consume_identifier, tokenize


def test_tokenize_emits_expected_newline_and_number_tokens() -> None:
    tokens = tokenize("\\\\\n\\sin x + .5")
    assert tokens[:7] == [
        Token("NEWLINE", "\\\\", 0),
        Token("NEWLINE", "\n", 2),
        Token("COMMAND", "sin", 3),
        Token("IDENT", "x", 8),
        Token("PLUS", "+", 10),
        Token("NUMBER", ".5", 12),
        Token("EOF", "", 14),
    ]


def test_tokenize_rejects_unsupported_escape_command_and_character() -> None:
    with pytest.raises(UnsupportedSyntaxError, match="Unsupported LaTeX escape"):
        tokenize("\\")

    with pytest.raises(UnsupportedSyntaxError, match=r"Unsupported LaTeX command '\\quad'"):
        tokenize(r"\quad")

    with pytest.raises(UnsupportedSyntaxError, match="Unsupported character '@'"):
        tokenize("@")


def test_consume_identifier_handles_two_letter_split_and_complex_subscripts() -> None:
    assert tokenize("ab")[:3] == [
        Token("IDENT", "a", 0),
        Token("IDENT", "b", 1),
        Token("EOF", "", 2),
    ]
    assert _consume_identifier("mass_1_2", 0) == ("mass_1_2", 8)
    assert _consume_identifier("x_{alpha_2}", 0) == ("x_{alpha_2}", 11)


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("x_{bad$}", "Unsupported character '\\$' inside subscript"),
        ("x_{bad", "Unterminated subscript brace"),
        ("x_", "Malformed identifier subscript"),
    ],
)
def test_consume_identifier_rejects_invalid_subscripts(text: str, pattern: str) -> None:
    with pytest.raises(UnsupportedSyntaxError, match=pattern):
        _consume_identifier(text, 0)
