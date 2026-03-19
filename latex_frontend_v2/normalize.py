"""Deterministic preprocessing for the restricted LaTeX grammar."""

from __future__ import annotations

import re

from latex_frontend_v2.symbols import UnsupportedSyntaxError

_DERIVATIVE_FRACTION_RE = re.compile(
    r"""
    \\frac
    \s*\{
        \s*d
        (?:\s*\^\s*(?:\{(?P<num_order_braced>\d+)\}|(?P<num_order_plain>\d+)))?
        \s*(?P<symbol>[A-Za-z][A-Za-z0-9_]*(?:_\{?[A-Za-z0-9_]+\}?)?)
        \s*
    \}
    \s*\{
        \s*d(?P<independent>[A-Za-z]+)
        (?:\s*\^\s*(?:\{(?P<den_order_braced>\d+)\}|(?P<den_order_plain>\d+)))?
        \s*
    \}
    """,
    re.VERBOSE,
)

_BRACED_SUBSCRIPT_RE = re.compile(r"([A-Za-z][A-Za-z0-9]*)_\{([A-Za-z0-9_]+)\}")
_TRAILING_SUBSCRIPT_DERIVATIVE_RE = re.compile(
    r"""
    \\(?P<command>dot|ddot)
    \s*\{
        (?P<symbol>[A-Za-z][A-Za-z0-9_]*)
    \}
    \s*_
    (?P<subscript>\{?[A-Za-z0-9_]+\}?)
    """,
    re.VERBOSE,
)
_TRAILING_SUBSCRIPT_GENERAL_DERIVATIVE_RE = re.compile(
    r"""
    \\deriv
    \s*\{
        (?P<order>\d+)
    \}
    \s*\{
        (?P<symbol>[A-Za-z][A-Za-z0-9_]*)
    \}
    \s*_
    (?P<subscript>\{?[A-Za-z0-9_]+\}?)
    """,
    re.VERBOSE,
)
_TIME_DEPENDENT_SYMBOL_RE = re.compile(
    r"(?<!\\)\b(?P<name>[A-Za-z][A-Za-z0-9_]*(?:_\{?[A-Za-z0-9_]+\}?)?)\s*\(\s*t\s*\)"
)

_GREEK_SYMBOL_MAP = {
    r"\theta": "q",
    r"\omega": "w",
}


def _normalize_symbol_name(symbol: str) -> str:
    return _BRACED_SUBSCRIPT_RE.sub(r"\1_\2", symbol)


def _replace_derivative_fraction(match: re.Match[str]) -> str:
    order = (
        match.group("num_order_braced")
        or match.group("num_order_plain")
        or match.group("den_order_braced")
        or match.group("den_order_plain")
        or "1"
    )
    denominator_order = match.group("den_order_braced") or match.group("den_order_plain") or "1"
    numerator_order = match.group("num_order_braced") or match.group("num_order_plain") or "1"

    if numerator_order != denominator_order:
        raise UnsupportedSyntaxError(
            "Derivative fraction order mismatch is unsupported in the deterministic frontend."
        )

    independent = match.group("independent")
    if independent != "t":
        raise UnsupportedSyntaxError(
            f"Only derivatives with respect to t are supported, found d{independent}."
        )

    symbol = _normalize_symbol_name(match.group("symbol"))
    return rf"\deriv{{{order}}}{{{symbol}}}"


def _move_derivative_subscript_inside_group(match: re.Match[str]) -> str:
    symbol = _normalize_symbol_name(match.group("symbol"))
    subscript = match.group("subscript")
    if subscript.startswith("{") and subscript.endswith("}"):
        subscript = subscript[1:-1]
    return rf"\{match.group('command')}{{{symbol}_{subscript}}}"


def _move_general_derivative_subscript_inside_group(match: re.Match[str]) -> str:
    symbol = _normalize_symbol_name(match.group("symbol"))
    subscript = match.group("subscript")
    if subscript.startswith("{") and subscript.endswith("}"):
        subscript = subscript[1:-1]
    return rf"\deriv{{{match.group('order')}}}{{{symbol}_{subscript}}}"


def normalize_latex(text: str) -> str:
    """Normalize supported LaTeX variants into the core deterministic grammar."""
    normalized = text.replace(r"\left", "").replace(r"\right", "")
    for source, target in _GREEK_SYMBOL_MAP.items():
        normalized = normalized.replace(source, target)
    normalized = _TRAILING_SUBSCRIPT_DERIVATIVE_RE.sub(_move_derivative_subscript_inside_group, normalized)
    normalized = _TRAILING_SUBSCRIPT_GENERAL_DERIVATIVE_RE.sub(
        _move_general_derivative_subscript_inside_group,
        normalized,
    )
    normalized = _BRACED_SUBSCRIPT_RE.sub(r"\1_\2", normalized)
    normalized = _TIME_DEPENDENT_SYMBOL_RE.sub(lambda match: _normalize_symbol_name(match.group("name")), normalized)

    previous = None
    while normalized != previous:
        previous = normalized
        normalized = _DERIVATIVE_FRACTION_RE.sub(_replace_derivative_fraction, normalized)

    return normalized
