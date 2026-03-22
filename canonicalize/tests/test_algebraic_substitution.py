from __future__ import annotations

import sympy
import pytest

from canonicalize import algebraic_substitution as substitution_module
from canonicalize.algebraic_substitution import classify_algebraic_equations, inline_algebraic_definitions
from ir.equation_dict import equation_to_string
from ir.expression_nodes import EquationNode, NumberNode, SymbolNode
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


def test_classify_algebraic_equations_distinguishes_helpers_from_constraints() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "u=kx",
                "x+y=1",
                r"\dot{x}=u-y",
            ]
        )
    )

    classification = classify_algebraic_equations(equations)

    assert set(classification.helper_definitions) == {"u"}
    assert [equation_to_string(equation) for equation in classification.algebraic_constraints] == ["x + y = 1"]
    assert [equation_to_string(equation) for equation in classification.dynamic_equations] == ["D1_x = u - y"]


def test_inline_algebraic_definitions_preserves_algebraic_constraints_after_helper_substitution() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "u=kx",
                "x+y=u",
                r"\dot{x}=u-y",
            ]
        )
    )

    result = inline_algebraic_definitions(equations)

    assert [equation_to_string(equation) for equation in result.algebraic_constraints] == ["x + y = k*x"]


def test_algebraic_substitution_helper_paths_cover_time_symbol_and_empty_substitution() -> None:
    equations = translate_latex(
        "\n".join(
            [
                "t=1",
                r"\dot{x}=t",
            ]
        )
    )

    classification = classify_algebraic_equations(equations)
    assert classification.helper_definitions == {}
    assert [equation_to_string(equation) for equation in classification.algebraic_constraints] == ["t = 1"]

    passthrough = inline_algebraic_definitions(translate_latex("x+y=1"))
    assert [equation_to_string(equation) for equation in passthrough.equations] == ["x + y = 1"]
    assert substitution_module._substitute(expression=sympy.Symbol("x"), substitutions={}) == sympy.Symbol("x")
