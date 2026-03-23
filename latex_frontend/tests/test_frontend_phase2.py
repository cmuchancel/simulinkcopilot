from __future__ import annotations

import unittest

from ir.equation_dict import equation_to_dict, equation_to_string
from latex_frontend.normalize import normalize_latex
from latex_frontend.symbols import UnsupportedSyntaxError
from latex_frontend.tokenizer import tokenize
from latex_frontend.translator import translate_latex


class FrontendPhase2Tests(unittest.TestCase):
    def test_normalizes_fractional_third_derivative(self) -> None:
        normalized = normalize_latex(r"\frac{d^3 x}{dt^3}+a\frac{dx}{dt}=u")
        self.assertEqual(normalized, r"\deriv{3}{x}+a\deriv{1}{x}=u")

    def test_normalizes_time_dependent_inputs_and_theta(self) -> None:
        normalized = normalize_latex(r"m\ddot{x}+kx=u(t) \quad \ddot{\theta}=0".replace(r" \quad ", " "))
        self.assertIn("u", normalized)
        self.assertNotIn("u(t)", normalized)
        self.assertIn(r"\ddot{theta}", normalized)

    def test_normalizes_trailing_derivative_subscripts_and_omega(self) -> None:
        normalized = normalize_latex(r"\dot{\theta}_1=\omega_1 \quad \ddot{\theta}_2=0".replace(r" \quad ", " "))
        self.assertIn(r"\dot{theta_1}=omega_1", normalized)
        self.assertIn(r"\ddot{theta_2}=0", normalized)

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
        self.assertEqual(equation_to_string(equations[0]), "D2_theta + g*sin(theta)/l = 0")

    def test_trig_and_log_functions_translate(self) -> None:
        equations = translate_latex(r"\dot{x}=\cos(\theta)+\tan(x)+\sec(y)+\ln(z)")
        self.assertEqual(equation_to_string(equations[0]), "D1_x = log(z) + cos(theta) + tan(x) + sec(y)")

    def test_bare_trig_function_arguments_normalize(self) -> None:
        normalized = normalize_latex(r"\dot{x}=\cos\theta+\sin x")
        self.assertEqual(normalized, r"\dot{x}=\cos(theta)+\sin(x)")

    def test_pi_constant_normalizes_to_numeric_literal(self) -> None:
        normalized = normalize_latex(r"\phi_e=\pi R^2")
        self.assertIn("3.141592653589793", normalized)

    def test_exponential_expression_translates(self) -> None:
        equations = translate_latex(r"\dot{x}=\exp(-ax)")
        self.assertEqual(equation_to_string(equations[0]), "D1_x = exp(-a*x)")

    def test_absolute_value_and_derivative_time_arguments_normalize(self) -> None:
        normalized = normalize_latex(r"m\ddot{x}(t)+(c_1+c_2\lvert\dot{x}(t)\rvert)\dot{x}(t)+kx(t)=F(t)")
        self.assertEqual(normalized, r"m\ddot{x}+(c_1+c_2\abs(\dot{x}))\dot{x}+kx=F")

    def test_absolute_value_and_sqrt_translate(self) -> None:
        equations = translate_latex(r"\dot{x}=\sqrt{x}+\lvert y \rvert")
        self.assertEqual(equation_to_string(equations[0]), "D1_x = sqrt(x) + Abs(y)")

    def test_multi_argument_functions_translate(self) -> None:
        equations = translate_latex(r"\dot{x}=\atan2(y,x)+\min(a,b)+\max(c,d)+\sat(u,u_{min},u_{max})")
        rendered = equation_to_string(equations[0])
        self.assertIn("atan2(y, x)", rendered)
        self.assertIn("Min(a, b)", rendered)
        self.assertIn("Max(c, d)", rendered)
        self.assertIn("sat(u, u_min, u_max)", rendered)

    def test_nonlinear_damping_equation_translates(self) -> None:
        equations = translate_latex(
            r"m\ddot{x}(t) + \left(c_1 + c_2 \lvert \dot{x}(t) \rvert \right)\dot{x}(t) + kx(t) = F(t)"
        )
        rendered = equation_to_string(equations[0])
        self.assertIn("Abs(D1_x)", rendered)
        self.assertIn("D2_x", rendered)
        self.assertIn("F", rendered)

    def test_subscripted_derivative_targets_translate(self) -> None:
        equations = translate_latex(r"\dot{\theta}_1=\omega_1" + "\n" + r"\dot{\omega}_1=-\sin(\theta_1-\theta_2)")
        self.assertEqual(equation_to_string(equations[0]), "D1_theta_1 = omega_1")
        self.assertEqual(equation_to_string(equations[1]), "D1_omega_1 = -sin(theta_1 - theta_2)")

    def test_left_right_and_multiple_subscripts_normalize(self) -> None:
        equations = translate_latex(r"\left(k_{12}\right)(x_1-x_2)=0")
        lhs = equation_to_dict(equations[0])["lhs"]
        self.assertEqual(lhs["op"], "mul")

    def test_malformed_derivative_fraction_raises(self) -> None:
        with self.assertRaises(UnsupportedSyntaxError):
            normalize_latex(r"\frac{d^2 x}{dt^3}=0")

    def test_arbitrary_symbol_commands_normalize_to_identifiers(self) -> None:
        normalized = normalize_latex(r"\dot{\phi_cart} + \alpha_drive x = \beta_input(t)")
        self.assertEqual(normalized, r"\dot{phi_cart} + alpha_drive x = beta_input")

    def test_multi_letter_identifiers_tokenize_as_single_symbols(self) -> None:
        tokens = tokenize("mass_cart*x_state + force_drive")
        self.assertEqual(tokens[0].value, "mass_cart")
        self.assertEqual(tokens[2].value, "x_state")
        self.assertEqual(tokens[4].value, "force_drive")

    def test_arbitrary_symbol_names_translate(self) -> None:
        equations = translate_latex(r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive")
        rendered = equation_to_string(equations[0])
        self.assertIn("D2_x_cart*m_cart", rendered)
        self.assertIn("D1_x_cart*c_damper", rendered)
        self.assertIn("k_spring*x_cart", rendered)
        self.assertTrue(rendered.endswith("= F_drive"))

    def test_equation_environment_wrappers_are_ignored(self) -> None:
        equations = translate_latex("\\begin{equation}\n\\dot{x}=ax+b\n\\end{equation}")
        self.assertEqual(equation_to_string(equations[0]), "D1_x = a*x + b")


if __name__ == "__main__":
    unittest.main()
