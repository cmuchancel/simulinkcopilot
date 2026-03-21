from __future__ import annotations

import pytest

from canonicalize.algebraic_substitution import inline_algebraic_definitions
from ir.equation_dict import equation_to_string
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex


def test_inline_algebraic_definitions_resolves_chained_helpers() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "gain=2",
                "u=gain*k*x",
                r"m\ddot{x}+c\dot{x}=u",
            ]
        )
    )

    result = inline_algebraic_definitions(equations)

    assert len(result.equations) == 1
    expanded = equation_to_string(result.equations[0])
    assert "u" not in expanded
    assert "gain" not in expanded
    assert "2*k*x" in expanded
    assert equation_to_string(result.resolved_definitions["gain"]) == "gain = 2"
    assert equation_to_string(result.resolved_definitions["u"]) == "u = 2*k*x"


def test_inline_algebraic_definitions_rejects_cyclic_helpers() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "u=v",
                "v=u",
                r"\dot{x}=u",
            ]
        )
    )

    with pytest.raises(DeterministicCompileError, match="Cyclic algebraic helper definitions"):
        inline_algebraic_definitions(equations)


def test_inline_algebraic_definitions_rejects_duplicate_helper_definitions() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "u=kx",
                "u=cv",
                r"\dot{x}=u",
            ]
        )
    )

    with pytest.raises(DeterministicCompileError, match="defined algebraically more than once"):
        inline_algebraic_definitions(equations)
