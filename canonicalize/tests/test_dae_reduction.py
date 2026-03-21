from __future__ import annotations

import sympy

from canonicalize.dae_reduction import reduce_semi_explicit_dae
from ir.equation_dict import equation_to_residual, equation_to_string, expression_to_sympy
from latex_frontend.translator import translate_latex


def test_reduce_semi_explicit_dae_solves_single_algebraic_variable() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}=-z",
                "z-x=0",
            ]
        )
    )

    reduction = reduce_semi_explicit_dae(equations)

    assert set(reduction.solved_algebraic_variables) == {"z"}
    assert equation_to_string(reduction.solved_algebraic_variables["z"]) == "z = x"
    assert reduction.residual_constraints == []
    assert [equation_to_string(equation) for equation in reduction.equations] == ["D1_x = -x"]


def test_reduce_semi_explicit_dae_handles_coupled_algebraic_variables() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}=-(z_1+z_2)",
                "z_1-z_2=0",
                "z_2-kx=0",
            ]
        )
    )

    reduction = reduce_semi_explicit_dae(equations)

    assert set(reduction.solved_algebraic_variables) == {"z_1", "z_2"}
    z1_rhs = expression_to_sympy(reduction.solved_algebraic_variables["z_1"].rhs)
    z2_rhs = expression_to_sympy(reduction.solved_algebraic_variables["z_2"].rhs)
    k = sympy.Symbol("k")
    x = sympy.Symbol("x")
    assert sympy.simplify(z1_rhs - k * x) == 0
    assert sympy.simplify(z2_rhs - k * x) == 0
    assert [equation_to_string(equation) for equation in reduction.equations] == ["D1_x = -2*k*x"]


def test_reduce_semi_explicit_dae_preserves_ambiguous_constraint_system() -> None:
    equations = translate_latex(
        "\n".join(
            [
                r"\dot{x}=y",
                "y^2-x=0",
            ]
        )
    )

    reduction = reduce_semi_explicit_dae(equations)

    assert reduction.solved_algebraic_variables == {}
    assert len(reduction.residual_constraints) == 1
    x = sympy.Symbol("x")
    y = sympy.Symbol("y")
    assert sympy.simplify(equation_to_residual(reduction.residual_constraints[0]) - (y**2 - x)) == 0
