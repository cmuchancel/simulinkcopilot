"""Deterministic lowering from symbolic IR to graph dictionaries."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ir.equation_dict import expression_to_dict
from ir.graph_dict import canonicalize_graph_dict
from ir.graph_validate import validate_graph_dict
from latex_frontend.symbols import DeterministicCompileError, SUPPORTED_FUNCTION_NAMES, state_name


def _sanitize(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name)


@dataclass
class GraphBuilder:
    kind: str
    name: str
    state_names: set[str] = field(default_factory=set)
    input_names: set[str] = field(default_factory=set)
    parameter_names: set[str] = field(default_factory=set)
    independent_variable_names: set[str] = field(default_factory=set)
    nodes: dict[str, dict[str, object]] = field(default_factory=dict)
    expression_cache: dict[str, str] = field(default_factory=dict)
    counter: int = 0

    def _next_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}_{self.counter:04d}"

    def _emit_node(
        self,
        node_id: str,
        op: str,
        inputs: list[str] | None = None,
        **metadata: object,
    ) -> str:
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "op": op,
                "inputs": list(inputs or []),
                **metadata,
            }
        return node_id

    def _cache_expression(self, key: dict[str, object], node_id: str) -> str:
        cache_key = json.dumps(key, sort_keys=True)
        self.expression_cache[cache_key] = node_id
        return node_id

    def _cached_expression(self, key: dict[str, object]) -> str | None:
        return self.expression_cache.get(json.dumps(key, sort_keys=True))

    def _lower_symbol(self, name: str) -> str:
        if name in self.state_names:
            signal_id = f"state_{_sanitize(name)}"
            source_id = f"integrator_{_sanitize(name)}"
            if self.kind != "first_order_system_graph":
                source_id = self._emit_node(
                    f"state_source_{_sanitize(name)}",
                    "symbol_input",
                    [],
                    name=name,
                    symbol_role="state_source",
                )
            return self._emit_node(
                signal_id,
                "state_signal",
                [source_id],
                state=name,
            )
        if name in self.independent_variable_names:
            return self._emit_node(
                f"symbol_{_sanitize(name)}",
                "symbol_input",
                [],
                name=name,
                symbol_role="independent_variable",
            )
        role = "parameter" if name in self.parameter_names else "input"
        return self._emit_node(
            f"symbol_{_sanitize(name)}",
            "symbol_input",
            [],
            name=name,
            symbol_role=role,
        )

    def lower_expression(self, expression_dict: dict[str, object]) -> str:
        cached = self._cached_expression(expression_dict)
        if cached is not None:
            return cached

        op = expression_dict["op"]
        if op == "const":
            node_id = self._emit_node(
                f"const_{_sanitize(str(expression_dict['value']))}",
                "constant",
                [],
                value=expression_dict["value"],
            )
            return self._cache_expression(expression_dict, node_id)
        if op == "symbol":
            node_id = self._lower_symbol(expression_dict["name"])
            return self._cache_expression(expression_dict, node_id)
        if op == "derivative":
            derived_state = state_name(expression_dict["base"], int(expression_dict["order"]))  # type: ignore[arg-type]
            node_id = self._lower_symbol(derived_state)
            return self._cache_expression(expression_dict, node_id)

        child_ids = [self.lower_expression(child) for child in expression_dict["args"]]

        if op == "neg":
            node_id = self._emit_node(self._next_id("expr"), "negate", child_ids)
        elif op == "add":
            node_id = self._emit_node(
                self._next_id("expr"),
                "add" if len(child_ids) == 2 else "sum",
                child_ids,
            )
        elif op == "mul":
            child_ops = [self.nodes[child_id]["op"] for child_id in child_ids]
            gain_like = len(child_ids) == 2 and any(
                child_op in {"constant", "symbol_input"}
                for child_op in child_ops
            )
            node_id = self._emit_node(self._next_id("expr"), "gain" if gain_like else "mul", child_ids)
        elif op == "div":
            node_id = self._emit_node(self._next_id("expr"), "div", child_ids)
        elif op == "pow":
            node_id = self._emit_node(self._next_id("expr"), "pow", child_ids)
        elif op in SUPPORTED_FUNCTION_NAMES:
            node_id = self._emit_node(self._next_id("expr"), op, child_ids)
        else:
            raise DeterministicCompileError(f"Unsupported graph-lowering op {op!r}.")

        structural_key = {"op": op, "children": child_ids}
        self._cache_expression(expression_dict, node_id)
        return self._cache_expression(structural_key, node_id)

    def to_graph(self, outputs: dict[str, str], state_chains: list[dict[str, str]] | None = None) -> dict[str, object]:
        graph = {
            "kind": self.kind,
            "name": self.name,
            "nodes": list(self.nodes.values()),
            "edges": [
                {"src": input_id, "dst": node["id"], "dst_port": index}
                for node in self.nodes.values()
                for index, input_id in enumerate(node["inputs"])
            ],
            "outputs": dict(outputs),
        }
        if state_chains is not None:
            graph["state_chains"] = list(state_chains)
        return validate_graph_dict(canonicalize_graph_dict(graph))


def lower_expression_graph(
    expression_dict: dict[str, object],
    *,
    state_names: set[str] | None = None,
    input_names: set[str] | None = None,
    parameter_names: set[str] | None = None,
    independent_variable_names: set[str] | None = None,
    name: str = "expression_graph",
) -> dict[str, object]:
    """Lower a single expression dictionary to a deterministic graph."""
    builder = GraphBuilder(
        kind="expression_graph",
        name=name,
        state_names=set(state_names or set()),
        input_names=set(input_names or set()),
        parameter_names=set(parameter_names or set()),
        independent_variable_names=set(independent_variable_names or set()),
    )
    output_id = builder.lower_expression(expression_dict)
    return builder.to_graph(outputs={"result": output_id})


def lower_first_order_system_graph(first_order_system: dict[str, object], *, name: str = "first_order_graph") -> dict[str, object]:
    """Lower a first-order system into a deterministic graph dictionary."""
    states = list(first_order_system["states"])  # type: ignore[index]
    inputs = set(first_order_system["inputs"])  # type: ignore[index]
    parameters = set(first_order_system["parameters"])  # type: ignore[index]
    builder = GraphBuilder(
        kind="first_order_system_graph",
        name=name,
        state_names=set(states),
        input_names=inputs,
        parameter_names=parameters,
        independent_variable_names=(
            {str(first_order_system["independent_variable"])}
            if first_order_system.get("independent_variable")
            else set()
        ),
    )

    for state in states:
        integrator_id = f"integrator_{_sanitize(state)}"
        builder._emit_node(integrator_id, "integrator", ["__pending__"], state=state)
        builder._emit_node(f"state_{_sanitize(state)}", "state_signal", [integrator_id], state=state)

    outputs: dict[str, str] = {}
    state_chains: list[dict[str, str]] = []
    for entry in first_order_system["state_equations"]:  # type: ignore[index]
        state = entry["state"]
        rhs_id = builder.lower_expression(entry["rhs"])  # type: ignore[arg-type]
        integrator_id = f"integrator_{_sanitize(state)}"
        builder.nodes[integrator_id]["inputs"] = [rhs_id]
        signal_id = f"state_{_sanitize(state)}"
        outputs[state] = signal_id
        outputs[f"rhs_{state}"] = rhs_id
        state_chains.append(
            {
                "state": state,
                "signal": signal_id,
                "integrator": integrator_id,
                "rhs": rhs_id,
            }
        )

    return builder.to_graph(outputs=outputs, state_chains=state_chains)
