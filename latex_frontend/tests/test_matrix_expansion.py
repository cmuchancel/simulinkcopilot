from __future__ import annotations

from canonicalize.first_order import build_first_order_system
from ir.equation_dict import equation_to_string
from latex_frontend.matrix_expansion import expand_matrix_syntax
from latex_frontend.translator import translate_latex
from states.extract_states import extract_states


def test_vector_assignment_expands_to_scalar_equations() -> None:
    expanded = expand_matrix_syntax(r"[u_1; u_2] = [a+b; c]")
    assert expanded == "u_1 = a+b\nu_2 = c"


def test_row_vector_transpose_expands_to_column_equations() -> None:
    expanded = expand_matrix_syntax(r"[u_1, u_2]^T = [a, b]^T")
    assert expanded == "u_1 = a\nu_2 = b"


def test_matrix_symbol_definitions_expand_matrix_vector_product() -> None:
    equations = translate_latex(
        r"""
A = \begin{bmatrix} 0 & 1 \\ -k/m & -c/m \end{bmatrix}
B = \begin{bmatrix} 0 \\ 1/m \end{bmatrix}
x = \begin{bmatrix} x_1 \\ x_2 \end{bmatrix}
u = \begin{bmatrix} u_1 \end{bmatrix}
\dot{x} = Ax + Bu
"""
    )
    rendered = [equation_to_string(equation) for equation in equations]
    assert len(rendered) == 2
    assert any("D1_x_1 = x_2" == line for line in rendered)
    assert any("D1_x_2" in line and "x_1" in line and "x_2" in line and "u_1" in line for line in rendered)


def test_matrix_expansion_flows_into_state_extraction_and_first_order() -> None:
    equations = translate_latex(
        r"""
A = \begin{bmatrix} 0 & 1 \\ -k/m & -c/m \end{bmatrix}
B = \begin{bmatrix} 0 \\ 1/m \end{bmatrix}
x = \begin{bmatrix} x_1 \\ x_2 \end{bmatrix}
u = \begin{bmatrix} u_1 \end{bmatrix}
\dot{x} = Ax + Bu
"""
    )
    extraction = extract_states(
        equations,
        mode="configured",
        symbol_config={"u_1": "input", "k": "parameter", "c": "parameter", "m": "parameter"},
    )
    first_order = build_first_order_system(equations, extraction=extraction)
    assert first_order["states"] == ["x_1", "x_2"]
    assert extraction.inputs == ("u_1",)
    assert extraction.parameters == ("c", "k", "m")
