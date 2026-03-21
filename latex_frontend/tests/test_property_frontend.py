from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import given, settings, strategies as st

from ir.equation_dict import equation_to_string
from latex_frontend.normalize import normalize_latex
from latex_frontend.tokenizer import tokenize
from latex_frontend.translator import translate_latex

pytestmark = [pytest.mark.property]


def _format_term(coefficient: int, symbol: str) -> str:
    if coefficient == 1:
        return symbol
    if coefficient == -1:
        return f"-{symbol}"
    return f"{coefficient}{symbol}"


def _build_linear_equation(a: int, b: int, c: int) -> str:
    pieces: list[str] = []
    if a != 0:
        pieces.append(_format_term(a, "x"))
    if b != 0:
        pieces.append(_format_term(b, "u"))
    if c != 0 or not pieces:
        pieces.append(str(c))

    rhs = pieces[0]
    for piece in pieces[1:]:
        rhs += piece if piece.startswith("-") else f"+{piece}"
    return rf"\dot{{x}}={rhs}"


_coefficients = st.integers(min_value=-5, max_value=5)


@settings(max_examples=100)
@given(a=_coefficients, b=_coefficients, c=_coefficients)
def test_normalization_is_idempotent_for_generated_linear_equations(a: int, b: int, c: int) -> None:
    equation = _build_linear_equation(a, b, c)
    normalized = normalize_latex(equation)
    assert normalize_latex(normalized) == normalized


@settings(max_examples=100)
@given(a=_coefficients, b=_coefficients, c=_coefficients)
def test_tokenization_is_deterministic_for_generated_linear_equations(a: int, b: int, c: int) -> None:
    equation = normalize_latex(_build_linear_equation(a, b, c))
    first = tokenize(equation)
    second = tokenize(equation)
    assert first == second


@settings(max_examples=100)
@given(a=_coefficients, b=_coefficients, c=_coefficients)
def test_translation_is_deterministic_for_generated_linear_equations(a: int, b: int, c: int) -> None:
    equation = _build_linear_equation(a, b, c)
    first = [equation_to_string(item) for item in translate_latex(equation)]
    second = [equation_to_string(item) for item in translate_latex(equation)]
    assert first == second
