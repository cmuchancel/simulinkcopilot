from __future__ import annotations

import json
from pathlib import Path

import pytest
import sympy

from ir.expression_nodes import EquationNode, NumberNode, SymbolNode
from latex_frontend.symbols import DeterministicCompileError
from states import classify_symbols as classify_module


def test_symbol_metadata_to_dict_and_load_config_validation_paths(tmp_path: Path) -> None:
    metadata = classify_module.SymbolMetadata(name="u", role="input", source="configured")
    assert metadata.to_dict() == {"name": "u", "role": "input", "source": "configured"}

    config_path = tmp_path / "symbols.json"
    config_path.write_text(json.dumps({"symbols": {"u": {"role": "input"}}}), encoding="utf-8")
    loaded = classify_module.load_symbol_config(config_path)
    assert loaded["u"].role == "input"

    with pytest.raises(DeterministicCompileError, match="Invalid configured symbol name"):
        classify_module.load_symbol_config({None: "input"})  # type: ignore[arg-type]
    with pytest.raises(DeterministicCompileError, match="must map to a role string"):
        classify_module.load_symbol_config({"u": 3})  # type: ignore[arg-type]
    with pytest.raises(DeterministicCompileError, match="unsupported role"):
        classify_module.load_symbol_config({"u": "state_candidate"})


def test_classify_symbol_validation_and_seed_metadata_conflict_paths() -> None:
    with pytest.raises(DeterministicCompileError, match="Unsupported symbol-classification mode"):
        classify_module._validate_classification_request("bad", {})
    with pytest.raises(DeterministicCompileError, match="cannot use a symbol configuration"):
        classify_module._validate_classification_request(
            "strict",
            {"u": classify_module.SymbolMetadata(name="u", role="input", source="configured")},
        )
    with pytest.raises(DeterministicCompileError, match="Exactly one independent variable"):
        classify_module._validate_classification_request(
            "configured",
            {
                "t": classify_module.SymbolMetadata(name="t", role="independent_variable", source="configured"),
                "tau": classify_module.SymbolMetadata(name="tau", role="independent_variable", source="configured"),
            },
        )
    with pytest.raises(DeterministicCompileError, match="conflicts with inferred state-candidate role"):
        classify_module._seed_metadata(
            {"x": 1},
            (),
            {"x": classify_module.SymbolMetadata(name="x", role="input", source="configured")},
        )
    seeded = classify_module._seed_metadata(
        {},
        (),
        {"t": classify_module.SymbolMetadata(name="t", role="independent_variable", source="configured")},
    )
    assert seeded["t"].role == "independent_variable"


def test_classify_symbol_helper_functions_cover_external_scan_and_finalize_paths() -> None:
    derivative_orders = {"x": 2}
    state_like = classify_module._build_state_like_symbols(derivative_orders, ("x_dot",))
    assert {symbol.name for symbol in state_like} >= {"x", "x_dot", "D1_x", "D2_x"}

    explicit_rhs = [sympy.Symbol("x") + sympy.Symbol("u"), sympy.Symbol("k") * sympy.Symbol("u")]
    metadata = {"x": classify_module.SymbolMetadata(name="x", role="state_candidate", source="inferred")}
    external = classify_module._collect_external_symbols(
        explicit_rhs,
        state_like_symbols={sympy.Symbol("x")},
        metadata=metadata,
        reserved_symbols={"t"},
    )
    assert {symbol.name for symbol in external} == {"k", "u"}

    parameter_names: set[str] = set()
    pure_terms = classify_module._scan_pure_terms(
        explicit_rhs,
        external_symbols=external,
        state_like_symbols={sympy.Symbol("x")},
        parameter_names=parameter_names,
    )
    assert parameter_names == set()
    assert len(pure_terms) == 2

    finalized = classify_module._finalize_metadata(
        metadata=dict(metadata),
        external_symbols=external | {sympy.Symbol("x")},
        configured={"u": classify_module.SymbolMetadata(name="u", role="input", source="configured")},
        parameter_names={"k"},
        input_names={"u"},
    )
    assert finalized["x"].role == "state_candidate"
    assert finalized["u"].role == "input"
    assert finalized["k"].role == "parameter"

    unresolved = classify_module._finalize_metadata(
        metadata={},
        external_symbols={sympy.Symbol("m")},
        configured={},
        parameter_names=set(),
        input_names=set(),
    )
    assert unresolved["m"].role == "unknown_unresolved"


def test_classify_symbol_role_inference_and_ambiguity_paths() -> None:
    pure_terms = [sympy.Symbol("a") * sympy.Symbol("u"), sympy.Symbol("b") ** 2]
    external_symbols = {sympy.Symbol("a"), sympy.Symbol("u"), sympy.Symbol("b")}
    parameter_names: set[str] = set()
    input_names: set[str] = set()

    classify_module._infer_pure_term_roles(
        pure_terms,
        external_symbols,
        metadata={"a": classify_module.SymbolMetadata(name="a", role="known_constant", source="configured")},
        parameter_names=parameter_names,
        input_names=input_names,
        mode="strict",
    )
    assert input_names == {"u"}
    assert parameter_names == {"a"}

    ambiguous = classify_module._ambiguous_pure_terms(
        [sympy.Symbol("p") * sympy.Symbol("q")],
        {sympy.Symbol("p"), sympy.Symbol("q")},
        metadata={},
        parameter_names=set(),
        input_names=set(),
    )
    assert ambiguous == ["p*q -> p, q"]


def test_classify_symbols_reports_ambiguous_external_symbols() -> None:
    equations = [EquationNode(lhs=NumberNode(0), rhs=SymbolNode("m"))]
    with pytest.raises(DeterministicCompileError, match="Ambiguous external-symbol classification"):
        classify_module.classify_symbols(
            equations,
            derivative_orders={},
            state_names=(),
            mode="configured",
            symbol_config={},
        )


def test_classify_symbols_reports_unresolved_finalize_output(monkeypatch: pytest.MonkeyPatch) -> None:
    equations = [EquationNode(lhs=NumberNode(0), rhs=NumberNode(1))]

    monkeypatch.setattr(classify_module, "_ambiguous_pure_terms", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        classify_module,
        "_finalize_metadata",
        lambda **kwargs: {
            "m": classify_module.SymbolMetadata(
                name="m",
                role="unknown_unresolved",
                source="inferred",
            )
        },
    )

    with pytest.raises(DeterministicCompileError, match="Unable to deterministically classify external symbols: m"):
        classify_module.classify_symbols(
            equations,
            derivative_orders={},
            state_names=(),
            mode="configured",
            symbol_config={},
        )
