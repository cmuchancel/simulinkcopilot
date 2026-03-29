from __future__ import annotations

from dataclasses import replace

import sympy
import pytest

from canonicalize.descriptor_system import (
    build_descriptor_system_from_dae,
    build_descriptor_system_from_first_order,
)
from canonicalize.first_order import build_first_order_system
from canonicalize.dae_reduction import reduce_semi_explicit_dae
from canonicalize.dae_system import build_semi_explicit_dae_system
from ir.equation_dict import matrix_from_dict
from ir.expression_nodes import EquationNode, NumberNode, SymbolNode
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex
from states.extract_states import analyze_state_extraction


def test_build_descriptor_system_from_first_order_explicit_linear_system() -> None:
    equations = translate_latex(r"\dot{x}=-ax+bu")

    first_order = build_first_order_system(
        equations,
        extraction=analyze_state_extraction(
            equations,
            mode="configured",
            symbol_config={"a": "parameter", "b": "parameter", "u": "input"},
        ).extraction,
    )
    descriptor = build_descriptor_system_from_first_order(first_order)

    a = sympy.Symbol("a")
    b = sympy.Symbol("b")
    assert matrix_from_dict(descriptor["E"]) == sympy.Matrix([[1]])
    assert matrix_from_dict(descriptor["A"]) == sympy.Matrix([[-a]])
    assert matrix_from_dict(descriptor["B"]) == sympy.Matrix([[b]])
    assert descriptor["algebraic_variables"] == []


def test_build_descriptor_system_from_dae_preserves_linear_algebraic_constraint_structure() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}+y=u",
                "x+y=1",
            ]
        )
    )

    analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
    descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

    assert descriptor["differential_states"] == ["x"]
    assert descriptor["algebraic_variables"] == ["y"]
    assert matrix_from_dict(descriptor["E"]) == sympy.Matrix([[1, 0], [0, 0]])
    assert matrix_from_dict(descriptor["A"]) == sympy.Matrix([[0, -1], [-1, -1]])
    assert matrix_from_dict(descriptor["B"]) == sympy.Matrix([[1], [0]])
    assert matrix_from_dict(descriptor["offset"]) == sympy.Matrix([[0], [1]])


def test_analyze_state_extraction_exposes_descriptor_system_for_nonreduced_linear_dae() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}+y=u",
                "x+y=1",
            ]
        )
    )

    analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})

    assert analysis.descriptor_system is not None
    assert analysis.dae_system.reduced_to_explicit is True
    assert analysis.descriptor_system["algebraic_variables"] == ["y"]


def test_build_descriptor_system_from_dae_rejects_higher_order_differential_structure() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\ddot{x}+y=0",
                "x+y=1",
            ]
        )
    )
    extraction = analyze_state_extraction(equations).extraction
    reduction = reduce_semi_explicit_dae(equations)
    dae_system = build_semi_explicit_dae_system(extraction, reduction)

    with pytest.raises(DeterministicCompileError, match="first-order differential states only"):
        build_descriptor_system_from_dae(dae_system, extraction)


def test_build_descriptor_system_from_first_order_rejects_nonlinear_system() -> None:
    equations = translate_latex(r"\dot{x}=x^2+u")
    analysis = analyze_state_extraction(
        equations,
        mode="configured",
        symbol_config={"u": "input"},
    )
    first_order = build_first_order_system(equations, extraction=analysis.extraction)

    with pytest.raises(DeterministicCompileError, match="not linear in states and inputs"):
        build_descriptor_system_from_first_order(first_order)


def test_build_descriptor_system_from_dae_rejects_algebraic_derivative_terms() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}=0",
                "y=0",
            ]
        )
    )
    analysis = analyze_state_extraction(equations)
    dae_system = replace(
        analysis.dae_system,
        algebraic_variables=("y",),
        algebraic_constraints=(EquationNode(lhs=SymbolNode("D1_y"), rhs=NumberNode(0)),),
    )

    with pytest.raises(DeterministicCompileError, match="retains dependence on \\['D1_y'\\]"):
        build_descriptor_system_from_dae(dae_system, analysis.extraction)


def test_build_descriptor_system_from_dae_rejects_non_square_system() -> None:
    equations = translate_latex(r"\dot{x}=0")
    analysis = analyze_state_extraction(equations)
    dae_system = replace(
        analysis.dae_system,
        algebraic_constraints=(EquationNode(lhs=SymbolNode("x"), rhs=NumberNode(1)),),
    )

    with pytest.raises(DeterministicCompileError, match="requires a square first-order semi-explicit DAE"):
        build_descriptor_system_from_dae(dae_system, analysis.extraction)
