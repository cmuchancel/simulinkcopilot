"""Deterministic preprocessing for the restricted LaTeX grammar."""

from __future__ import annotations

import re

from latex_frontend.symbols import LATEX_FUNCTION_ALIASES, RESERVED_LATEX_COMMANDS, UnsupportedSyntaxError

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
_DERIVATIVE_TIME_ARGUMENT_RE = re.compile(
    r"""
    \\(?P<command>dot|ddot)
    \s*\{
        \s*(?P<symbol>[A-Za-z][A-Za-z0-9_]*(?:_\{?[A-Za-z0-9_]+\}?)?)\s*
    \}
    \s*\(\s*t\s*\)
    """,
    re.VERBOSE,
)
_GENERAL_DERIVATIVE_TIME_ARGUMENT_RE = re.compile(
    r"""
    \\deriv
    \s*\{\s*(?P<order>\d+)\s*\}
    \s*\{
        \s*(?P<symbol>[A-Za-z][A-Za-z0-9_]*(?:_\{?[A-Za-z0-9_]+\}?)?)\s*
    \}
    \s*\(\s*t\s*\)
    """,
    re.VERBOSE,
)
_TIME_DEPENDENT_SYMBOL_RE = re.compile(
    r"(?<!\\)\b(?P<name>[A-Za-z][A-Za-z0-9_]*(?:_\{?[A-Za-z0-9_]+\}?)?)\s*\(\s*t\s*\)"
)
_BEGIN_END_ENV_RE = re.compile(r"\\(?P<command>begin|end)\s*\{\s*(?P<environment>[A-Za-z*]+)\s*\}")
_GENERIC_SYMBOL_COMMAND_RE = re.compile(r"\\(?P<command>[A-Za-z]+)")
_PI_COMMAND_RE = re.compile(r"\\pi(?![A-Za-z])")
_BARE_FUNCTION_ARGUMENT_RE = re.compile(
    rf"""
    \\(?P<function>{'|'.join(sorted(map(re.escape, LATEX_FUNCTION_ALIASES), key=len, reverse=True))})
    (?![A-Za-z])
    \s*
    (?P<argument>
        \\[A-Za-z]+(?:_\{{?[A-Za-z0-9_]+\}}?)?
        |
        [A-Za-z][A-Za-z0-9_]*(?:_\{{?[A-Za-z0-9_]+\}}?)?
    )
    """,
    re.VERBOSE,
)

_STRIPPED_ENVIRONMENTS = {"equation", "equation*", "align", "align*"}


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


def _strip_derivative_time_argument(match: re.Match[str]) -> str:
    symbol = _normalize_symbol_name(match.group("symbol"))
    return rf"\{match.group('command')}{{{symbol}}}"


def _strip_general_derivative_time_argument(match: re.Match[str]) -> str:
    symbol = _normalize_symbol_name(match.group("symbol"))
    return rf"\deriv{{{match.group('order')}}}{{{symbol}}}"


def _rewrite_absolute_delimiters(text: str) -> str:
    result: list[str] = []
    i = 0
    start_token = r"\lvert"
    end_token = r"\rvert"
    while i < len(text):
        if text.startswith(start_token, i):
            depth = 1
            inner_start = i + len(start_token)
            cursor = inner_start
            while cursor < len(text):
                if text.startswith(start_token, cursor):
                    depth += 1
                    cursor += len(start_token)
                    continue
                if text.startswith(end_token, cursor):
                    depth -= 1
                    if depth == 0:
                        inner = _rewrite_absolute_delimiters(text[inner_start:cursor].strip())
                        result.append(rf"\abs({inner})")
                        i = cursor + len(end_token)
                        break
                    cursor += len(end_token)
                    continue
                cursor += 1
            else:
                raise UnsupportedSyntaxError("Unterminated absolute-value delimiter '\\lvert ... \\rvert'.")
            continue
        result.append(text[i])
        i += 1
    return "".join(result)


def _strip_supported_environments(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group("environment") in _STRIPPED_ENVIRONMENTS:
            return ""
        return match.group(0)

    return _BEGIN_END_ENV_RE.sub(replace, text)


def _rewrite_symbol_commands(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        command = match.group("command")
        if command in RESERVED_LATEX_COMMANDS:
            return match.group(0)
        return command

    return _GENERIC_SYMBOL_COMMAND_RE.sub(replace, text)


def _wrap_bare_function_arguments(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return rf"\{match.group('function')}({match.group('argument')})"

    return _BARE_FUNCTION_ARGUMENT_RE.sub(replace, text)


def _rewrite_math_constants(text: str) -> str:
    return _PI_COMMAND_RE.sub("(3.141592653589793)", text)


def normalize_latex(text: str) -> str:
    """Normalize supported LaTeX variants into the core deterministic grammar."""
    normalized = _strip_supported_environments(text)
    normalized = normalized.replace(r"\left|", r"\lvert").replace(r"\right|", r"\rvert")
    normalized = normalized.replace(r"\left", "").replace(r"\right", "")
    normalized = _rewrite_math_constants(normalized)
    normalized = _wrap_bare_function_arguments(normalized)
    normalized = _rewrite_symbol_commands(normalized)
    normalized = _TRAILING_SUBSCRIPT_DERIVATIVE_RE.sub(_move_derivative_subscript_inside_group, normalized)
    normalized = _TRAILING_SUBSCRIPT_GENERAL_DERIVATIVE_RE.sub(
        _move_general_derivative_subscript_inside_group,
        normalized,
    )
    normalized = _BRACED_SUBSCRIPT_RE.sub(r"\1_\2", normalized)
    normalized = _DERIVATIVE_TIME_ARGUMENT_RE.sub(_strip_derivative_time_argument, normalized)
    normalized = _GENERAL_DERIVATIVE_TIME_ARGUMENT_RE.sub(_strip_general_derivative_time_argument, normalized)
    normalized = _TIME_DEPENDENT_SYMBOL_RE.sub(lambda match: _normalize_symbol_name(match.group("name")), normalized)
    normalized = _rewrite_absolute_delimiters(normalized)

    previous = None
    while normalized != previous:
        previous = normalized
        normalized = _DERIVATIVE_FRACTION_RE.sub(_replace_derivative_fraction, normalized)

    return normalized
