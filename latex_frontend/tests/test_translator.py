from __future__ import annotations

import unittest

from ir.equation_dict import equation_to_dict
from latex_frontend.translator import translate_latex


class TranslatorTests(unittest.TestCase):
    def test_mass_spring_equation_translates_deterministically(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
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
                                {"op": "symbol", "name": "m"},
                                {"op": "derivative", "base": "x", "order": 2},
                            ],
                        },
                        {
                            "op": "mul",
                            "args": [
                                {"op": "symbol", "name": "c"},
                                {"op": "derivative", "base": "x", "order": 1},
                            ],
                        },
                        {
                            "op": "mul",
                            "args": [
                                {"op": "symbol", "name": "k"},
                                {"op": "symbol", "name": "x"},
                            ],
                        },
                    ],
                },
                "rhs": {"op": "symbol", "name": "u"},
            },
        )

    def test_first_order_equation_translates(self) -> None:
        equations = translate_latex(r"\dot{x}=v")
        self.assertEqual(
            equation_to_dict(equations[0]),
            {
                "op": "equation",
                "lhs": {"op": "derivative", "base": "x", "order": 1},
                "rhs": {"op": "symbol", "name": "v"},
            },
        )

    def test_fraction_equation_translates(self) -> None:
        equations = translate_latex(r"\dot{v}=\frac{u-cv-kx}{m}")
        self.assertEqual(
            equation_to_dict(equations[0]),
            {
                "op": "equation",
                "lhs": {"op": "derivative", "base": "v", "order": 1},
                "rhs": {
                    "op": "div",
                    "args": [
                        {
                            "op": "add",
                            "args": [
                                {"op": "symbol", "name": "u"},
                                {
                                    "op": "neg",
                                    "args": [
                                        {
                                            "op": "mul",
                                            "args": [
                                                {"op": "symbol", "name": "c"},
                                                {"op": "symbol", "name": "v"},
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "op": "neg",
                                    "args": [
                                        {
                                            "op": "mul",
                                            "args": [
                                                {"op": "symbol", "name": "k"},
                                                {"op": "symbol", "name": "x"},
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                        {"op": "symbol", "name": "m"},
                    ],
                },
            },
        )

    def test_multi_equation_system_translates(self) -> None:
        equations = translate_latex("\\dot{x}=v\n\\dot{v}=\\frac{u-cv-kx}{m}")
        self.assertEqual(len(equations), 2)


if __name__ == "__main__":
    unittest.main()
