"""Shared symbolic naming helpers and frontend exceptions."""

from __future__ import annotations

import re


class LatexFrontendError(ValueError):
    """Base error for deterministic LaTeX frontend failures."""


class UnsupportedSyntaxError(LatexFrontendError):
    """Raised when the restricted grammar encounters unsupported syntax."""


class DeterministicCompileError(ValueError):
    """Raised when the symbolic pipeline cannot determine a unique result."""


_DERIVATIVE_PATTERN = re.compile(r"^D(?P<order>\d+)_(?P<base>[A-Za-z][A-Za-z0-9_]*)$")

LATEX_FUNCTION_ALIASES: dict[str, str] = {
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "sec": "sec",
    "csc": "csc",
    "cot": "cot",
    "asin": "asin",
    "acos": "acos",
    "atan": "atan",
    "arcsin": "asin",
    "arccos": "acos",
    "arctan": "atan",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
    "sech": "sech",
    "csch": "csch",
    "coth": "coth",
    "asinh": "asinh",
    "acosh": "acosh",
    "atanh": "atanh",
    "arsinh": "asinh",
    "arcosh": "acosh",
    "artanh": "atanh",
    "exp": "exp",
    "ln": "log",
    "log": "log",
}

SUPPORTED_FUNCTION_NAMES = frozenset(LATEX_FUNCTION_ALIASES.values())
SUPPORTED_LATEX_COMMANDS = frozenset({"dot", "ddot", "frac", "deriv"} | set(LATEX_FUNCTION_ALIASES))
DIRECT_SIMULINK_TRIG_FUNCTIONS = frozenset(
    {"sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh"}
)
RECIPROCAL_FUNCTION_BASES: dict[str, str] = {
    "sec": "cos",
    "csc": "sin",
    "cot": "tan",
    "sech": "cosh",
    "csch": "sinh",
    "coth": "tanh",
}
DIRECT_SIMULINK_MATH_FUNCTIONS = frozenset({"exp", "log"})


def derivative_symbol_name(base: str, order: int) -> str:
    """Return the canonical internal symbol for a derivative."""
    if order < 1:
        raise DeterministicCompileError(f"Derivative order must be >= 1, got {order}.")
    return f"D{order}_{base}"


def parse_derivative_symbol_name(name: str) -> tuple[str, int] | None:
    """Parse a canonical derivative symbol name if present."""
    match = _DERIVATIVE_PATTERN.match(name)
    if not match:
        return None
    return match.group("base"), int(match.group("order"))


def derivative_display_name(base: str, order: int) -> str:
    """Return a human-readable derivative label."""
    return f"D{order}({base})"


def state_name(base: str, order: int) -> str:
    """Return the canonical state name for a base variable and derivative order."""
    if order < 0:
        raise DeterministicCompileError(f"State order must be >= 0, got {order}.")
    if order == 0:
        return base
    if order == 1:
        return f"{base}_dot"
    if order == 2:
        return f"{base}_ddot"
    return f"{base}_d{order}"
