from __future__ import annotations

import pytest

from latex_frontend.symbols import DeterministicCompileError, derivative_symbol_name
from pipeline import input_frontends as frontend_module


def test_normalize_problem_rejects_invalid_payload_shapes() -> None:
    with pytest.raises(DeterministicCompileError, match="mapping payload"):
        frontend_module.normalize_problem(["not", "a", "mapping"])  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="non-empty source_type"):
        frontend_module.normalize_problem({})

    with pytest.raises(DeterministicCompileError, match="Unsupported source_type"):
        frontend_module.normalize_problem({"source_type": "unknown"})


def test_symbolic_diff_rewrite_validates_time_consistency() -> None:
    with pytest.raises(DeterministicCompileError, match="but payload declares"):
        frontend_module._rewrite_symbolic_diff_equations(
            ["diff(x,tau) == -x"],
            "t",
            source_type="matlab_symbolic",
        )

    with pytest.raises(DeterministicCompileError, match="multiple time variables"):
        frontend_module._rewrite_symbolic_diff_equations(
            ["diff(x,t) == -x", "diff(y,tau) == y"],
            None,
            source_type="matlab_symbolic",
        )


def test_component_expression_ode_function_validation_errors() -> None:
    with pytest.raises(DeterministicCompileError, match="requires explicit states"):
        frontend_module._normalize_component_expression_ode_function(
            {"expressions": ["-x"]},
            states=(),
            inputs=(),
            parameters=(),
            time_variable="t",
        )

    with pytest.raises(DeterministicCompileError, match="one RHS expression per declared state"):
        frontend_module._normalize_component_expression_ode_function(
            {"expressions": ["-x"]},
            states=("x", "y"),
            inputs=(),
            parameters=(),
            time_variable="t",
        )

    with pytest.raises(DeterministicCompileError, match="outputs must match the RHS expression count"):
        frontend_module._normalize_component_expression_ode_function(
            {"expressions": ["-x"], "outputs": ["xdot", "ydot"]},
            states=("x",),
            inputs=(),
            parameters=(),
            time_variable="t",
        )

    with pytest.raises(DeterministicCompileError, match="does not match the derivative"):
        frontend_module._normalize_component_expression_ode_function(
            {"expressions": ["-x"], "outputs": ["ydot"]},
            states=("x",),
            inputs=(),
            parameters=(),
            time_variable="t",
        )


def test_vector_rhs_ode_function_validation_errors() -> None:
    with pytest.raises(DeterministicCompileError, match="requires explicit state_names"):
        frontend_module._normalize_vector_rhs_ode_function(
            {"rhs": ["-x(1)"]},
            states=(),
            inputs=(),
            parameters=(),
            time_variable="t",
        )

    with pytest.raises(DeterministicCompileError, match="one RHS entry per declared state"):
        frontend_module._normalize_vector_rhs_ode_function(
            {"rhs": ["-x(1)"], "state_vector_name": "x"},
            states=("x_1", "x_2"),
            inputs=(),
            parameters=(),
            time_variable="t",
        )

    with pytest.raises(DeterministicCompileError, match="out of range"):
        frontend_module._normalize_vector_rhs_ode_function(
            {"rhs": ["-x(2)"], "state_vector_name": "x"},
            states=("x_1",),
            inputs=(),
            parameters=(),
            time_variable="t",
        )


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("", "empty equation"),
        ("x == y == z", "exactly one equality operator"),
        ("x = y = z", "exactly one equality operator"),
        ("x + y", "missing '=' or '=='"),
        ("= y", "non-empty lhs and rhs"),
        ("x =", "non-empty lhs and rhs"),
    ],
)
def test_split_equation_rejects_invalid_forms(text: str, pattern: str) -> None:
    with pytest.raises(DeterministicCompileError, match=pattern):
        frontend_module._split_equation(text, source_type="matlab_equation_text")


def test_load_derivative_map_validates_alias_targets() -> None:
    with pytest.raises(DeterministicCompileError, match="must be a mapping"):
        frontend_module._load_derivative_map(["xdot"], states=("x",), time_variable="t")  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="Invalid derivative_map alias"):
        frontend_module._load_derivative_map({1: "x"}, states=("x",), time_variable="t")  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="must be a state name or mapping"):
        frontend_module._load_derivative_map({"xdot": 1}, states=("x",), time_variable="t")  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="missing a valid base state"):
        frontend_module._load_derivative_map({"xdot": {"base": "", "order": 1}}, states=("x",), time_variable="t")

    with pytest.raises(DeterministicCompileError, match="targets undeclared state"):
        frontend_module._load_derivative_map({"xdot": "y"}, states=("x",), time_variable="t")

    normalized = frontend_module._load_derivative_map(
        {"xddot": {"base": "x", "order": 2}},
        states=("x",),
        time_variable="t",
    )
    assert normalized == {"xddot": ("x", 2)}


def test_identifier_alias_rewrite_and_output_matching_helpers() -> None:
    alias_map = frontend_module._build_derivative_alias_map(states=("x",), time_variable="t")
    alias_map_with_second_order = frontend_module._build_derivative_alias_map(
        states=("x",),
        time_variable="t",
        derivative_map={"xddot": ("x", 2)},
    )
    rewritten = frontend_module._replace_identifier_aliases(
        "xdot + dxdt",
        alias_map,
        source_type="matlab_equation_text",
        time_variable="t",
    )
    assert rewritten == f"{derivative_symbol_name('x', 1)} + {derivative_symbol_name('x', 1)}"
    assert alias_map_with_second_order["xddot"] == derivative_symbol_name("x", 2)
    assert frontend_module._output_matches_state("dxdt", "x", "t") is True
    assert frontend_module._output_matches_state("ydot", "x", "t") is False

    with pytest.raises(DeterministicCompileError, match="state derivative or an ordinary variable"):
        frontend_module._replace_identifier_aliases(
            "xdot + x",
            {},
            source_type="matlab_equation_text",
            time_variable="t",
        )


def test_text_document_and_equation_list_helpers_validate_shapes() -> None:
    assert frontend_module._extract_text_document({"text": [" xdot = z ", "", "0 = z"]}, field="text") == "xdot = z\n0 = z"
    assert frontend_module._coerce_equation_list({"equations": "x = 1\n\n y = 2"}, "equations") == ["x = 1", "y = 2"]
    assert frontend_module._coerce_equation_list({"text": ["x = 1"]}, "equations") == ["x = 1"]

    with pytest.raises(DeterministicCompileError, match="entry at index 0 must be a string"):
        frontend_module._extract_text_document({"text": [1]}, field="text")

    with pytest.raises(DeterministicCompileError, match="at least one non-empty equation string"):
        frontend_module._extract_text_document({"text": ["   "]}, field="text")

    with pytest.raises(DeterministicCompileError, match="must be a string or list of equation strings"):
        frontend_module._coerce_equation_list({"equations": 3}, "equations")  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="at least one non-empty equation string"):
        frontend_module._coerce_equation_list({"equations": ["   "]}, "equations")


def test_optional_helper_validators_reject_invalid_types() -> None:
    with pytest.raises(DeterministicCompileError, match="must be a list of symbol names"):
        frontend_module._optional_name_list({"states": "x"}, "states")

    with pytest.raises(DeterministicCompileError, match="must be a non-empty string"):
        frontend_module._optional_name_list({"states": ["", "x"]}, "states")

    with pytest.raises(DeterministicCompileError, match="must be a mapping"):
        frontend_module._optional_mapping({"assumptions": []}, "assumptions")  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="must be a non-empty string"):
        frontend_module._optional_string({"time_variable": "   "}, "time_variable")

    with pytest.raises(DeterministicCompileError, match="path is required"):
        frontend_module._require_string({}, "path")

    with pytest.raises(DeterministicCompileError, match="must be a list of strings"):
        frontend_module._require_string_list({"rhs": "x"}, "rhs")

    with pytest.raises(DeterministicCompileError, match="must be a non-empty string"):
        frontend_module._require_string_list({"rhs": ["   "]}, "rhs")


def test_parse_math_expression_raises_precise_error_for_invalid_expression() -> None:
    with pytest.raises(DeterministicCompileError, match="could not parse expression"):
        frontend_module._parse_math_expression(
            "sin(",
            source_type="matlab_equation_text",
            alias_map={},
            time_variable="t",
        )
