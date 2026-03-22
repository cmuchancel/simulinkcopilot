from __future__ import annotations

import pytest

from latex_frontend.symbols import DeterministicCompileError
from pipeline.input_frontends import (
    _coerce_equation_list,
    _extract_text_document,
    _load_derivative_map,
    _optional_mapping,
    _optional_name_list,
    _replace_vector_references,
    _require_string_list,
    normalize_from_latex_text,
    normalize_problem,
)


def test_normalize_problem_accepts_normalized_problem_instances() -> None:
    problem = normalize_from_latex_text(r"\dot{x}=-x", assumptions={"domain": "real"})
    assert normalize_problem(problem) is problem
    assert problem.assumptions == {"domain": "real"}


def test_matlab_ode_function_rejects_missing_and_unsupported_representations() -> None:
    with pytest.raises(DeterministicCompileError, match="structured exported specification"):
        normalize_problem({"source_type": "matlab_ode_function", "function_spec": None})

    with pytest.raises(DeterministicCompileError, match="must declare a representation"):
        normalize_problem({"source_type": "matlab_ode_function", "function_spec": {}})

    with pytest.raises(DeterministicCompileError, match="Supported representations"):
        normalize_problem(
            {
                "source_type": "matlab_ode_function",
                "function_spec": {"representation": "mystery"},
                "state_names": ["x"],
            }
        )


def test_matlab_ode_function_component_expressions_and_parameter_vectors_normalize() -> None:
    component_problem = normalize_problem(
        {
            "source_type": "matlab_ode_function",
            "function_spec": {
                "representation": "component_expressions",
                "outputs": ["xdot", "ydot"],
                "expressions": ["-x + u", "x - y"],
            },
            "states": ["x", "y"],
            "inputs": ["u"],
        }
    )
    assert tuple(component_problem.states) == ("x", "y")

    vector_problem = normalize_problem(
        {
            "source_type": "matlab_ode_function",
            "function_spec": {
                "representation": "vector_rhs",
                "state_vector_name": "x",
                "input_vector_name": "u",
                "parameter_vector_name": "p",
                "rhs": ["-p(1)*x(1) + u(1)"],
            },
            "state_names": ["x_1"],
            "input_names": ["u_1"],
            "parameter_names": ["a"],
        }
    )
    assert vector_problem.parameters == ("a",)


def test_load_derivative_map_and_vector_reference_helpers_cover_validation_paths() -> None:
    assert _load_derivative_map({"xd": {"base": "x", "order": 2}}, states=("x",), time_variable="t") == {"xd": ("x", 2)}

    with pytest.raises(DeterministicCompileError, match="mapping of alias"):
        _load_derivative_map([], states=(), time_variable=None)
    with pytest.raises(DeterministicCompileError, match="Invalid derivative_map alias"):
        _load_derivative_map({1: "x"}, states=("x",), time_variable=None)
    with pytest.raises(DeterministicCompileError, match="undeclared state"):
        _load_derivative_map({"xd": "y"}, states=("x",), time_variable=None)

    assert _replace_vector_references("u(1) + 1", "u", (), source_type="matlab_ode_function") == "u(1) + 1"


def test_text_and_list_coercion_helpers_reject_invalid_payload_shapes() -> None:
    assert _coerce_equation_list({"equations": "x=1\n\n y=2"}, "equations") == ["x=1", "y=2"]
    assert _extract_text_document({"text": ["x=1", " ", "y=2"]}, field="text") == "x=1\ny=2"
    assert _optional_name_list({"states": None}, "states") == ()

    with pytest.raises(DeterministicCompileError, match="text must be a string or list"):
        _extract_text_document({"text": 3}, field="text")
    with pytest.raises(DeterministicCompileError, match="entry at index 0 must be a string"):
        _coerce_equation_list({"equations": [1]}, "equations")
    with pytest.raises(DeterministicCompileError, match="assumptions must be a mapping"):
        _optional_mapping({"assumptions": []}, "assumptions")
    with pytest.raises(DeterministicCompileError, match="must contain at least one string"):
        _require_string_list({"equations": []}, "equations")
