"""Deterministic graph grouping and ownership helpers for Simulink lowering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass(frozen=True)
class GraphSubsystemPlan:
    """Precomputed subsystem ownership and layering for a lowered graph."""

    state_groups: tuple[str, ...]
    node_groups: dict[str, set[str]]
    node_owners: dict[str, str]
    node_layers: dict[str, int]


def build_graph_subsystem_plan(
    node_map: Mapping[str, Mapping[str, object]],
    state_chain_map: Mapping[str, Mapping[str, object]],
    *,
    root_system: str,
    group_key_for_state: Callable[[str], str],
    subsystem_id_for_group: Callable[[str], str],
) -> GraphSubsystemPlan:
    state_groups = tuple(sorted({group_key_for_state(state) for state in state_chain_map}))
    node_groups = _build_node_groups(node_map, state_chain_map, group_key_for_state)
    node_owners = _build_node_owners(
        node_map,
        node_groups,
        root_system=root_system,
        group_key_for_state=group_key_for_state,
        subsystem_id_for_group=subsystem_id_for_group,
    )
    node_layers = {
        node_id: _graph_layer(node_map, node_id, set())
        for node_id, node in node_map.items()
        if node["op"] not in {"state_signal", "integrator"}
    }
    return GraphSubsystemPlan(
        state_groups=state_groups,
        node_groups=node_groups,
        node_owners=node_owners,
        node_layers=node_layers,
    )


def _mark_group_dependency(
    node_map: Mapping[str, Mapping[str, object]],
    node_groups: dict[str, set[str]],
    *,
    node_id: str,
    group: str,
    seen: set[tuple[str, str]],
) -> None:
    marker = (node_id, group)
    if marker in seen:
        return
    seen.add(marker)
    node_groups.setdefault(node_id, set()).add(group)
    if node_map[node_id]["op"] in {"state_signal", "constant", "symbol_input"}:
        return
    for child_id in node_map[node_id].get("inputs", []):
        _mark_group_dependency(
            node_map,
            node_groups,
            node_id=str(child_id),
            group=group,
            seen=seen,
        )


def _build_node_groups(
    node_map: Mapping[str, Mapping[str, object]],
    state_chain_map: Mapping[str, Mapping[str, object]],
    group_key_for_state: Callable[[str], str],
) -> dict[str, set[str]]:
    node_groups: dict[str, set[str]] = {}
    for state, chain in state_chain_map.items():
        _mark_group_dependency(
            node_map,
            node_groups,
            node_id=str(chain["rhs"]),
            group=group_key_for_state(str(state)),
            seen=set(),
        )
    return node_groups


def _build_node_owners(
    node_map: Mapping[str, Mapping[str, object]],
    node_groups: Mapping[str, set[str]],
    *,
    root_system: str,
    group_key_for_state: Callable[[str], str],
    subsystem_id_for_group: Callable[[str], str],
) -> dict[str, str]:
    owners: dict[str, str] = {}
    for node_id, node in node_map.items():
        op = str(node["op"])
        if op in {"constant", "symbol_input"}:
            owners[node_id] = root_system
        elif op in {"integrator", "state_signal"}:
            owners[node_id] = subsystem_id_for_group(group_key_for_state(str(node["state"])))
        else:
            groups = sorted(node_groups.get(node_id, set()))
            owners[node_id] = subsystem_id_for_group(groups[0]) if len(groups) == 1 else root_system
    return owners


def _graph_layer(
    node_map: Mapping[str, Mapping[str, object]],
    node_id: str,
    active: set[str],
) -> int:
    if node_id in active:
        return 0
    node = node_map[node_id]
    op = str(node["op"])
    if op in {"constant", "symbol_input", "state_signal", "integrator"}:
        return 0
    active.add(node_id)
    child_layers = [_graph_layer(node_map, str(child_id), active) for child_id in node.get("inputs", [])]
    active.remove(node_id)
    return (max(child_layers) + 1) if child_layers else 0
