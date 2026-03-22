from __future__ import annotations

import pytest

from latex_frontend.normalize import (
    _DERIVATIVE_FRACTION_RE,
    _GENERAL_DERIVATIVE_TIME_ARGUMENT_RE,
    _TRAILING_SUBSCRIPT_DERIVATIVE_RE,
    _TRAILING_SUBSCRIPT_GENERAL_DERIVATIVE_RE,
    _move_derivative_subscript_inside_group,
    _move_general_derivative_subscript_inside_group,
    _replace_derivative_fraction,
    _rewrite_absolute_delimiters,
    _rewrite_symbol_commands,
    _strip_general_derivative_time_argument,
    _strip_supported_environments,
)
from latex_frontend.symbols import UnsupportedSyntaxError


def _fraction_match(text: str):
    match = _DERIVATIVE_FRACTION_RE.search(text)
    assert match is not None
    return match


def test_replace_derivative_fraction_rejects_non_time_independent_variable() -> None:
    with pytest.raises(UnsupportedSyntaxError, match="Only derivatives with respect to t are supported"):
        _replace_derivative_fraction(_fraction_match(r"\frac{dx}{ds}"))


def test_move_derivative_subscript_inside_group_strips_braces() -> None:
    dot_match = _TRAILING_SUBSCRIPT_DERIVATIVE_RE.search(r"\dot{x}_{cart}")
    assert dot_match is not None
    assert _move_derivative_subscript_inside_group(dot_match) == r"\dot{x_cart}"

    deriv_match = _TRAILING_SUBSCRIPT_GENERAL_DERIVATIVE_RE.search(r"\deriv{3}{x}_{cart}")
    assert deriv_match is not None
    assert _move_general_derivative_subscript_inside_group(deriv_match) == r"\deriv{3}{x_cart}"

    bare_deriv_match = _TRAILING_SUBSCRIPT_GENERAL_DERIVATIVE_RE.search(r"\deriv{3}{x}_cart")
    assert bare_deriv_match is not None
    assert _move_general_derivative_subscript_inside_group(bare_deriv_match) == r"\deriv{3}{x_cart}"


def test_strip_general_derivative_time_argument_normalizes_symbol_name() -> None:
    match = _GENERAL_DERIVATIVE_TIME_ARGUMENT_RE.search(r"\deriv{4}{x_{12}}(t)")
    assert match is not None
    assert _strip_general_derivative_time_argument(match) == r"\deriv{4}{x_12}"


def test_rewrite_absolute_delimiters_handles_nested_and_unterminated_cases() -> None:
    assert _rewrite_absolute_delimiters(r"\lvert x + \lvert y \rvert \rvert") == r"\abs(x + \abs(y))"

    with pytest.raises(UnsupportedSyntaxError, match="Unterminated absolute-value delimiter"):
        _rewrite_absolute_delimiters(r"\lvert x + y")


def test_strip_supported_environments_only_removes_supported_wrappers() -> None:
    assert _strip_supported_environments(r"\begin{align}x=1\end{align}") == "x=1"
    assert _strip_supported_environments(r"\begin{bmatrix}x\end{bmatrix}") == r"\begin{bmatrix}x\end{bmatrix}"


def test_rewrite_symbol_commands_preserves_reserved_commands() -> None:
    rewritten = _rewrite_symbol_commands(r"\alpha + \dot{x} + \sin(x)")
    assert rewritten == r"alpha + \dot{x} + \sin(x)"
