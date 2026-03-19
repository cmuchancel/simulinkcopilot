from __future__ import annotations

import unittest

import sympy

from canonicalize_v2.first_order import build_first_order_system
from canonicalize_v2.linearity_check import analyze_first_order_linearity
from canonicalize_v2.nonlinear_forms import build_explicit_system_form
from canonicalize_v2.solve_for_derivatives import solve_for_highest_derivatives
from canonicalize_v2.state_space import build_state_space_system
from ir_v2.equation_dict import equation_to_string, expression_from_dict, expression_to_sympy, matrix_from_dict
from latex_frontend_v2.symbols import DeterministicCompileError
from latex_frontend_v2.translator import translate_latex
from states_v2.extract_states import extract_states


class CanonicalizeTests(unittest.TestCase):
    def test_solve_for_mass_spring_derivative(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
        solved = solve_for_highest_derivatives(equations)
        self.assertEqual(len(solved), 1)
        self.assertEqual(equation_to_string(solved[0].equation).replace(" ", ""), "D2_x=(-D1_x*c-k*x+u)/m".replace(" ", ""))
        self.assertEqual(solved[0].equation.rhs.__class__.__name__, "DivNode")
        rhs = expression_to_sympy(solved[0].equation.rhs)
        x = sympy.Symbol("x")
        m = sympy.Symbol("m")
        c = sympy.Symbol("c")
        k = sympy.Symbol("k")
        u = sympy.Symbol("u")
        d1x = sympy.Symbol("D1_x")
        self.assertEqual(sympy.simplify(rhs - (u - c * d1x - k * x) / m), 0)

    def test_first_order_conversion_mass_spring(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
        first_order = build_first_order_system(equations)
        mapping = {
            entry["state"]: sympy.simplify(expression_to_sympy(expression_from_dict(entry["rhs"])))
            for entry in first_order["state_equations"]
        }
        self.assertEqual(first_order["states"], ["x", "x_dot"])
        self.assertEqual(sympy.sstr(mapping["x"]), "x_dot")
        x = sympy.Symbol("x")
        x_dot = sympy.Symbol("x_dot")
        u = sympy.Symbol("u")
        c = sympy.Symbol("c")
        k = sympy.Symbol("k")
        m = sympy.Symbol("m")
        self.assertEqual(sympy.simplify(mapping["x_dot"] - (u - c * x_dot - k * x) / m), 0)

    def test_state_space_conversion_mass_spring(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
        first_order = build_first_order_system(equations, extraction=extract_states(equations))
        state_space = build_state_space_system(first_order)
        A = matrix_from_dict(state_space["A"])
        B = matrix_from_dict(state_space["B"])
        m = sympy.Symbol("m")
        c = sympy.Symbol("c")
        k = sympy.Symbol("k")
        self.assertEqual(A, sympy.Matrix([[0, 1], [-k / m, -c / m]]))
        self.assertEqual(B, sympy.Matrix([[0], [1 / m]]))

    def test_third_order_system_generates_full_state_chain(self) -> None:
        equations = translate_latex(r"a\frac{d^3 x}{dt^3}+b\ddot{x}+c\dot{x}+kx=u")
        first_order = build_first_order_system(equations)
        self.assertEqual(first_order["states"], ["x", "x_dot", "x_ddot"])
        mapping = {
            entry["state"]: sympy.simplify(expression_to_sympy(expression_from_dict(entry["rhs"])))
            for entry in first_order["state_equations"]
        }
        self.assertEqual(sympy.sstr(mapping["x"]), "x_dot")
        self.assertEqual(sympy.sstr(mapping["x_dot"]), "x_ddot")

    def test_coupled_second_order_system_solves_multiple_targets(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"m_1\ddot{x_1}+c(\dot{x_1}-\dot{x_2})+k(x_1-x_2)=u",
                    r"m_2\ddot{x_2}+c(\dot{x_2}-\dot{x_1})+k(x_2-x_1)=0",
                ]
            )
        )
        solved = solve_for_highest_derivatives(equations)
        self.assertEqual([(item.base, item.order) for item in solved], [("x_1", 2), ("x_2", 2)])

    def test_mixed_first_and_second_order_system_builds(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"m\ddot{x}+c\dot{x}+kx+y=u",
                    r"\dot{y}=-ay+x",
                ]
            )
        )
        first_order = build_first_order_system(equations)
        self.assertEqual(first_order["states"], ["x", "x_dot", "y"])

    def test_duplicate_inconsistent_derivative_definitions_raise(self) -> None:
        equations = translate_latex("\\dot{x}=y\n\\dot{x}=z")
        with self.assertRaises(DeterministicCompileError):
            solve_for_highest_derivatives(equations)

    def test_implicit_nonlinear_derivative_coupling_raises(self) -> None:
        equations = translate_latex(r"\dot{x}+\dot{x}^2=u")
        with self.assertRaises(DeterministicCompileError):
            solve_for_highest_derivatives(equations)

    def test_implicit_trigonometric_derivative_coupling_raises(self) -> None:
        equations = translate_latex(r"\dot{x}+\sin(\dot{x})=u")
        with self.assertRaises(DeterministicCompileError):
            solve_for_highest_derivatives(equations)

    def test_linearity_check_detects_nonlinear_state_dependence(self) -> None:
        equations = translate_latex(r"\dot{x}=u-kx^3")
        first_order = build_first_order_system(equations)
        analysis = analyze_first_order_linearity(first_order)
        self.assertFalse(analysis["is_linear"])
        with self.assertRaises(DeterministicCompileError):
            build_state_space_system(first_order)

    def test_explicit_system_form_exposes_rhs(self) -> None:
        equations = translate_latex(r"\dot{x}=u-kx^3")
        first_order = build_first_order_system(equations)
        explicit = build_explicit_system_form(first_order)
        self.assertEqual(explicit["form"], "explicit_first_order")
        self.assertIn("x", explicit["rhs"])


if __name__ == "__main__":
    unittest.main()
