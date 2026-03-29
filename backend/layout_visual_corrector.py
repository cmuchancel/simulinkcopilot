"""Guardrailed visual post-correction for deterministic Simulink layouts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.layout_renderer import render_system_image
from backend.layout_metrics import LayoutMetrics, measure_layout
from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict, validate_simulink_model_dict
from repo_paths import WORKSPACE_ROOT
from simulink.utils import sanitize_block_name


load_dotenv()

ReasonCode = Literal[
    "resolve_overlap",
    "reduce_crossing_proxy",
    "separate_feedback",
    "align_integrator_chain",
    "reduce_label_collision",
    "improve_column_alignment",
    "improve_subsystem_balance",
    "increase_readability_margin",
]

DEFAULT_CRITIC_MODEL = "gpt-5.4"
DEFAULT_PATCH_MODEL = "gpt-5.4-mini"


class VisualIssue(BaseModel):
    kind: Literal[
        "clutter",
        "alignment",
        "feedback_loop",
        "integrator_chain",
        "label_collision",
        "subsystem_balance",
        "spacing",
    ]
    severity: int = Field(ge=1, le=5)
    evidence: str = ""
    target_block_ids: list[str] = Field(default_factory=list)
    recommended_reasons: list[ReasonCode] = Field(default_factory=list)


class VisualCritique(BaseModel):
    system: str
    summary: str = ""
    issues: list[VisualIssue] = Field(default_factory=list)


class PositionMove(BaseModel):
    block_id: str
    new_position: list[int] = Field(min_length=4, max_length=4)
    reason: ReasonCode


class VisualPatch(BaseModel):
    moves: list[PositionMove] = Field(default_factory=list)


@dataclass(frozen=True)
class VisualRepairConfig:
    critic_model: str = DEFAULT_CRITIC_MODEL
    patch_model: str = DEFAULT_PATCH_MODEL
    critic_detail: str = "original"
    patch_detail: str = "high"
    max_iterations: int = 2
    max_move_pixels: int = 160
    improvement_epsilon: float = 0.25
    artifact_dir: Path | None = None


def resolve_visual_repair_config(
    *,
    artifact_dir: str | Path | None = None,
) -> VisualRepairConfig:
    """Resolve visual repair settings from environment defaults."""
    shared_model = os.getenv("EQN2SIM_OPENAI_MODEL")
    return VisualRepairConfig(
        critic_model=os.getenv("EQN2SIM_VISUAL_CRITIC_MODEL") or shared_model or DEFAULT_CRITIC_MODEL,
        patch_model=os.getenv("EQN2SIM_VISUAL_PATCH_MODEL") or shared_model or DEFAULT_PATCH_MODEL,
        critic_detail=os.getenv("EQN2SIM_VISUAL_CRITIC_DETAIL", "original"),
        patch_detail=os.getenv("EQN2SIM_VISUAL_PATCH_DETAIL", "high"),
        max_iterations=int(os.getenv("EQN2SIM_VISUAL_REPAIR_MAX_ITERS", "2")),
        max_move_pixels=int(os.getenv("EQN2SIM_VISUAL_REPAIR_MAX_MOVE_PX", "160")),
        improvement_epsilon=float(os.getenv("EQN2SIM_VISUAL_REPAIR_EPSILON", "0.25")),
        artifact_dir=None if artifact_dir is None else Path(artifact_dir),
    )


def _resolve_client(client: OpenAI | None) -> OpenAI:
    if client is not None:
        return client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY was not found for visual layout repair.")
    return OpenAI(api_key=api_key)


def _image_to_data_url(path: str | Path) -> str:
    payload = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _systems_for_repair(model: BackendSimulinkModelDict) -> list[str]:
    subsystems = [
        block_id
        for block_id, block_spec in model["blocks"].items()
        if block_spec["type"] == "Subsystem" and block_spec["system"] == ROOT_SYSTEM
    ]
    return [ROOT_SYSTEM, *sorted(subsystems)]


def _system_block_summary(model: BackendSimulinkModelDict, system: str) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for block_id, block_spec in sorted(
        model["blocks"].items(),
        key=lambda item: (
            str(item[1]["system"]),
            int(item[1].get("position", [0, 0, 0, 0])[0]) if item[1].get("position") else 0,
            int(item[1].get("position", [0, 0, 0, 0])[1]) if item[1].get("position") else 0,
            item[0],
        ),
    ):
        if block_spec["system"] != system or block_spec.get("position") is None:
            continue
        metadata = block_spec.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        summary.append(
            {
                "block_id": block_id,
                "name": block_spec["name"],
                "type": block_spec["type"],
                "position": [int(value) for value in block_spec["position"]],
                "layout_role": metadata.get("layout_role"),
                "layer_hint": metadata.get("layer_hint"),
                "trace_expression": metadata.get("trace_expression"),
            }
        )
    return summary


def _system_connections(model: BackendSimulinkModelDict, system: str) -> list[dict[str, object]]:
    connections = []
    for connection in model["connections"]:
        if connection["system"] != system:
            continue
        connections.append(
            {
                "src_block": connection["src_block"],
                "dst_block": connection["dst_block"],
                "label": connection.get("label", ""),
            }
        )
    return connections


def _critique_prompt(
    *,
    system: str,
    metrics: LayoutMetrics,
    blocks: list[dict[str, object]],
    connections: list[dict[str, object]],
) -> str:
    return (
        "You are a visual layout critic for engineering block diagrams.\n"
        "Inspect the rendered diagram image and the structured model summary.\n"
        "Identify only visual/readability issues. Do not propose coordinates.\n"
        "Focus on clutter, awkward whitespace, poor alignment, unclear feedback loops, weak integrator-chain clarity, "
        "crowded labels, and subsystem balance.\n"
        f"System: {system}\n"
        f"Current metrics: {json.dumps(metrics.to_dict(), sort_keys=True)}\n"
        f"Blocks: {json.dumps(blocks, sort_keys=True)}\n"
        f"Connections: {json.dumps(connections, sort_keys=True)}\n"
        "Return a concise structured critique only."
    )


def _patch_prompt(
    *,
    system: str,
    critique: VisualCritique,
    blocks: list[dict[str, object]],
    connections: list[dict[str, object]],
    config: VisualRepairConfig,
) -> str:
    return (
        "You are a guardrailed visual repair agent for engineering block diagrams.\n"
        "You may only move blocks. Do not resize them. Keep width and height unchanged.\n"
        "Do not change names, types, params, labels, ports, connections, subsystem membership, or semantics.\n"
        f"Only propose moves for blocks inside system {system!r}.\n"
        f"Maximum absolute movement per move: {config.max_move_pixels} pixels.\n"
        "Return the minimum set of moves needed to improve readability.\n"
        f"Critique: {critique.model_dump_json()}\n"
        f"Blocks: {json.dumps(blocks, sort_keys=True)}\n"
        f"Connections: {json.dumps(connections, sort_keys=True)}\n"
        "Use only these reason codes: "
        "resolve_overlap, reduce_crossing_proxy, separate_feedback, align_integrator_chain, "
        "reduce_label_collision, improve_column_alignment, improve_subsystem_balance, increase_readability_margin.\n"
        "Return structured JSON only."
    )


def _run_structured_call(
    client: OpenAI,
    *,
    model: str,
    prompt: str,
    image_path: str | Path,
    detail: str,
    schema,
):
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": _image_to_data_url(image_path), "detail": detail},
                ],
            }
        ],
        text_format=schema,
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI visual repair response did not include parsed structured output.")
    return response.output_parsed


def _validate_candidate_patch(
    model: BackendSimulinkModelDict,
    *,
    system: str,
    patch: VisualPatch,
    before_metrics: LayoutMetrics,
    config: VisualRepairConfig,
) -> tuple[BackendSimulinkModelDict, LayoutMetrics] | None:
    if not patch.moves:
        return None
    candidate = deepcopy(model)
    seen: set[str] = set()
    for move in patch.moves:
        block_id = move.block_id
        if block_id in seen:
            return None
        seen.add(block_id)
        if block_id not in candidate["blocks"]:
            return None
        block_spec = candidate["blocks"][block_id]
        if block_spec["system"] != system or block_spec.get("position") is None:
            return None
        old_position = [int(value) for value in block_spec["position"]]
        new_position = [int(value) for value in move.new_position]
        old_width = old_position[2] - old_position[0]
        old_height = old_position[3] - old_position[1]
        new_width = new_position[2] - new_position[0]
        new_height = new_position[3] - new_position[1]
        if old_width != new_width or old_height != new_height:
            return None
        if any(value < 0 for value in new_position[:2]):
            return None
        deltas = [abs(new - old) for new, old in zip(new_position, old_position)]
        if max(deltas) > config.max_move_pixels:
            return None
        block_spec["position"] = new_position

    validated = validate_simulink_model_dict(candidate)
    after_metrics = measure_layout(validated)
    if after_metrics.block_overlap_count > before_metrics.block_overlap_count:
        return None
    if after_metrics.label_block_overlap_count > before_metrics.label_block_overlap_count:
        return None
    if after_metrics.label_label_overlap_count > before_metrics.label_label_overlap_count:
        return None
    if after_metrics.block_line_crossing_count > before_metrics.block_line_crossing_count:
        return None
    if after_metrics.estimated_page_count > before_metrics.estimated_page_count:
        return None
    if after_metrics.score <= before_metrics.score + config.improvement_epsilon:
        return None
    return validated, after_metrics


def apply_visual_repair(
    model: BackendSimulinkModelDict | dict[str, object],
    *,
    client: OpenAI | None = None,
    config: VisualRepairConfig | None = None,
) -> BackendSimulinkModelDict:
    """Apply bounded visual post-corrections using rendered image feedback."""
    active_config = config or resolve_visual_repair_config()
    resolved_client = _resolve_client(client)
    current = validate_simulink_model_dict(model)
    artifact_root = active_config.artifact_dir or (WORKSPACE_ROOT / "layout_bench" / "visual_repair" / sanitize_block_name(current["name"]))
    artifact_root.mkdir(parents=True, exist_ok=True)
    accepted_moves: list[dict[str, object]] = []
    iterations_run = 0

    for iteration in range(1, active_config.max_iterations + 1):
        iterations_run = iteration
        changed = False
        for system in _systems_for_repair(current):
            blocks = _system_block_summary(current, system)
            if len(blocks) < 2:
                continue
            connections = _system_connections(current, system)
            before_metrics = measure_layout(current)
            render_path = artifact_root / f"{iteration:02d}_{sanitize_block_name(system)}.png"
            render_system_image(current, system=system, output_path=render_path, title=f"{current['name']}:{system}")
            critique = _run_structured_call(
                resolved_client,
                model=active_config.critic_model,
                prompt=_critique_prompt(system=system, metrics=before_metrics, blocks=blocks, connections=connections),
                image_path=render_path,
                detail=active_config.critic_detail,
                schema=VisualCritique,
            )
            (artifact_root / f"{iteration:02d}_{sanitize_block_name(system)}_critique.json").write_text(
                critique.model_dump_json(indent=2),
                encoding="utf-8",
            )
            patch = _run_structured_call(
                resolved_client,
                model=active_config.patch_model,
                prompt=_patch_prompt(
                    system=system,
                    critique=critique,
                    blocks=blocks,
                    connections=connections,
                    config=active_config,
                ),
                image_path=render_path,
                detail=active_config.patch_detail,
                schema=VisualPatch,
            )
            (artifact_root / f"{iteration:02d}_{sanitize_block_name(system)}_patch.json").write_text(
                patch.model_dump_json(indent=2),
                encoding="utf-8",
            )
            validated_candidate = _validate_candidate_patch(
                current,
                system=system,
                patch=patch,
                before_metrics=before_metrics,
                config=active_config,
            )
            if validated_candidate is None:
                continue
            current, after_metrics = validated_candidate
            changed = True
            accepted_moves.append(
                {
                    "iteration": iteration,
                    "system": system,
                    "moves": patch.model_dump(),
                    "before_score": before_metrics.score,
                    "after_score": after_metrics.score,
                }
            )
        if not changed:
            break

    current.setdefault("metadata", {})
    current["metadata"]["visual_repair"] = {
        "enabled": True,
        "critic_model": active_config.critic_model,
        "patch_model": active_config.patch_model,
        "iterations_run": iterations_run,
        "accepted_move_batches": accepted_moves,
        "artifact_dir": str(artifact_root),
    }
    return current
