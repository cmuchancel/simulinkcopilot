from __future__ import annotations

from backend import layout as layout_module
from backend.layout import LayoutProfile, apply_deterministic_layout, audit_layout
from backend.simulink_dict import SUBSYSTEM_BLOCK, validate_simulink_model_dict


def _root_spacing_model(label: str) -> dict[str, object]:
    return {
        "name": "root_spacing_demo",
        "blocks": {
            "subsystem": {
                "type": "Subsystem",
                "lib_path": SUBSYSTEM_BLOCK,
                "system": "root",
                "name": "dynamics",
                "metadata": {"layout_role": "subsystem", "inport_count": 1, "outport_count": 1},
            },
            "src": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "system": "root",
                "name": "u",
                "metadata": {"layout_role": "source", "trace_expression": "u"},
            },
            "out": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "root",
                "name": "y",
                "metadata": {"layout_role": "output", "trace_expression": "y"},
            },
        },
        "connections": [
            {
                "system": "root",
                "src_block": "src",
                "src_port": "1",
                "dst_block": "subsystem",
                "dst_port": "1",
                "label": label,
            },
            {
                "system": "root",
                "src_block": "subsystem",
                "src_port": "1",
                "dst_block": "out",
                "dst_port": "1",
                "label": "y",
            },
        ],
        "outputs": [{"name": "y", "block": "out", "port": "1"}],
    }


def _subsystem_spacing_model(label: str) -> dict[str, object]:
    return {
        "name": "subsystem_spacing_demo",
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
            "gain": {
                "type": "Gain",
                "lib_path": "simulink/Math Operations/Gain",
                "system": "subsystem",
                "name": "gain",
                "params": {"Gain": "2"},
                "metadata": {"layout_role": "compute", "layer_hint": 0, "trace_expression": label},
            },
            "int": {
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
                "metadata": {"layout_role": "outport", "trace_expression": "y"},
            },
        },
        "connections": [
            {"system": "subsystem", "src_block": "in", "src_port": "1", "dst_block": "gain", "dst_port": "1", "label": "u"},
            {"system": "subsystem", "src_block": "gain", "src_port": "1", "dst_block": "int", "dst_port": "1", "label": label},
            {"system": "subsystem", "src_block": "int", "src_port": "1", "dst_block": "out", "dst_port": "1", "label": "x"},
        ],
        "outputs": [],
    }


def _row_spacing_model(label: str) -> dict[str, object]:
    return {
        "name": "row_spacing_demo",
        "blocks": {
            "subsystem": {
                "type": "Subsystem",
                "lib_path": SUBSYSTEM_BLOCK,
                "system": "root",
                "name": "dynamics",
                "metadata": {"layout_role": "subsystem", "inport_count": 2, "outport_count": 1},
            },
            "src_a": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "system": "root",
                "name": "u_a",
                "metadata": {"layout_role": "source", "trace_expression": "u_a"},
            },
            "src_b": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "system": "root",
                "name": "u_b",
                "metadata": {"layout_role": "source", "trace_expression": "u_b"},
            },
            "out": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "root",
                "name": "y",
                "metadata": {"layout_role": "output", "trace_expression": "y"},
            },
        },
        "connections": [
            {"system": "root", "src_block": "src_a", "src_port": "1", "dst_block": "subsystem", "dst_port": "1", "label": label},
            {"system": "root", "src_block": "src_b", "src_port": "1", "dst_block": "subsystem", "dst_port": "2", "label": "u_b"},
            {"system": "root", "src_block": "subsystem", "src_port": "1", "dst_block": "out", "dst_port": "1", "label": "y"},
        ],
        "outputs": [{"name": "y", "block": "out", "port": "1"}],
    }


def test_root_column_spacing_grows_with_long_connection_labels() -> None:
    short_model = apply_deterministic_layout(validate_simulink_model_dict(_root_spacing_model("u")))
    long_model = apply_deterministic_layout(
        validate_simulink_model_dict(
            _root_spacing_model("very_long_trace_expression_that_should_force_more_horizontal_clearance")
        )
    )

    short_subsystem_x = short_model["blocks"]["subsystem"]["position"][0]
    long_subsystem_x = long_model["blocks"]["subsystem"]["position"][0]
    assert long_subsystem_x > short_subsystem_x


def test_subsystem_column_spacing_grows_with_long_internal_trace_labels() -> None:
    short_model = apply_deterministic_layout(validate_simulink_model_dict(_subsystem_spacing_model("x")))
    long_model = apply_deterministic_layout(
        validate_simulink_model_dict(
            _subsystem_spacing_model("extremely_long_internal_debug_trace_expression_for_rhs_signal")
        )
    )

    short_integrator_x = short_model["blocks"]["int"]["position"][0]
    long_integrator_x = long_model["blocks"]["int"]["position"][0]
    assert long_integrator_x > short_integrator_x


def test_root_row_spacing_grows_with_multiline_trace_budget() -> None:
    short_model = apply_deterministic_layout(validate_simulink_model_dict(_row_spacing_model("u_a")))
    long_model = apply_deterministic_layout(
        validate_simulink_model_dict(
            _row_spacing_model("this_trace_expression_is_long_enough_to_wrap_and_need_more_vertical_clearance")
        )
    )

    short_second_source_y = short_model["blocks"]["src_b"]["position"][1]
    long_second_source_y = long_model["blocks"]["src_b"]["position"][1]
    assert long_second_source_y > short_second_source_y


def test_layout_audit_detects_manual_block_overlap() -> None:
    overlapping_model = validate_simulink_model_dict(
        {
            "name": "manual_overlap_demo",
            "blocks": {
                "a": {
                    "type": "Constant",
                    "lib_path": "simulink/Sources/Constant",
                    "system": "root",
                    "name": "a",
                    "position": [40, 40, 150, 80],
                    "metadata": {"layout_role": "source", "trace_expression": "a"},
                },
                "b": {
                    "type": "Gain",
                    "lib_path": "simulink/Math Operations/Gain",
                    "system": "root",
                    "name": "b",
                    "position": [120, 55, 230, 95],
                    "metadata": {"layout_role": "shared", "trace_expression": "b"},
                },
            },
            "connections": [],
            "outputs": [],
        }
    )

    report = audit_layout(overlapping_model)
    assert report.block_overlap_count == 1
    assert not report.passes


def test_apply_deterministic_layout_repairs_cramped_profile() -> None:
    model = validate_simulink_model_dict(
        _root_spacing_model("very_long_trace_expression_that_should_force_more_horizontal_clearance_and_repair")
    )
    cramped_profile = LayoutProfile(
        root_shared_x=100,
        root_subsystem_x=120,
        root_outport_x=180,
        min_column_gap=8,
        min_row_gap=4,
        horizontal_scale=0.25,
        vertical_scale=0.25,
    )

    first_pass = apply_deterministic_layout(model, profile=cramped_profile, max_iterations=1)
    assert first_pass["metadata"]["layout_quality"]["passes"] is False

    repaired = apply_deterministic_layout(model, profile=cramped_profile)
    assert repaired["metadata"]["layout_quality"]["passes"] is True
    assert repaired["metadata"]["layout_quality"]["iterations"] > 1


def test_layout_helper_paths_cover_empty_text_and_missing_positions() -> None:
    profile = LayoutProfile()
    block_spec = {"type": "Gain", "name": "gain", "metadata": []}
    assert layout_module._block_visible_text(block_spec) == "gain"
    assert layout_module._estimated_text_width("", profile) == 0
    assert layout_module._estimated_text_lines("   ", profile) == 1

    model = validate_simulink_model_dict(
        {
            "name": "layout_helpers",
            "blocks": {
                "a": {
                    "type": "Constant",
                    "lib_path": "simulink/Sources/Constant",
                    "system": "root",
                    "name": "a",
                    "metadata": {"layout_role": "source"},
                },
                "b": {
                    "type": "Gain",
                    "lib_path": "simulink/Math Operations/Gain",
                    "system": "root",
                    "name": "b",
                    "metadata": {"layout_role": "shared"},
                },
            },
            "connections": [{"system": "root", "src_block": "a", "src_port": "1", "dst_block": "b", "dst_port": "1", "label": ""}],
            "outputs": [],
        }
    )

    assert layout_module._label_rect(model, model["connections"][0], profile) is None
    report = audit_layout(model)
    assert report.block_overlap_count == 0


def test_label_rect_returns_none_when_blocks_lack_positions_even_with_a_label() -> None:
    profile = LayoutProfile()
    model = validate_simulink_model_dict(
        {
            "name": "layout_label_missing_positions",
            "blocks": {
                "a": {
                    "type": "Constant",
                    "lib_path": "simulink/Sources/Constant",
                    "system": "root",
                    "name": "a",
                    "metadata": {"layout_role": "source"},
                },
                "b": {
                    "type": "Gain",
                    "lib_path": "simulink/Math Operations/Gain",
                    "system": "root",
                    "name": "b",
                    "metadata": {"layout_role": "shared"},
                },
            },
            "connections": [
                {"system": "root", "src_block": "a", "src_port": "1", "dst_block": "b", "dst_port": "1", "label": "trace"}
            ],
            "outputs": [],
        }
    )

    assert layout_module._label_rect(model, model["connections"][0], profile) is None


def test_apply_deterministic_layout_zero_iteration_falls_back_to_best_model() -> None:
    model = validate_simulink_model_dict(_root_spacing_model("u"))
    laid_out = apply_deterministic_layout(model, max_iterations=0)

    assert "layout_quality" in laid_out["metadata"]
