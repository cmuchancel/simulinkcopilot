from __future__ import annotations

import pytest

from latex_frontend.matrix_expansion import (
    MatrixValue,
    _add_matrices,
    _combine_add,
    _combine_mul,
    _consume_balanced,
    _consume_matrix_environment,
    _consume_scalar_segment,
    _consume_transpose_suffix,
    _evaluate_expr,
    _evaluate_product_term,
    _evaluate_lhs,
    _expand_vector_derivative,
    _has_matrix_intent,
    _match_matrix_symbol,
    _match_vector_derivative,
    _matrix_equations,
    _matrix_literal_end,
    _multiply_values,
    _parse_factors,
    _parse_matrix_literal,
    _parse_plain_symbol,
    _scale_matrix,
    _split_additive_terms,
    _split_equation,
    _split_statements,
    _split_top_level,
    _sum_terms,
    _validate_matrix_rows,
    expand_matrix_syntax,
)
from latex_frontend.symbols import UnsupportedSyntaxError


def test_matrix_value_helpers_cover_scalar_and_transpose() -> None:
    scalar = MatrixValue((("x",),))
    assert scalar.shape == (1, 1)
    assert scalar.is_scalar() is True
    assert scalar.scalar() == "x"

    matrix = MatrixValue((("a", "b"), ("c", "d")))
    assert matrix.transpose().rows == (("a", "c"), ("b", "d"))

    with pytest.raises(UnsupportedSyntaxError, match="Expected a scalar"):
        matrix.scalar()


def test_expand_matrix_syntax_handles_symbol_context_and_shape_mismatch() -> None:
    expanded = expand_matrix_syntax("A = [1, 2; 3, 4]\nB = A")
    assert expanded == ""

    with pytest.raises(UnsupportedSyntaxError, match="shape mismatch"):
        expand_matrix_syntax("[x; y] = [1, 2]")

    with pytest.raises(UnsupportedSyntaxError, match="plain symbol definition"):
        expand_matrix_syntax("x+y = [1; 2]")


def test_split_helpers_handle_nested_structures_and_missing_top_level_equality() -> None:
    statements = _split_statements("[x; y] = [1; 2]\nA = \\begin{bmatrix}1 \\\\ 2\\end{bmatrix}")
    assert statements == ["[x; y] = [1; 2]", "A = \\begin{bmatrix}1 \\\\ 2\\end{bmatrix}"]

    lhs, rhs = _split_equation("A = [1, sin(x+y)]")
    assert lhs == "A"
    assert rhs == "[1, sin(x+y)]"
    lhs, rhs = _split_equation(r"\begin{bmatrix}1 & 2\end{bmatrix} = [1, 2]")
    assert lhs == r"\begin{bmatrix}1 & 2\end{bmatrix}"
    assert rhs == "[1, 2]"

    with pytest.raises(UnsupportedSyntaxError, match="missing top-level"):
        _split_equation("A + B")

    assert _split_top_level("a,(b+c),d", row_delimiter=",") == ["a", "(b+c)", "d"]


def test_evaluate_lhs_and_expr_handle_literals_derivatives_and_context() -> None:
    context = {"x": MatrixValue((("x_1",), ("x_2",)))}

    assert _evaluate_lhs("[a; b]", context).rows == (("a",), ("b",))
    assert _evaluate_lhs("\\dot{x}", context).rows == (("\\dot{x_1}",), ("\\dot{x_2}",))
    assert _evaluate_lhs("x", context) is None

    evaluated = _evaluate_expr("x + [1; 2]", context)
    assert evaluated.rows == (("(x_1) + (1)",), ("(x_2) + (2)",))
    assert _evaluate_expr(r"\deriv{2}{x}", context).rows == ((r"\ddot{x_1}",), (r"\ddot{x_2}",))
    with pytest.raises(UnsupportedSyntaxError, match="Unsupported empty matrix expression"):
        _evaluate_expr("   ", {})

    assert _has_matrix_intent("x", context) is True
    assert _has_matrix_intent("[1; 2]", context) is True
    assert _has_matrix_intent(r"\dot{x}", context) is True
    assert _has_matrix_intent("plain_scalar", context) is False


def test_derivative_matching_and_symbol_matching_helpers() -> None:
    context = {"x": MatrixValue((("x_1",), ("x_2",))), "xx": MatrixValue((("xx_1",),))}

    assert _expand_vector_derivative("\\dot{x}", context).rows == (("\\dot{x_1}",), ("\\dot{x_2}",))
    assert _expand_vector_derivative("\\deriv{3}{x}", context).rows == (("\\deriv{3}{x_1}",), ("\\deriv{3}{x_2}",))
    assert _expand_vector_derivative("\\dot{y}", context) is None
    assert _expand_vector_derivative("\\deriv{3}{y}", context) is None

    match = _match_vector_derivative("\\dot{x} + 1", 0, context)
    assert match is not None
    assert match[0] == len("\\dot{x}")
    general_match = _match_vector_derivative(r"\deriv{3}{x} + 1", 0, context)
    assert general_match is not None
    assert general_match[0] == len(r"\deriv{3}{x}")
    assert _match_vector_derivative("\\deriv{3}{y}", 0, context) is None

    symbol_match = _match_matrix_symbol("xx + x", 0, context)
    assert symbol_match is not None
    assert symbol_match[0] == 2

    assert _match_matrix_symbol("xyz", 0, {"x": MatrixValue((("x",),))}) is None
    assert _parse_plain_symbol("x_1") == "x_1"
    assert _parse_plain_symbol("x+y") is None


def test_parse_matrix_literal_covers_environments_transpose_and_validation_errors() -> None:
    env_matrix = _parse_matrix_literal("\\begin{bmatrix}1 & 2 \\\\ 3 & 4\\end{bmatrix}")
    assert env_matrix.rows == (("1", "2"), ("3", "4"))
    assert _parse_matrix_literal("\\begin{equation}x\\end{equation}") is None

    transposed = _parse_matrix_literal("[a, b]^T")
    assert transposed.rows == (("a",), ("b",))
    assert _parse_matrix_literal("[a, b]^{T}").rows == (("a",), ("b",))
    assert _parse_matrix_literal(r"[a, b]^{\top}").rows == (("a",), ("b",))
    assert _parse_matrix_literal(r"[a, b]^\top").rows == (("a",), ("b",))

    with pytest.raises(UnsupportedSyntaxError, match="Empty matrix/vector literal"):
        _parse_matrix_literal("[]")

    with pytest.raises(UnsupportedSyntaxError, match="Unterminated matrix environment"):
        _parse_matrix_literal("\\begin{bmatrix}1 & 2")

    with pytest.raises(UnsupportedSyntaxError, match="consistent widths"):
        _validate_matrix_rows((("1", "2"), ("3",)))

    with pytest.raises(UnsupportedSyntaxError, match="may not be empty"):
        _validate_matrix_rows((("1", ""),))

    with pytest.raises(UnsupportedSyntaxError, match="Empty matrix/vector literal"):
        _validate_matrix_rows(tuple())


def test_matrix_literal_consumers_cover_balancing_and_transpose_suffixes() -> None:
    assert _consume_matrix_environment("\\begin{bmatrix}1\\end{bmatrix}", 0) == len("\\begin{bmatrix}1\\end{bmatrix}")
    assert _consume_matrix_environment("\\begin{equation}x\\end{equation}", 0) is None
    with pytest.raises(UnsupportedSyntaxError, match="Unterminated matrix environment"):
        _consume_matrix_environment("\\begin{bmatrix}1", 0)

    assert _consume_balanced("[a[b]c]", 0, "[", "]") == len("[a[b]c]")
    assert _consume_balanced("[abc", 0, "[", "]") is None
    assert _consume_transpose_suffix("[a]^T", len("[a]")) == len("[a]^T")
    assert _consume_transpose_suffix("[a]", len("[a]")) == len("[a]")
    assert _matrix_literal_end("[a]^T + 1", 0) == len("[a]^T")
    assert _matrix_literal_end("\\begin{bmatrix}1\\end{bmatrix} + 1", 0) == len("\\begin{bmatrix}1\\end{bmatrix}")
    with pytest.raises(UnsupportedSyntaxError, match="Unterminated square-bracket"):
        _matrix_literal_end("[a", 0)


def test_additive_and_scalar_segment_helpers_cover_signs_and_boundaries() -> None:
    terms = _split_additive_terms("-a + b - [1; 2]")
    assert terms == [(-1, "a"), (1, "b"), (-1, "[1; 2]")]
    assert _split_additive_terms("a+-b") == [(1, "a"), (-1, "b")]
    assert _split_additive_terms("a+ +b") == [(1, "a"), (1, "b")]
    assert _split_additive_terms("{a+b}-c") == [(1, "{a+b}"), (-1, "c")]
    assert _split_additive_terms(r"\begin{bmatrix}1 & 2\end{bmatrix} - c") == [(1, r"\begin{bmatrix}1 & 2\end{bmatrix}"), (-1, "c")]
    assert _split_top_level(r"\begin{bmatrix}1 & 2\end{bmatrix},d", row_delimiter=",") == [
        r"\begin{bmatrix}1 & 2\end{bmatrix}",
        "d",
    ]
    assert _split_top_level("{a,b},[c,d],(e,f)", row_delimiter=",") == ["{a,b}", "[c,d]", "(e,f)"]

    context = {"A": MatrixValue((("a",),))}
    term = "2*(x+y)A"
    assert _consume_scalar_segment(term, 0, context) == len("2")
    assert _consume_scalar_segment("2[1;2]", 0, context) == len("2")
    assert _consume_scalar_segment(r"2\dot{x}", 0, {"x": MatrixValue((("x_1",),))}) == len("2")
    assert _consume_scalar_segment("2A", 0, context) == len("2")
    assert _consume_scalar_segment("f{a}A", 0, context) == len("f{a}")
    assert _consume_scalar_segment(r"2\begin{bmatrix}1\\2\end{bmatrix}", 0, context) == len("2")
    assert _consume_scalar_segment(r"(2\begin{bmatrix}1\\2\end{bmatrix})A", 0, context) == len(r"(2\begin{bmatrix}1\\2\end{bmatrix})")
    assert _consume_scalar_segment("f([1,2])A", 0, context) == len("f([1,2])")

    assert _parse_factors("A*[1;2]", {"A": MatrixValue((("a", "b"),))})[0].rows == (("a", "b"),)
    assert _parse_factors(r"  \dot{x}", {"x": MatrixValue((("x_1",),))})[0].rows == ((r"\dot{x_1}",),)
    with pytest.raises(UnsupportedSyntaxError, match="Unsupported matrix product term"):
        _evaluate_product_term("   ", {})


def test_parse_factors_rejects_empty_scalar_segments_when_consumer_makes_no_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("latex_frontend.matrix_expansion._consume_scalar_segment", lambda term, start, context: start)
    with pytest.raises(UnsupportedSyntaxError, match="Unable to parse matrix product term"):
        _parse_factors("?", {})


def test_matrix_arithmetic_helpers_cover_success_and_failure_paths() -> None:
    left = MatrixValue((("a", "b"),))
    right = MatrixValue((("c", "d"),))
    assert _add_matrices(left, right).rows == (("(a) + (c)", "(b) + (d)"),)
    with pytest.raises(UnsupportedSyntaxError, match="Cannot add matrices"):
        _add_matrices(left, MatrixValue((("x",), ("y",))))

    assert _scale_matrix("-1", MatrixValue((("x",),))).rows == (("-(x)",),)
    assert _multiply_values(MatrixValue((("2",),)), MatrixValue((("x", "y"),))).rows == (("(2)*(x)", "(2)*(y)"),)
    assert _multiply_values(
        MatrixValue((("a", "b"), ("c", "d"))),
        MatrixValue((("x",), ("y",))),
    ).rows == (("((a)*(x)) + ((b)*(y))",), ("((c)*(x)) + ((d)*(y))",))

    with pytest.raises(UnsupportedSyntaxError, match="Cannot multiply matrices"):
        _multiply_values(MatrixValue((("a", "b"),)), MatrixValue((("x", "y"),)))

    assert _sum_terms(["0", "x", "y"]) == "(x) + (y)"
    assert _combine_add("0", "x") == "x"
    assert _combine_add("x", "0") == "x"
    assert _combine_mul("1", "x") == "x"
    assert _combine_mul("x", "1") == "x"
    assert _combine_mul("-1", "x") == "-(x)"
    assert _combine_mul("x", "-1") == "-(x)"
    assert _combine_mul("0", "x") == "0"

    equations = _matrix_equations(MatrixValue((("x",), ("y",))), MatrixValue((("1",), ("2",))))
    assert equations == ["x = 1", "y = 2"]
