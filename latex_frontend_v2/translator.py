"""Public translator entrypoints for deterministic LaTeX equations."""

from __future__ import annotations

from pathlib import Path

from ir_v2.equation_dict import equation_to_dict
from ir_v2.operation_catalog import validate_supported_node
from latex_frontend_v2.normalize import normalize_latex
from latex_frontend_v2.parser import Parser
from latex_frontend_v2.tokenizer import tokenize


def translate_latex(text: str):
    """Translate LaTeX equations into deterministic IR nodes."""
    parser = Parser(tokenize(normalize_latex(text)))
    equations = parser.parse_document()
    for equation in equations:
        validate_supported_node(equation)
    return equations


def translate_latex_to_dicts(text: str) -> list[dict]:
    """Translate LaTeX equations directly into canonical dictionaries."""
    return [equation_to_dict(equation) for equation in translate_latex(text)]


def translate_file(path: str | Path):
    """Translate a LaTeX source file into deterministic IR nodes."""
    return translate_latex(Path(path).read_text(encoding="utf-8"))
