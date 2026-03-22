from __future__ import annotations

import pytest

from backend.simulink_dict import ROOT_SYSTEM, SUBSYSTEM_BLOCK, validate_simulink_model_dict


def _valid_backend_model() -> dict[str, object]:
    return {
        "name": "backend_demo",
        "blocks": {
            "sub": {
                "type": "Subsystem",
                "lib_path": SUBSYSTEM_BLOCK,
            },
            "in1": {
                "type": "Inport",
                "lib_path": "simulink/Ports & Subsystems/In1",
                "system": "sub",
                "params": {"Port": 1},
            },
            "gain": {
                "type": "Gain",
                "lib_path": "simulink/Math Operations/Gain",
                "system": "sub",
                "params": {"Gain": 2},
                "position": [1, 2, 3, 4],
                "metadata": {"node": "g1"},
            },
            "out1": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "sub",
                "params": {"Port": 1},
            },
        },
        "connections": [
            {
                "system": "sub",
                "src_block": "gain",
                "src_port": 1,
                "dst_block": "out1",
                "dst_port": 1,
            },
            {
                "system": "sub",
                "src_block": "in1",
                "src_port": 1,
                "dst_block": "gain",
                "dst_port": 1,
                "label": "u",
                "metadata": {"trace": "edge-1"},
            },
        ],
        "outputs": [{"name": "y", "block": "out1", "port": "1"}],
        "model_params": {"StopTime": "5"},
        "workspace_variables": {"k": 2.0},
        "metadata": {"kind": "unit"},
    }


def test_validate_simulink_model_dict_normalizes_hierarchy_and_sorts_connections() -> None:
    model = validate_simulink_model_dict(_valid_backend_model())

    assert model["blocks"]["gain"]["system"] == "sub"
    assert model["blocks"]["gain"]["position"] == [1, 2, 3, 4]
    assert model["connections"][0]["src_block"] == "gain"
    assert model["connections"][1]["label"] == "u"
    assert model["outputs"] == [{"name": "y", "block": "out1", "port": "1"}]
    assert model["workspace_variables"] == {"k": 2.0}
    assert model["metadata"] == {"kind": "unit"}


def test_validate_simulink_model_dict_accepts_tuple_connections_and_default_names() -> None:
    model = validate_simulink_model_dict(
        {
            "name": "tuple_demo",
            "blocks": {
                "src": {"lib_path": "simulink/Sources/Constant"},
                "dst": {"lib_path": "simulink/Sinks/Out1"},
            },
            "connections": [("src", 1, "dst", 1)],
        }
    )

    assert model["blocks"]["src"]["type"] == "src"
    assert model["blocks"]["src"]["name"] == "src"
    assert model["connections"] == [
        {
            "system": ROOT_SYSTEM,
            "src_block": "src",
            "src_port": "1",
            "dst_block": "dst",
            "dst_port": "1",
            "label": "",
            "metadata": {},
        }
    ]


@pytest.mark.parametrize(
    ("payload", "error_type", "pattern"),
    [
        (None, TypeError, "dictionary-like mappings"),
        ({}, ValueError, "non-empty 'name'"),
        ({"name": "demo", "blocks": {}}, ValueError, "non-empty 'blocks' mapping"),
        (
            {"name": "demo", "blocks": {"b": {"lib_path": "simulink/Sources/Constant", "metadata": []}}},
            TypeError,
            "metadata must be a mapping",
        ),
        (
            {"name": "demo", "blocks": {"b": {"lib_path": "simulink/Sources/Constant", "params": []}}},
            TypeError,
            "non-dictionary params",
        ),
        (
            {"name": "demo", "blocks": {"b": {"lib_path": "simulink/Sources/Constant", "position": [1, 2, 3]}}},
            ValueError,
            "position must be a four-value list",
        ),
        (
            {"name": "demo", "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}}, "connections": "bad"},
            TypeError,
            "Model 'connections' must be a list",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "connections": [{"src_block": "b", "src_port": 1, "dst_block": "c", "dst_port": 1, "metadata": []}],
            },
            TypeError,
            "Invalid connection metadata",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "connections": [{"src_block": "", "src_port": 1, "dst_block": "b", "dst_port": 1}],
            },
            ValueError,
            "Invalid connection entry",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "connections": ["bad"],
            },
            ValueError,
            "Invalid connection entry",
        ),
        (
            {
                "name": "demo",
                "blocks": {"child": {"lib_path": "simulink/Sources/Constant", "system": "missing"}},
            },
            ValueError,
            "unknown parent system",
        ),
        (
            {
                "name": "demo",
                "blocks": {
                    "parent": {"lib_path": "simulink/Sources/Constant"},
                    "child": {"lib_path": "simulink/Sources/Constant", "system": "parent"},
                },
            },
            ValueError,
            "is not a subsystem block",
        ),
        (
            {
                "name": "demo",
                "blocks": {
                    "sub": {"lib_path": SUBSYSTEM_BLOCK},
                    "child": {"lib_path": "simulink/Sources/Constant", "system": "sub"},
                },
                "connections": [{"system": "missing", "src_block": "child", "src_port": 1, "dst_block": "child", "dst_port": 1}],
            },
            ValueError,
            "unknown system",
        ),
        (
            {
                "name": "demo",
                "blocks": {
                    "plain": {"lib_path": "simulink/Sources/Constant"},
                    "child": {"lib_path": "simulink/Sources/Constant", "system": ROOT_SYSTEM},
                },
                "connections": [{"system": "plain", "src_block": "child", "src_port": 1, "dst_block": "child", "dst_port": 1}],
            },
            ValueError,
            "is not a subsystem block",
        ),
        (
            {
                "name": "demo",
                "blocks": {
                    "sub": {"lib_path": SUBSYSTEM_BLOCK},
                    "child": {"lib_path": "simulink/Sources/Constant", "system": "sub"},
                    "other": {"lib_path": "simulink/Sources/Constant"},
                },
                "connections": [{"system": "sub", "src_block": "other", "src_port": 1, "dst_block": "child", "dst_port": 1}],
            },
            ValueError,
            "does not belong to connection system",
        ),
        (
            {
                "name": "demo",
                "blocks": {
                    "sub": {"lib_path": SUBSYSTEM_BLOCK},
                    "src": {"lib_path": "simulink/Sources/Constant", "system": "sub"},
                    "dst": {"lib_path": "simulink/Sources/Constant"},
                },
                "connections": [{"system": "sub", "src_block": "src", "src_port": 1, "dst_block": "dst", "dst_port": 1}],
            },
            ValueError,
            "does not belong to connection system",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "connections": [{"src_block": "missing", "src_port": 1, "dst_block": "b", "dst_port": 1}],
            },
            ValueError,
            "unknown source block",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "connections": [{"src_block": "b", "src_port": 1, "dst_block": "missing", "dst_port": 1}],
            },
            ValueError,
            "unknown destination block",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "outputs": "bad",
            },
            TypeError,
            "outputs' must be a list",
        ),
        (
            {
                "name": "demo",
                "blocks": {None: {"lib_path": "simulink/Sources/Constant"}},
            },
            ValueError,
            "Invalid block name",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": []},
            },
            TypeError,
            "must map to a dictionary of properties",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "outputs": [{"name": "", "block": "b", "port": "1"}],
            },
            ValueError,
            "Invalid output spec",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "outputs": ["bad"],
            },
            TypeError,
            "Invalid output spec",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "outputs": [{"name": "y", "block": "missing", "port": "1"}],
            },
            ValueError,
            "unknown block",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "model_params": [],
            },
            TypeError,
            "model_params' must be a mapping",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "workspace_variables": [],
            },
            TypeError,
            "workspace_variables' must be a mapping",
        ),
        (
            {
                "name": "demo",
                "blocks": {"b": {"lib_path": "simulink/Sources/Constant"}},
                "metadata": [],
            },
            TypeError,
            "metadata' must be a mapping",
        ),
    ],
)
def test_validate_simulink_model_dict_rejects_invalid_payloads(payload, error_type, pattern) -> None:
    with pytest.raises(error_type, match=pattern):
        validate_simulink_model_dict(payload)
