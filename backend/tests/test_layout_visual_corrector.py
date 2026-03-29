from __future__ import annotations

from pathlib import Path

from backend.layout import apply_deterministic_layout
from backend.layout_metrics import measure_layout
from backend.layout_renderer import render_system_image
from backend.layout_visual_corrector import (
    PositionMove,
    VisualCritique,
    VisualIssue,
    VisualPatch,
    VisualRepairConfig,
    _validate_candidate_patch,
    apply_visual_repair,
)
from backend.simulink_dict import SUBSYSTEM_BLOCK, validate_simulink_model_dict


def _feedback_model() -> dict[str, object]:
    return {
        "name": "visual_repair_demo",
        "blocks": {
            "subsystem": {
                "type": "Subsystem",
                "lib_path": SUBSYSTEM_BLOCK,
                "system": "root",
                "name": "dynamics",
                "metadata": {"layout_role": "subsystem", "inport_count": 1, "outport_count": 1},
            },
            "in": {
                "type": "Inport",
                "lib_path": "simulink/Ports & Subsystems/In1",
                "system": "subsystem",
                "name": "u",
                "params": {"Port": 1},
                "metadata": {"layout_role": "inport", "trace_expression": "u"},
            },
            "sum": {
                "type": "Sum",
                "lib_path": "simulink/Math Operations/Sum",
                "system": "subsystem",
                "name": "sum",
                "params": {"Inputs": "++"},
                "metadata": {"layout_role": "compute", "layer_hint": 0, "trace_expression": "u-x"},
            },
            "neg": {
                "type": "Gain",
                "lib_path": "simulink/Math Operations/Gain",
                "system": "subsystem",
                "name": "neg_x",
                "params": {"Gain": "-1"},
                "metadata": {"layout_role": "compute", "layer_hint": 0, "trace_expression": "-x"},
            },
            "int_x_dot": {
                "type": "Integrator",
                "lib_path": "simulink/Continuous/Integrator",
                "system": "subsystem",
                "name": "x_dot",
                "metadata": {"layout_role": "integrator", "state": "x_dot", "state_order": 1, "trace_expression": "x_dot"},
            },
            "int_x": {
                "type": "Integrator",
                "lib_path": "simulink/Continuous/Integrator",
                "system": "subsystem",
                "name": "x",
                "metadata": {"layout_role": "integrator", "state": "x", "state_order": 0, "trace_expression": "x"},
            },
            "out": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "subsystem",
                "name": "y",
                "params": {"Port": 1},
                "metadata": {"layout_role": "outport", "trace_expression": "x"},
            },
        },
        "connections": [
            {"system": "subsystem", "src_block": "in", "src_port": "1", "dst_block": "sum", "dst_port": "1", "label": "u"},
            {"system": "subsystem", "src_block": "sum", "src_port": "1", "dst_block": "int_x_dot", "dst_port": "1", "label": "u-x"},
            {"system": "subsystem", "src_block": "int_x_dot", "src_port": "1", "dst_block": "int_x", "dst_port": "1", "label": "x_dot"},
            {"system": "subsystem", "src_block": "int_x", "src_port": "1", "dst_block": "neg", "dst_port": "1", "label": "x"},
            {"system": "subsystem", "src_block": "neg", "src_port": "1", "dst_block": "sum", "dst_port": "2", "label": "-x"},
            {"system": "subsystem", "src_block": "int_x", "src_port": "1", "dst_block": "out", "dst_port": "1", "label": "x"},
        ],
        "outputs": [],
    }


class _FakeResponse:
    def __init__(self, payload) -> None:
        self.output_parsed = payload


class _FakeResponses:
    def __init__(self, payloads: list[object]) -> None:
        self._payloads = list(payloads)

    def parse(self, **kwargs):
        return _FakeResponse(self._payloads.pop(0))


class _FakeClient:
    def __init__(self, payloads: list[object]) -> None:
        self.responses = _FakeResponses(payloads)


def test_render_system_image_writes_png(tmp_path: Path) -> None:
    model = apply_deterministic_layout(validate_simulink_model_dict(_feedback_model()))

    rendered = render_system_image(model, system="subsystem", output_path=tmp_path / "subsystem.png")

    assert Path(rendered.path).exists()


def test_visual_patch_validator_rejects_resizing_moves() -> None:
    model = apply_deterministic_layout(validate_simulink_model_dict(_feedback_model()))
    patch = VisualPatch(moves=[PositionMove(block_id="neg", new_position=[100, 100, 260, 200], reason="separate_feedback")])

    result = _validate_candidate_patch(
        model,
        system="subsystem",
        patch=patch,
        before_metrics=measure_layout(model),
        config=VisualRepairConfig(max_move_pixels=200),
    )

    assert result is None


def test_apply_visual_repair_accepts_improving_patch_and_records_metadata(tmp_path: Path) -> None:
    model = apply_deterministic_layout(validate_simulink_model_dict(_feedback_model()))
    before_neg = list(model["blocks"]["neg"]["position"])
    improving_patch = VisualPatch(
        moves=[
            PositionMove(
                block_id="neg",
                new_position=[before_neg[0], before_neg[1] + 40, before_neg[2], before_neg[3] + 40],
                reason="separate_feedback",
            )
        ]
    )
    client = _FakeClient(
        [
            VisualCritique(
                system="subsystem",
                summary="Feedback leg is too low and bends across the lower area.",
                issues=[
                    VisualIssue(
                        kind="feedback_loop",
                        severity=4,
                        evidence="The reverse-flow leg has unnecessary vertical travel.",
                        target_block_ids=["neg", "sum", "int_x"],
                        recommended_reasons=["separate_feedback"],
                    )
                ],
            ),
            improving_patch,
        ]
    )

    repaired = apply_visual_repair(
        model,
        client=client,
        config=VisualRepairConfig(max_iterations=1, max_move_pixels=80, artifact_dir=tmp_path),
    )

    assert repaired["blocks"]["neg"]["position"] != before_neg
    assert repaired["metadata"]["visual_repair"]["accepted_move_batches"]


def test_apply_visual_repair_noops_when_patch_has_no_moves(tmp_path: Path) -> None:
    model = apply_deterministic_layout(validate_simulink_model_dict(_feedback_model()))
    before_neg = list(model["blocks"]["neg"]["position"])
    client = _FakeClient(
        [
            VisualCritique(
                system="subsystem",
                summary="Diagram is already acceptable.",
                issues=[],
            ),
            VisualPatch(moves=[]),
        ]
    )

    repaired = apply_visual_repair(
        model,
        client=client,
        config=VisualRepairConfig(max_iterations=1, max_move_pixels=80, artifact_dir=tmp_path),
    )

    assert repaired["blocks"]["neg"]["position"] == before_neg
    assert repaired["metadata"]["visual_repair"]["accepted_move_batches"] == []
