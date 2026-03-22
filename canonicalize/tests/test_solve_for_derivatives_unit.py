from __future__ import annotations

import pytest
import sympy

from canonicalize import solve_for_derivatives as solve_module
from ir.equation_dict import expression_to_sympy
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex


def test_solve_for_highest_derivatives_rejects_missing_derivatives() -> None:
    equations = translate_latex("x+y=1")
    with pytest.raises(DeterministicCompileError, match="No derivatives found"):
        solve_module.solve_for_highest_derivatives(equations)


def test_solve_for_highest_derivatives_rejects_underdetermined_and_algebraic_constraints() -> None:
    underdetermined = translate_latex(r"\ddot{x}+\ddot{y}=0")
    with pytest.raises(DeterministicCompileError, match="Underdetermined system"):
        solve_module.solve_for_highest_derivatives(underdetermined)

    dae_like = translate_latex("y^2-x=0\n\\dot{x}=y")
    with pytest.raises(DeterministicCompileError, match="Algebraic/DAE-like constraints are unsupported"):
        solve_module.solve_for_highest_derivatives(dae_like)


def test_solve_for_highest_derivatives_reduces_reducible_semi_explicit_dae() -> None:
    equations = translate_latex("y-x=0\n\\dot{x}=-y")

    solved = solve_module.solve_for_highest_derivatives(equations)

    assert len(solved) == 1
    assert str(solved[0].base) == "x"
    assert sympy.simplify(
        expression_to_sympy(solved[0].equation.rhs) + sympy.Symbol("x")
    ) == 0


def test_solve_for_highest_derivatives_converts_sympy_edge_cases_to_compile_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    equations = translate_latex(r"\dot{x}=u")
    target = sympy.Symbol("D1_x")

    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: (_ for _ in ()).throw(NotImplementedError("nope")))
    with pytest.raises(DeterministicCompileError, match="implicit nonlinear derivative coupling"):
        solve_module.solve_for_highest_derivatives(equations)

    overdetermined = translate_latex(r"\dot{x}=u" + "\n" + r"\dot{x}=u")
    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: [])
    with pytest.raises(DeterministicCompileError, match="Overdetermined or inconsistent system"):
        solve_module.solve_for_highest_derivatives(overdetermined)

    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: [{target: sympy.Symbol("u")}, {target: sympy.Symbol("v")}])
    with pytest.raises(DeterministicCompileError, match="Expected exactly one deterministic solution"):
        solve_module.solve_for_highest_derivatives(equations)

    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: [])
    with pytest.raises(DeterministicCompileError, match="implicit nonlinear derivative coupling"):
        solve_module.solve_for_highest_derivatives(equations)


def test_solve_for_highest_derivatives_rejects_missing_implicit_and_unresolved_solutions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one_target = translate_latex(r"\dot{x}=u")
    target = sympy.Symbol("D1_x")
    other = sympy.Symbol("D1_y")

    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: [{}])
    with pytest.raises(DeterministicCompileError, match="Failed to isolate highest derivative D1_x"):
        solve_module.solve_for_highest_derivatives(one_target)

    two_targets = translate_latex(r"\dot{x}=u" + "\n" + r"\dot{y}=v")
    monkeypatch.setattr(
        solve_module.sympy,
        "solve",
        lambda *args, **kwargs: [{target: other, other: sympy.Integer(0)}],
    )
    with pytest.raises(DeterministicCompileError, match="remains implicitly coupled"):
        solve_module.solve_for_highest_derivatives(two_targets)

    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: [{target: sympy.Symbol("u") + 1}])
    with pytest.raises(DeterministicCompileError, match="System retains unresolved algebraic constraints"):
        solve_module.solve_for_highest_derivatives(one_target)

    monkeypatch.setattr(solve_module.sympy, "nsimplify", lambda expr: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(DeterministicCompileError, match="System retains unresolved algebraic constraints"):
        solve_module.solve_for_highest_derivatives(one_target)


def test_solve_for_highest_derivatives_rejects_zero_order_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    equations = translate_latex(r"\dot{x}=u")

    monkeypatch.setattr(solve_module, "collect_derivative_orders", lambda _equations: {"x": 0})
    with pytest.raises(DeterministicCompileError, match="No derivatives found"):
        solve_module.solve_for_highest_derivatives(equations)


def test_solved_derivative_to_dict_and_nsimplify_zero_helper_path(monkeypatch: pytest.MonkeyPatch) -> None:
    equations = translate_latex(r"\dot{x}=u")
    target = sympy.Symbol("D1_x")

    monkeypatch.setattr(solve_module.sympy, "solve", lambda *args, **kwargs: [{target: sympy.Symbol("u") + sympy.Symbol("eps")}])
    monkeypatch.setattr(solve_module.sympy, "nsimplify", lambda expr: sympy.Integer(0))

    solved = solve_module.solve_for_highest_derivatives(equations)

    assert solved[0].to_dict()["base"] == "x"
