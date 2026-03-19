"""Utility helpers for Simulink model construction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_INVALID_BLOCK_CHARS = re.compile(r"[^0-9A-Za-z_]+")


def sanitize_block_name(name: str) -> str:
    """Return a Simulink-safe block identifier."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Block names must be non-empty strings.")

    sanitized = _INVALID_BLOCK_CHARS.sub("_", name.strip())
    sanitized = sanitized.strip("_")
    if not sanitized:
        raise ValueError(f"Block name {name!r} does not contain any valid characters.")
    if sanitized[0].isdigit():
        sanitized = f"blk_{sanitized}"
    return sanitized


def format_port(port: str | int) -> str:
    """Normalize a Simulink port reference to a string."""
    if isinstance(port, int):
        if port < 1:
            raise ValueError("Port numbers must be 1-based positive integers.")
        return str(port)

    port_text = str(port).strip()
    if not port_text:
        raise ValueError("Port references must not be empty.")
    return port_text


def validate_library_path(lib_path: str) -> str:
    """Perform lightweight validation on a Simulink library path."""
    path = str(lib_path).strip()
    if not path:
        raise ValueError("Simulink library paths must not be empty.")
    if "/" not in path:
        raise ValueError(f"Invalid Simulink library path {lib_path!r}. Expected 'library/category/block'.")
    return path


def format_position(position: Iterable[int]) -> str:
    """Convert a four-value position into MATLAB's bracketed vector syntax."""
    values = [int(value) for value in position]
    if len(values) != 4:
        raise ValueError(f"Simulink block positions require four integers, got {values!r}.")
    return "[" + " ".join(str(value) for value in values) + "]"


def matlab_param_value(value: Any) -> str:
    """Convert a Python value into a MATLAB-friendly parameter string."""
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "[" + " ".join(str(item) for item in value) + "]"
    raise TypeError(f"Unsupported parameter value type: {type(value).__name__}")


def ensure_output_dir(path: str | Path) -> Path:
    """Create an output directory if it does not already exist."""
    directory = Path(path).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory
