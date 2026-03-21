from __future__ import annotations

from ir.graph_lowering import lower_semi_explicit_dae_graph
from latex_frontend.translator import translate_latex
from states.extract_states import analyze_state_extraction


def test_lower_semi_explicit_dae_graph_emits_algebraic_chains() -> None:
    analysis = analyze_state_extraction(
        translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
        mode="strict",
    )

    graph = lower_semi_explicit_dae_graph(analysis.dae_system, name="nonlinear_dae")

    assert graph["kind"] == "semi_explicit_dae_graph"
    assert graph["algebraic_chains"][0]["variable"] == "z"
    assert "x" in graph["outputs"]
    assert "z" in graph["outputs"]
