"""Deterministic symbol metadata and classification helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import sympy

from ir.equation_dict import expression_to_sympy
from ir.expression_nodes import EquationNode
from latex_frontend.symbols import DeterministicCompileError, derivative_symbol_name


VALID_SYMBOL_ROLES = {
    "state_candidate",
    "derivative_derived_state",
    "input",
    "parameter",
    "independent_variable",
    "known_constant",
    "unknown_unresolved",
}

CONFIGURABLE_ROLES = {"input", "parameter", "independent_variable", "known_constant"}


@dataclass(frozen=True)
class SymbolMetadata:
    """Deterministic metadata assigned to a symbol."""

    name: str
    role: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "role": self.role, "source": self.source}


def load_symbol_config(symbol_config: str | Path | Mapping[str, object] | None) -> dict[str, SymbolMetadata]:
    """Load optional user-provided symbol metadata."""
    if symbol_config is None:
        return {}

    if isinstance(symbol_config, (str, Path)):
        payload = json.loads(Path(symbol_config).read_text(encoding="utf-8"))
    else:
        payload = dict(symbol_config)

    if isinstance(payload, Mapping) and "symbols" in payload and isinstance(payload["symbols"], Mapping):
        payload = dict(payload["symbols"])

    metadata: dict[str, SymbolMetadata] = {}
    for name, raw_entry in payload.items():
        if not isinstance(name, str) or not name.strip():
            raise DeterministicCompileError(f"Invalid configured symbol name: {name!r}")
        if isinstance(raw_entry, str):
            role = raw_entry
        elif isinstance(raw_entry, Mapping):
            role = raw_entry.get("role")
        else:
            raise DeterministicCompileError(
                f"Configured symbol {name!r} must map to a role string or a mapping with a 'role' field."
            )

        if role not in CONFIGURABLE_ROLES:
            raise DeterministicCompileError(
                f"Configured symbol {name!r} has unsupported role {role!r}. "
                f"Expected one of {sorted(CONFIGURABLE_ROLES)}."
            )
        metadata[name] = SymbolMetadata(name=name, role=role, source="configured")
    return metadata


def _symbol_names(symbols: set[sympy.Symbol]) -> set[str]:
    return {symbol.name for symbol in symbols}


def _as_additive_terms(expr: sympy.Expr) -> tuple[sympy.Expr, ...]:
    expanded = sympy.expand(expr)
    return tuple(sympy.Add.make_args(expanded))


def _configured_independent_variable_names(configured: Mapping[str, SymbolMetadata]) -> list[str]:
    return [
        entry.name
        for entry in configured.values()
        if entry.role == "independent_variable"
    ]


def _validate_classification_request(mode: str, configured: Mapping[str, SymbolMetadata]) -> None:
    if mode not in {"strict", "configured"}:
        raise DeterministicCompileError(f"Unsupported symbol-classification mode {mode!r}.")
    if mode == "strict" and configured:
        raise DeterministicCompileError("Strict symbol classification cannot use a symbol configuration.")

    configured_independent_variables = _configured_independent_variable_names(configured)
    if len(configured_independent_variables) > 1:
        raise DeterministicCompileError("Exactly one independent variable may be declared.")


def _seed_metadata(
    derivative_orders: dict[str, int],
    state_names: tuple[str, ...],
    configured: Mapping[str, SymbolMetadata],
) -> dict[str, SymbolMetadata]:
    metadata: dict[str, SymbolMetadata] = {}
    for base in sorted(derivative_orders):
        if base in configured and configured[base].role != "state_candidate":
            raise DeterministicCompileError(
                f"Configured symbol {base!r} conflicts with inferred state-candidate role."
            )
        metadata[base] = SymbolMetadata(name=base, role="state_candidate", source="inferred")

    for independent_name in _configured_independent_variable_names(configured):
        metadata[independent_name] = configured[independent_name]

    for name in sorted(state_names):
        if name in metadata:
            continue
        metadata[name] = SymbolMetadata(name=name, role="derivative_derived_state", source="inferred")
    return metadata


def _build_state_like_symbols(
    derivative_orders: Mapping[str, int],
    state_names: tuple[str, ...],
) -> set[sympy.Symbol]:
    state_like_symbols = {sympy.Symbol(name) for name in derivative_orders}
    state_like_symbols.update(sympy.Symbol(name) for name in state_names)
    state_like_symbols.update(
        sympy.Symbol(derivative_symbol_name(base, order))
        for base, max_order in derivative_orders.items()
        for order in range(1, max_order + 1)
    )
    return state_like_symbols


def _collect_external_symbols(
    explicit_rhs: list[sympy.Expr],
    state_like_symbols: set[sympy.Symbol],
    metadata: Mapping[str, SymbolMetadata],
    reserved_symbols: set[str],
) -> set[sympy.Symbol]:
    free_symbols = set().union(*(expr.free_symbols for expr in explicit_rhs)) if explicit_rhs else set()
    return {
        symbol
        for symbol in free_symbols
        if symbol not in state_like_symbols and symbol.name not in metadata and symbol.name not in reserved_symbols
    }


def _scan_pure_terms(
    explicit_rhs: list[sympy.Expr],
    external_symbols: set[sympy.Symbol],
    state_like_symbols: set[sympy.Symbol],
    parameter_names: set[str],
) -> list[sympy.Expr]:
    external_symbol_names = _symbol_names(external_symbols)
    pure_terms: list[sympy.Expr] = []
    for expr in explicit_rhs:
        for term in _as_additive_terms(expr):
            term_symbols = term.free_symbols
            external_names = sorted(
                symbol.name
                for symbol in term_symbols
                if symbol in external_symbols
            )
            if not external_names:
                continue

            if term_symbols & state_like_symbols:
                parameter_names.update(external_names)
                continue

            denominator = sympy.fraction(sympy.together(term))[1]
            denominator_names = _symbol_names(denominator.free_symbols) & external_symbol_names
            parameter_names.update(denominator_names)
            pure_terms.append(term)
    return pure_terms


def _infer_pure_term_roles(
    pure_terms: list[sympy.Expr],
    external_symbols: set[sympy.Symbol],
    metadata: Mapping[str, SymbolMetadata],
    parameter_names: set[str],
    input_names: set[str],
    *,
    mode: str,
) -> None:
    if mode == "configured":
        return

    changed = True
    while changed:
        changed = False
        for term in pure_terms:
            term_external = sorted(
                symbol.name
                for symbol in term.free_symbols
                if symbol in external_symbols and symbol.name not in metadata
            )
            unresolved = [
                name
                for name in term_external
                if name not in parameter_names and name not in input_names
            ]
            if len(unresolved) != 1:
                continue

            candidate = unresolved[0]
            candidate_symbol = sympy.Symbol(candidate)
            if sympy.simplify(sympy.diff(term, candidate_symbol, 2)) != 0:
                continue

            input_names.add(candidate)
            changed = True

            coefficient = sympy.simplify(sympy.diff(term, candidate_symbol))
            coefficient_symbols = {
                symbol.name
                for symbol in coefficient.free_symbols
                if symbol in external_symbols and symbol.name != candidate
            }
            new_parameters = coefficient_symbols - parameter_names - input_names
            if new_parameters:
                parameter_names.update(new_parameters)
                changed = True


def _ambiguous_pure_terms(
    pure_terms: list[sympy.Expr],
    external_symbols: set[sympy.Symbol],
    metadata: Mapping[str, SymbolMetadata],
    parameter_names: set[str],
    input_names: set[str],
) -> list[str]:
    ambiguous_terms: list[str] = []
    for term in pure_terms:
        term_external = sorted(
            symbol.name
            for symbol in term.free_symbols
            if symbol in external_symbols and symbol.name not in metadata
        )
        unresolved = [
            name
            for name in term_external
            if name not in parameter_names and name not in input_names
        ]
        if unresolved:
            ambiguous_terms.append(f"{sympy.sstr(term)} -> {', '.join(unresolved)}")
    return ambiguous_terms


def _finalize_metadata(
    metadata: dict[str, SymbolMetadata],
    external_symbols: set[sympy.Symbol],
    configured: Mapping[str, SymbolMetadata],
    parameter_names: set[str],
    input_names: set[str],
) -> dict[str, SymbolMetadata]:
    for symbol in sorted(external_symbols, key=lambda item: item.name):
        if symbol.name in metadata:
            continue
        if symbol.name in configured:
            metadata[symbol.name] = configured[symbol.name]
            continue
        if symbol.name in input_names:
            metadata[symbol.name] = SymbolMetadata(name=symbol.name, role="input", source="inferred")
            continue
        if symbol.name in parameter_names:
            metadata[symbol.name] = SymbolMetadata(name=symbol.name, role="parameter", source="inferred")
            continue
        metadata[symbol.name] = SymbolMetadata(name=symbol.name, role="unknown_unresolved", source="inferred")
    return dict(sorted(metadata.items()))


def classify_symbols(
    equations: list[EquationNode],
    derivative_orders: dict[str, int],
    state_names: tuple[str, ...],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
    reserved_symbols: set[str] | None = None,
) -> dict[str, SymbolMetadata]:
    """Classify states, inputs, parameters, and related symbols deterministically."""
    configured = load_symbol_config(symbol_config)
    _validate_classification_request(mode, configured)

    metadata = _seed_metadata(
        derivative_orders=derivative_orders,
        state_names=state_names,
        configured=configured,
    )

    explicit_rhs = [sympy.simplify(expression_to_sympy(equation.rhs)) for equation in equations]
    state_like_symbols = _build_state_like_symbols(derivative_orders, state_names)
    external_symbols = _collect_external_symbols(
        explicit_rhs,
        state_like_symbols,
        metadata,
        set(reserved_symbols or set()),
    )

    parameter_names = {
        entry.name
        for entry in configured.values()
        if entry.role in {"parameter", "known_constant"}
    }
    input_names = {
        entry.name
        for entry in configured.values()
        if entry.role == "input"
    }

    pure_terms = _scan_pure_terms(
        explicit_rhs=explicit_rhs,
        external_symbols=external_symbols,
        state_like_symbols=state_like_symbols,
        parameter_names=parameter_names,
    )
    _infer_pure_term_roles(
        pure_terms=pure_terms,
        external_symbols=external_symbols,
        metadata=metadata,
        parameter_names=parameter_names,
        input_names=input_names,
        mode=mode,
    )
    ambiguous_terms = _ambiguous_pure_terms(
        pure_terms=pure_terms,
        external_symbols=external_symbols,
        metadata=metadata,
        parameter_names=parameter_names,
        input_names=input_names,
    )

    if ambiguous_terms:
        raise DeterministicCompileError(
            "Ambiguous external-symbol classification encountered in pure forcing terms: "
            + "; ".join(ambiguous_terms)
        )

    metadata = _finalize_metadata(
        metadata=metadata,
        external_symbols=external_symbols,
        configured=configured,
        parameter_names=parameter_names,
        input_names=input_names,
    )

    unresolved = [
        entry.name
        for entry in metadata.values()
        if entry.role == "unknown_unresolved"
    ]
    if unresolved:
        raise DeterministicCompileError(
            "Unable to deterministically classify external symbols: "
            + ", ".join(sorted(unresolved))
        )

    return metadata
