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


def classify_symbols(
    equations: list[EquationNode],
    derivative_orders: dict[str, int],
    state_names: tuple[str, ...],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> dict[str, SymbolMetadata]:
    """Classify states, inputs, parameters, and related symbols deterministically."""
    if mode not in {"strict", "configured"}:
        raise DeterministicCompileError(f"Unsupported symbol-classification mode {mode!r}.")

    configured = load_symbol_config(symbol_config)
    if mode == "strict" and configured:
        raise DeterministicCompileError("Strict symbol classification cannot use a symbol configuration.")

    metadata: dict[str, SymbolMetadata] = {}
    for base in sorted(derivative_orders):
        if base in configured and configured[base].role != "state_candidate":
            raise DeterministicCompileError(
                f"Configured symbol {base!r} conflicts with inferred state-candidate role."
            )
        metadata[base] = SymbolMetadata(name=base, role="state_candidate", source="inferred")

    for name in sorted(state_names):
        if name in metadata:
            continue
        metadata[name] = SymbolMetadata(name=name, role="derivative_derived_state", source="inferred")

    explicit_rhs = [sympy.simplify(expression_to_sympy(equation.rhs)) for equation in equations]
    state_like_symbols = {sympy.Symbol(name) for name in derivative_orders}
    state_like_symbols.update(sympy.Symbol(name) for name in state_names)
    state_like_symbols.update(
        sympy.Symbol(derivative_symbol_name(base, order))
        for base, max_order in derivative_orders.items()
        for order in range(1, max_order + 1)
    )

    free_symbols = set().union(*(expr.free_symbols for expr in explicit_rhs)) if explicit_rhs else set()
    external_symbols = {
        symbol
        for symbol in free_symbols
        if symbol not in state_like_symbols and symbol.name not in metadata
    }

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

    for symbol in sorted(external_symbols, key=lambda item: item.name):
        if symbol.name == "t" and symbol.name not in configured:
            metadata[symbol.name] = SymbolMetadata(
                name=symbol.name,
                role="independent_variable",
                source="inferred",
            )

    pure_terms: list[sympy.Expr] = []
    for expr in explicit_rhs:
        for term in _as_additive_terms(expr):
            term_symbols = term.free_symbols
            external_names = sorted(
                symbol.name
                for symbol in term_symbols
                if symbol in external_symbols and symbol.name not in metadata
            )
            if not external_names:
                continue

            if term_symbols & state_like_symbols:
                parameter_names.update(external_names)
                continue

            denominator = sympy.fraction(sympy.together(term))[1]
            denominator_names = _symbol_names(denominator.free_symbols) & set(external_names)
            parameter_names.update(denominator_names)
            pure_terms.append(term)

    changed = True
    while changed:
        changed = False
        for term in pure_terms:
            if mode == "configured":
                continue
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
            if sympy.simplify(sympy.diff(term, sympy.Symbol(candidate), 2)) != 0:
                continue

            input_names.add(candidate)
            changed = True

            coefficient = sympy.simplify(sympy.diff(term, sympy.Symbol(candidate)))
            coefficient_symbols = {
                symbol.name
                for symbol in coefficient.free_symbols
                if symbol in external_symbols and symbol.name != candidate
            }
            new_parameters = coefficient_symbols - parameter_names - input_names
            if new_parameters:
                parameter_names.update(new_parameters)
                changed = True

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

    if ambiguous_terms:
        raise DeterministicCompileError(
            "Ambiguous external-symbol classification encountered in pure forcing terms: "
            + "; ".join(ambiguous_terms)
        )

    for name in sorted(external_symbols, key=lambda item: item.name):
        if name.name in metadata:
            continue
        if name.name in configured:
            metadata[name.name] = configured[name.name]
            continue
        if name.name in input_names:
            metadata[name.name] = SymbolMetadata(name=name.name, role="input", source="inferred")
            continue
        if name.name in parameter_names:
            metadata[name.name] = SymbolMetadata(name=name.name, role="parameter", source="inferred")
            continue
        metadata[name.name] = SymbolMetadata(name=name.name, role="unknown_unresolved", source="inferred")

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

    return dict(sorted(metadata.items()))
