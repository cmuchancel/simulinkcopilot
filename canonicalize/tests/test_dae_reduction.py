from __future__ import annotations

import sympy

from canonicalize import dae_reduction as dae_reduction_module
from canonicalize.dae_reduction import reduce_semi_explicit_dae
from ir.equation_dict import equation_to_residual, equation_to_string, expression_to_sympy
from ir.expression_nodes import EquationNode, NumberNode, SymbolNode
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


def test_candidate_algebraic_variables_respects_protected_symbols() -> None:
    equations = translate_latex("\n".join([r"\dot{x}=u+z", "z+x=0"]))
    candidates = dae_reduction_module._candidate_algebraic_variables(
        dynamic_equations=[equations[0]],
        algebraic_constraints=[equations[1]],
        protected_symbols={"z"},
    )
    assert candidates == []


def test_solve_algebraic_variables_covers_empty_and_not_implemented_paths(monkeypatch) -> None:
    assert dae_reduction_module._solve_algebraic_variables(algebraic_constraints=[], candidate_names=[]) == {}

    equation = EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z"))
    monkeypatch.setattr(
        dae_reduction_module.sympy,
        "solve",
        lambda *args, **kwargs: (_ for _ in ()).throw(NotImplementedError()),
    )
    assert dae_reduction_module._solve_algebraic_variables(
        algebraic_constraints=[equation],
        candidate_names=["z"],
    ) == {}


def test_solve_algebraic_variables_rejects_multiple_or_empty_solutions(monkeypatch) -> None:
    equation = EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z"))
    monkeypatch.setattr(dae_reduction_module.sympy, "solve", lambda *args, **kwargs: [{sympy.Symbol("z"): 1}, {sympy.Symbol("z"): -1}])
    assert dae_reduction_module._solve_algebraic_variables(
        algebraic_constraints=[equation],
        candidate_names=["z"],
    ) == {}

    monkeypatch.setattr(dae_reduction_module.sympy, "solve", lambda *args, **kwargs: [{sympy.Symbol("y"): 2}])
    assert dae_reduction_module._solve_algebraic_variables(
        algebraic_constraints=[equation],
        candidate_names=["z"],
    ) == {}


def test_resolve_solution_map_rejects_cycles_self_reference_and_unresolved_candidates() -> None:
    assert dae_reduction_module._resolve_solution_map({"z": sympy.Symbol("w") + 1}, ["z", "w"]) == {}
    assert dae_reduction_module._resolve_solution_map(
        {"z": sympy.Symbol("w") + 1, "w": sympy.Symbol("z") + 1},
        ["z", "w"],
    ) == {}


def test_resolve_solution_map_uses_cached_dependency_results() -> None:
    resolved = dae_reduction_module._resolve_solution_map(
        {"z": sympy.Integer(1), "w": sympy.Symbol("z") + 1},
        ["z", "w"],
    )
    assert resolved == {"z": sympy.Integer(1), "w": sympy.Integer(2)}


def test_substitute_equation_rewrites_both_sides() -> None:
    equation = EquationNode(lhs=SymbolNode("z"), rhs=SymbolNode("x"))
    substituted = dae_reduction_module._substitute_equation(
        equation,
        {sympy.Symbol("z"): sympy.Integer(2), sympy.Symbol("x"): sympy.Integer(1)},
    )
    assert equation_to_string(substituted) == "2 = 1"
