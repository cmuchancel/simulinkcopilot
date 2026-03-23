"""Tokenizer for a deterministic subset of LaTeX ODE syntax."""

from __future__ import annotations

from dataclasses import dataclass

from latex_frontend.symbols import SUPPORTED_LATEX_COMMANDS, UnsupportedSyntaxError


SUPPORTED_COMMANDS = SUPPORTED_LATEX_COMMANDS


@dataclass(frozen=True)
class Token:
    """Single token emitted by the deterministic LaTeX tokenizer."""

    kind: str
    value: str
    position: int


def tokenize(text: str) -> list[Token]:
    """Tokenize a restricted LaTeX expression deterministically."""
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        char = text[i]

        if char in " \t\r":
            i += 1
            continue

        if char == "\n":
            tokens.append(Token("NEWLINE", "\n", i))
            i += 1
            continue

        if char == "\\":
            if i + 1 < len(text) and text[i + 1] == "\\":
                tokens.append(Token("NEWLINE", "\\\\", i))
                i += 2
                continue

            start = i
            i += 1
            command_start = i
            while i < len(text) and text[i].isalnum():
                i += 1
            command = text[command_start:i]
            if not command:
                raise UnsupportedSyntaxError(f"Unsupported LaTeX escape at position {start}.")
            if command not in SUPPORTED_COMMANDS:
                raise UnsupportedSyntaxError(
                    f"Unsupported LaTeX command '\\{command}' at position {start}."
                )
            tokens.append(Token("COMMAND", command, start))
            continue

        if char.isalpha():
            start = i
            name, i = _consume_identifier(text, i)
            tokens.append(Token("IDENT", name, start))
            continue

        if char.isdigit() or (char == "." and i + 1 < len(text) and text[i + 1].isdigit()):
            start = i
            has_decimal = char == "."
            i += 1
            while i < len(text) and (text[i].isdigit() or (text[i] == "." and not has_decimal)):
                if text[i] == ".":
                    has_decimal = True
                i += 1
            tokens.append(Token("NUMBER", text[start:i], start))
            continue

        single_tokens = {
            "+": "PLUS",
            "-": "MINUS",
            "*": "STAR",
            "/": "SLASH",
            "^": "CARET",
            "=": "EQUALS",
            ",": "COMMA",
            "(": "LPAREN",
            ")": "RPAREN",
            "{": "LBRACE",
            "}": "RBRACE",
        }
        if char in single_tokens:
            tokens.append(Token(single_tokens[char], char, i))
            i += 1
            continue

        raise UnsupportedSyntaxError(f"Unsupported character {char!r} at position {i}.")

    tokens.append(Token("EOF", "", len(text)))
    return tokens


def _consume_identifier(text: str, start: int) -> tuple[str, int]:
    """Consume a full identifier including repeated subscript segments."""
    i = start
    while i < len(text) and text[i].isalpha():
        i += 1

    if i - start == 2 and (i >= len(text) or text[i] not in "_0123456789"):
        return text[start], start + 1

    name = [text[start:i]]

    while i < len(text) and text[i].isdigit():
        name.append(text[i])
        i += 1

    while i < len(text) and text[i] == "_":
        name.append(text[i])
        i += 1
        if i < len(text) and text[i] == "{":
            name.append(text[i])
            i += 1
            while i < len(text) and text[i] != "}":
                if not (text[i].isalnum() or text[i] == "_"):
                    raise UnsupportedSyntaxError(
                        f"Unsupported character {text[i]!r} inside subscript at position {i}."
                    )
                name.append(text[i])
                i += 1
            if i >= len(text):
                raise UnsupportedSyntaxError("Unterminated subscript brace.")
            name.append(text[i])
            i += 1
            continue

        if i >= len(text) or not (text[i].isalnum() or text[i] == "_"):
            raise UnsupportedSyntaxError(f"Malformed identifier subscript at position {i}.")
        while i < len(text) and (text[i].isalnum() or text[i] == "_"):
            name.append(text[i])
            i += 1

    return "".join(name), i
