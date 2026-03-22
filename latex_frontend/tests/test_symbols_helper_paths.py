from __future__ import annotations

import pytest

from latex_frontend.symbols import (
    DeterministicCompileError,
    derivative_display_name,
    derivative_symbol_name,
    parse_derivative_symbol_name,
    state_name,
)


def test_derivative_symbol_name_requires_positive_order() -> None:
    with pytest.raises(DeterministicCompileError, match="Derivative order must be >= 1"):
        derivative_symbol_name("x", 0)


def test_parse_derivative_symbol_name_and_display_name() -> None:
    assert parse_derivative_symbol_name("plain_x") is None
    assert parse_derivative_symbol_name("D3_x") == ("x", 3)
    assert derivative_display_name("theta", 2) == "D2(theta)"


def test_state_name_handles_negative_first_second_and_higher_orders() -> None:
    with pytest.raises(DeterministicCompileError, match="State order must be >= 0"):
        state_name("x", -1)

    assert state_name("x", 0) == "x"
    assert state_name("x", 1) == "x_dot"
    assert state_name("x", 2) == "x_ddot"
    assert state_name("x", 5) == "x_d5"
