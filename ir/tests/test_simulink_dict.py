from __future__ import annotations

import pytest

from ir.simulink_dict import example_model, validate_model_dict


def test_validate_model_dict_normalizes_blocks_and_connections() -> None:
    model = validate_model_dict(
        {
            "name": "demo_model",
            "blocks": {
                "const1": {
                    "type": "Constant",
                    "lib_path": "simulink/Sources/Constant",
                    "params": {"Value": 1},
                    "position": (1, 2, 3, 4),
                },
                "scope1": {
                    "type": "Scope",
                    "lib_path": "simulink/Sinks/Scope",
                    "params": {},
                },
            },
            "connections": [
                ("const1", 1, "scope1", "1"),
            ],
        }
    )

    assert model["blocks"]["const1"]["position"] == [1, 2, 3, 4]
    assert model["connections"] == [("const1", "1", "scope1", "1")]


def test_example_model_returns_valid_minimal_chain() -> None:
    model = example_model("custom_name")

    assert model["name"] == "custom_name"
    assert set(model["blocks"]) == {"const1", "gain1", "scope1"}
    assert model["connections"] == [
        ("const1", "1", "gain1", "1"),
        ("gain1", "1", "scope1", "1"),
    ]


@pytest.mark.parametrize(
    ("payload", "error_type", "pattern"),
    [
        (None, TypeError, "dictionary-like mappings"),
        ({}, ValueError, "non-empty 'name'"),
        ({"name": "demo", "blocks": {}}, ValueError, "non-empty 'blocks' mapping"),
        (
            {"name": "demo", "blocks": {"": {"lib_path": "simulink/Sources/Constant"}}},
            ValueError,
            "Invalid block name",
        ),
        (
            {"name": "demo", "blocks": {"const1": "not-a-dict"}},
            TypeError,
            "must map to a dictionary",
        ),
        (
            {
                "name": "demo",
                "blocks": {"const1": {"lib_path": "simulink/Sources/Constant", "params": []}},
            },
            TypeError,
            "non-dictionary params",
        ),
        (
            {
                "name": "demo",
                "blocks": {"const1": {"lib_path": "simulink/Sources/Constant", "position": [1, 2, 3]}},
            },
            ValueError,
            "position must be a four-value list or tuple",
        ),
        (
            {
                "name": "demo",
                "blocks": {"const1": {"lib_path": "simulink/Sources/Constant"}},
                "connections": "not-a-list",
            },
            TypeError,
            "must be a list of 4-tuples",
        ),
        (
            {
                "name": "demo",
                "blocks": {"const1": {"lib_path": "simulink/Sources/Constant"}},
                "connections": [("const1", 1, "missing", 1)],
            },
            ValueError,
            "unknown destination block",
        ),
    ],
)
def test_validate_model_dict_rejects_invalid_models(payload, error_type, pattern) -> None:
    with pytest.raises(error_type, match=pattern):
        validate_model_dict(payload)
