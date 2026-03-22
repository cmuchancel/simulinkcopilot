from __future__ import annotations

from canonicalize import dae_system as dae_system_module
from canonicalize.dae_reduction import DaeReductionResult
from ir.expression_nodes import AddNode, DerivativeNode, EquationNode, NumberNode, SymbolNode
from latex_frontend.translator import translate_latex
from states.extract_states import analyze_state_extraction
from states.rules import ExtractionResult


def test_explicit_ode_classifies_as_explicit_ode() -> None:
    analysis = analyze_state_extraction(
        translate_latex(r"\dot{x}=-ax+bu"),
        mode="configured",
        symbol_config={"b": "parameter", "u": "input"},
    )

    assert analysis.dae_system.classification.kind == "explicit_ode"
    assert analysis.dae_system.classification.supported is True


def test_reducible_semi_explicit_dae_classifies_as_reducible() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", "z-x=0"])),
        mode="strict",
    )

    assert analysis.dae_system.classification.kind == "reducible_semi_explicit_dae"
    assert analysis.dae_system.reduced_to_explicit is True


def test_nonlinear_preserved_dae_classifies_as_supported_preserved_dae() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    assert analysis.dae_system.classification.kind == "nonlinear_preserved_semi_explicit_dae"
    assert analysis.dae_system.classification.supported is True
    assert analysis.dae_system.preserved_form is not None


def test_high_order_preserved_dae_classifies_as_unsupported() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\ddot{x}+y=0", r"y+\sin(y)-x=0"])),
        mode="strict",
    )

    assert analysis.dae_system.classification.kind == "unsupported_dae"
    assert analysis.dae_system.classification.supported is False


def test_preserved_form_and_finalize_support_cover_helper_paths() -> None:
    extraction = ExtractionResult(
        states=("x",),
        inputs=("u",),
        parameters=("k",),
        independent_variable=None,
        derivative_orders={"x": 1},
        symbol_metadata={},
    )
    dynamic = EquationNode(lhs=DerivativeNode(base="x", order=1), rhs=SymbolNode("z"))
    constraint = EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z"))
    reduction = DaeReductionResult(
        equations=[dynamic, constraint],
        dynamic_equations=[dynamic],
        reduced_dynamic_equations=[dynamic],
        algebraic_constraints=[constraint],
        resolved_helper_definitions={},
        solved_algebraic_variables={},
        residual_constraints=[constraint],
        algebraic_variables=("z",),
    )

    dae_system = dae_system_module.build_semi_explicit_dae_system(extraction, reduction)

    assert dae_system.to_dict()["preserved_form"]["algebraic_constraint_map"]["z"] == "0 = z"
    finalized = dae_system_module.finalize_dae_support(dae_system, descriptor_system={"form": "linear_descriptor"})
    assert finalized.classification.kind == "linear_descriptor_dae"
    assert finalized.classification.python_validation_supported is True

    unsupported = dae_system_module.finalize_dae_support(
        dae_system_module.replace(
            dae_system,
            classification=dae_system_module.DaeSupportClassification(
                kind="unsupported_dae",
                route="unsupported",
                supported=False,
                python_validation_supported=False,
                simulink_lowering_supported=False,
                diagnostic="nope",
            ),
        ),
        descriptor_system={"form": "linear_descriptor"},
    )
    assert unsupported.classification.kind == "unsupported_dae"


def test_build_preserved_form_rejects_non_explicit_differential_rows_and_ambiguous_constraints() -> None:
    extraction = ExtractionResult(
        states=("x",),
        inputs=(),
        parameters=(),
        independent_variable="t",
        derivative_orders={"x": 1},
        symbol_metadata={},
    )
    bad_dynamic = EquationNode(
        lhs=NumberNode(0),
        rhs=NumberNode(0),
    )
    reduction = DaeReductionResult(
        equations=[],
        dynamic_equations=[bad_dynamic],
        reduced_dynamic_equations=[bad_dynamic],
        algebraic_constraints=[EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z"))],
        resolved_helper_definitions={},
        solved_algebraic_variables={},
        residual_constraints=[EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z"))],
        algebraic_variables=("z",),
    )
    preserved, diagnostic = dae_system_module._build_preserved_form(extraction, reduction)
    assert preserved is None
    assert "Differential equations are not explicit" in diagnostic

    ambiguous_reduction = DaeReductionResult(
        equations=[],
        dynamic_equations=[EquationNode(lhs=DerivativeNode(base="x", order=1), rhs=SymbolNode("z"))],
        reduced_dynamic_equations=[EquationNode(lhs=DerivativeNode(base="x", order=1), rhs=SymbolNode("z"))],
        algebraic_constraints=[
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z")),
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z")),
        ],
        resolved_helper_definitions={},
        solved_algebraic_variables={},
        residual_constraints=[
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z")),
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z")),
        ],
        algebraic_variables=("z",),
    )
    preserved, diagnostic = dae_system_module._build_preserved_form(extraction, ambiguous_reduction)
    assert preserved is None
    assert "structurally singular" in diagnostic


def test_assign_algebraic_constraints_handles_empty_and_unmatched_cases() -> None:
    assert dae_system_module._assign_algebraic_constraints((), ()) == {}

    unmatched = dae_system_module._assign_algebraic_constraints(
        ("z",),
        (EquationNode(lhs=NumberNode(0), rhs=NumberNode(1)),),
    )
    assert unmatched is None

    contended = dae_system_module._assign_algebraic_constraints(
        ("z1", "z2"),
        (
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z1")),
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z1")),
        ),
    )
    assert contended is None


def test_build_preserved_form_rejects_missing_differential_state_and_assignment_helpers_cover_recursion() -> None:
    extraction = ExtractionResult(
        states=("x", "y"),
        inputs=(),
        parameters=(),
        independent_variable=None,
        derivative_orders={"x": 1, "y": 1},
        symbol_metadata={},
    )
    reduction = DaeReductionResult(
        equations=[],
        dynamic_equations=[EquationNode(lhs=DerivativeNode(base="x", order=1), rhs=NumberNode(0))],
        reduced_dynamic_equations=[EquationNode(lhs=DerivativeNode(base="x", order=1), rhs=NumberNode(0))],
        algebraic_constraints=[
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z1")),
            EquationNode(lhs=NumberNode(0), rhs=AddNode(args=(SymbolNode("z1"), SymbolNode("z2")))),
        ],
        resolved_helper_definitions={},
        solved_algebraic_variables={},
        residual_constraints=[
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z1")),
            EquationNode(lhs=NumberNode(0), rhs=AddNode(args=(SymbolNode("z1"), SymbolNode("z2")))),
        ],
        algebraic_variables=("z1", "z2"),
    )

    preserved, diagnostic = dae_system_module._build_preserved_form(extraction, reduction)
    assert preserved is None
    assert "do not isolate exactly one derivative" in diagnostic

    constraint_map = dae_system_module._assign_algebraic_constraints(
        ("z1", "z2"),
        (
            EquationNode(lhs=NumberNode(0), rhs=AddNode(args=(SymbolNode("z1"), SymbolNode("z2")))),
            EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z1")),
        ),
    )
    assert constraint_map == {
        "z1": EquationNode(lhs=NumberNode(0), rhs=SymbolNode("z1")),
        "z2": EquationNode(lhs=NumberNode(0), rhs=AddNode(args=(SymbolNode("z1"), SymbolNode("z2")))),
    }
