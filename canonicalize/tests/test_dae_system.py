from __future__ import annotations

from latex_frontend.translator import translate_latex
from states.extract_states import analyze_state_extraction


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
