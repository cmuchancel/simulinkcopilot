from __future__ import annotations

import unittest

from ir.equation_dict import equation_to_dict, equation_to_string
from latex_frontend.normalize import normalize_latex
from latex_frontend.symbols import UnsupportedSyntaxError
from latex_frontend.translator import translate_latex


class FrontendPhase2Tests(unittest.TestCase):
    def test_normalizes_fractional_third_derivative(self) -> None:
        normalized = normalize_latex(r"\frac{d^3 x}{dt^3}+a\frac{dx}{dt}=u")
        self.assertEqual(normalized, r"\deriv{3}{x}+a\deriv{1}{x}=u")

    def test_normalizes_time_dependent_inputs_and_theta(self) -> None:
        normalized = normalize_latex(r"m\ddot{x}+kx=u(t) \quad \ddot{\theta}=0".replace(r" \quad ", " "))
        self.assertIn("u", normalized)
        self.assertNotIn("u(t)", normalized)
        self.assertIn(r"\ddot{q}", normalized)

    def test_normalizes_trailing_derivative_subscripts_and_omega(self) -> None:
        normalized = normalize_latex(r"\dot{\theta}_1=\omega_1 \quad \ddot{\theta}_2=0".replace(r" \quad ", " "))
        self.assertIn(r"\dot{q_1}=w_1", normalized)
        self.assertIn(r"\ddot{q_2}=0", normalized)

    def test_parenthesized_implicit_products_translate(self) -> None:
        equations = translate_latex(r"c(\dot{x}-\dot{y})+k(x_1-x_2)=0")
        self.assertEqual(
            equation_to_dict(equations[0]),
            {
                "op": "equation",
                "lhs": {
                    "op": "add",
                    "args": [
                        {
                            "op": "mul",
                            "args": [
                                {"op": "symbol", "name": "c"},
                                {
                                    "op": "add",
                                    "args": [
                                        {"op": "derivative", "base": "x", "order": 1},
                                        {"op": "neg", "args": [{"op": "derivative", "base": "y", "order": 1}]},
                                    ],
                                },
                            ],
                        },
                        {
                            "op": "mul",
                            "args": [
                                {"op": "symbol", "name": "k"},
                                {
                                    "op": "add",
                                    "args": [
                                        {"op": "symbol", "name": "x_1"},
                                        {"op": "neg", "args": [{"op": "symbol", "name": "x_2"}]},
                                    ],
                                },
                            ],
                        },
                    ],
                },
                "rhs": {"op": "const", "value": 0},
            },
        )

    def test_nested_fraction_and_unary_minus_translate(self) -> None:
        equations = translate_latex(r"\dot{x}=-\frac{\frac{u}{m}}{1+k}")
        self.assertEqual(equation_to_dict(equations[0])["rhs"]["op"], "neg")

    def test_unary_minus_has_lower_precedence_than_power(self) -> None:
        equations = translate_latex(r"\dot{v}=-w_0^2x+u")
        self.assertEqual(equation_to_string(equations[0]), "D1_v = u - w_0**2*x")

    def test_sine_expression_translates(self) -> None:
        equations = translate_latex(r"\ddot{\theta}+\frac{g}{l}\sin(\theta)=0")
        self.assertEqual(equation_to_string(equations[0]), "D2_q + g*sin(q)/l = 0")

    def test_trig_and_log_functions_translate(self) -> None:
        equations = translate_latex(r"\dot{x}=\cos(\theta)+\tan(x)+\sec(y)+\ln(z)")
        self.assertEqual(equation_to_string(equations[0]), "D1_x = log(z) + cos(q) + tan(x) + sec(y)")

    def test_exponential_expression_translates(self) -> None:
        equations = translate_latex(r"\dot{x}=\exp(-ax)")
        self.assertEqual(equation_to_string(equations[0]), "D1_x = exp(-a*x)")

    def test_subscripted_derivative_targets_translate(self) -> None:
        equations = translate_latex(r"\dot{\theta}_1=\omega_1" + "\n" + r"\dot{\omega}_1=-\sin(\theta_1-\theta_2)")
        self.assertEqual(equation_to_string(equations[0]), "D1_q_1 = w_1")
        self.assertEqual(equation_to_string(equations[1]), "D1_w_1 = -sin(q_1 - q_2)")

    def test_left_right_and_multiple_subscripts_normalize(self) -> None:
        equations = translate_latex(r"\left(k_{12}\right)(x_1-x_2)=0")
        lhs = equation_to_dict(equations[0])["lhs"]
        self.assertEqual(lhs["op"], "mul")

    def test_malformed_derivative_fraction_raises(self) -> None:
        with self.assertRaises(UnsupportedSyntaxError):
            normalize_latex(r"\frac{d^2 x}{dt^3}=0")


if __name__ == "__main__":
    unittest.main()
