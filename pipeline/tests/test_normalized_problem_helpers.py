from __future__ import annotations

import pytest

from ir.expression_nodes import DerivativeNode, EquationNode, NumberNode, SymbolNode
from latex_frontend.symbols import DeterministicCompileError
from pipeline import normalized_problem as normalized_module


def _simple_problem(**overrides):
    payload = dict(
        source_type="latex",
        equations=[EquationNode(lhs=DerivativeNode(base="x", order=1), rhs=SymbolNode("u"))],
        states=["x"],
        algebraics=(),
        inputs=["u"],
        parameters=(),
        time_variable="t",
        source_metadata={"name": "demo"},
    )
    payload.update(overrides)
    return normalized_module.build_normalized_problem(**payload)


def test_normalize_equation_orientation_and_canonical_equation_cover_rhs_derivative_and_zero() -> None:
    rhs_derivative = EquationNode(lhs=SymbolNode("rhs"), rhs=DerivativeNode(base="x", order=1))
    normalized = normalized_module.normalize_equation_orientation(rhs_derivative)
    assert normalized.lhs == DerivativeNode(base="x", order=1)
    assert normalized.rhs == SymbolNode("rhs")

    zero_rhs = EquationNode(lhs=SymbolNode("y"), rhs=NumberNode(0))
    canonical = normalized_module.CanonicalEquation.from_equation_node(zero_rhs, original_text="y = 0", source_index=2)
    assert canonical.lhs_kind == "algebraic_zero"
    assert canonical.lhs_symbol is None
    assert canonical.to_dict()["source_index"] == 2


def test_normalized_problem_source_name_label_and_dict_round_trip() -> None:
    problem = _simple_problem(source_metadata={"display_path": "/tmp/example.tex", "path": "/tmp/ignored.tex"})

    assert problem.source_name() == "example"
    assert problem.source_label() == "/tmp/example.tex"
    payload = problem.to_dict()
    assert payload["source_type"] == "latex"
    assert payload["states"] == ["x"]
    assert payload["inputs"] == ["u"]


def test_build_normalized_problem_validates_supported_source_duplicates_and_text_count() -> None:
    with pytest.raises(DeterministicCompileError, match="Unsupported source_type"):
        normalized_module.build_normalized_problem(
            source_type="bad",
            equations=[EquationNode(lhs=SymbolNode("x"), rhs=NumberNode(1))],
        )

    with pytest.raises(DeterministicCompileError, match="symbol roles must be disjoint"):
        normalized_module.build_normalized_problem(
            source_type="latex",
            equations=[EquationNode(lhs=SymbolNode("x"), rhs=NumberNode(1))],
            states=["x"],
            inputs=["x"],
        )

    with pytest.raises(DeterministicCompileError, match="cannot also be declared"):
        normalized_module.build_normalized_problem(
            source_type="latex",
            equations=[EquationNode(lhs=SymbolNode("x"), rhs=NumberNode(1))],
            time_variable="t",
            parameters=["t"],
        )

    with pytest.raises(DeterministicCompileError, match="original_texts must match"):
        normalized_module.build_normalized_problem(
            source_type="latex",
            equations=[EquationNode(lhs=SymbolNode("x"), rhs=NumberNode(1))],
            original_texts=["x = 1", "y = 2"],
        )


def test_merge_symbol_config_merges_declared_roles_and_rejects_conflicts() -> None:
    problem = _simple_problem()
    merged = normalized_module.merge_symbol_config(problem, {"k": "parameter"})
    assert merged == {"k": "parameter", "u": "input", "t": "independent_variable"}

    with pytest.raises(DeterministicCompileError, match="must map to a role string or mapping"):
        normalized_module.merge_symbol_config(problem, {"u": 3})  # type: ignore[arg-type]

    with pytest.raises(DeterministicCompileError, match="declares symbol 'u' as 'input'"):
        normalized_module.merge_symbol_config(problem, {"u": "parameter"})


@pytest.mark.parametrize(
    ("problem_override", "kwargs", "pattern"),
    [
        (
            {
                "equations": [EquationNode(lhs=DerivativeNode(base="x", order=2), rhs=NumberNode(0))],
                "states": ["y"],
            },
            {
                "states": ("x",),
                "algebraics": (),
                "inputs": (),
                "parameters": (),
                "independent_variable": None,
            },
            "higher-order bases",
        ),
        (
            {"algebraics": ("z",)},
            {
                "states": ("x",),
                "algebraics": (),
                "inputs": ("u",),
                "parameters": (),
                "independent_variable": "t",
            },
            "declared algebraics do not match",
        ),
        (
            {},
            {
                "states": ("x",),
                "algebraics": (),
                "inputs": (),
                "parameters": (),
                "independent_variable": "t",
            },
            "declared inputs do not match",
        ),
        (
            {"parameters": ("k",)},
            {
                "states": ("x",),
                "algebraics": (),
                "inputs": ("u",),
                "parameters": (),
                "independent_variable": "t",
            },
            "declared parameters do not match",
        ),
        (
            {},
            {
                "states": ("x",),
                "algebraics": (),
                "inputs": ("u",),
                "parameters": (),
                "independent_variable": "tau",
            },
            "declared time variable does not match",
        ),
    ],
)
def test_validate_problem_against_extraction_rejects_mismatches(problem_override, kwargs, pattern: str) -> None:
    problem = _simple_problem(**problem_override)
    with pytest.raises(DeterministicCompileError, match=pattern):
        normalized_module.validate_problem_against_extraction(problem, **kwargs)
