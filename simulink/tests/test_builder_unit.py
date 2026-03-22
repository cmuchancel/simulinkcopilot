from __future__ import annotations

import importlib
import sys
import types

from simulink.constants import DEFAULT_BLOCK_POSITION, DEFAULT_HORIZONTAL_SPACING


class FakeEngine:
    def __init__(self) -> None:
        self.workspace: dict[str, object] = {}
        self.calls: list[tuple[object, ...]] = []

    def eval(self, expression: str, nargout: int = 0) -> None:
        self.calls.append(("eval", expression, nargout))

    def load_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("load_system", name, nargout))

    def new_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("new_system", name, nargout))

    def add_block(self, lib_path: str, block_path: str, nargout: int = 0) -> None:
        self.calls.append(("add_block", lib_path, block_path, nargout))

    def set_param(self, *args, nargout: int = 0) -> None:
        self.calls.append(("set_param", *args, nargout))

    def add_line(self, *args, nargout: int = 0) -> None:
        self.calls.append(("add_line", *args, nargout))

    def open_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("open_system", name, nargout))

    def save_system(self, *args, nargout: int = 0) -> None:
        self.calls.append(("save_system", *args, nargout))

    def sim(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("sim", name, nargout))


def _load_builder(monkeypatch):
    fake_matlab = types.SimpleNamespace(double=lambda value: ("matlab.double", value))
    monkeypatch.setitem(sys.modules, "matlab", fake_matlab)
    sys.modules.pop("simulink.builder", None)
    return importlib.import_module("simulink.builder")


def test_default_position_tiles_blocks(monkeypatch) -> None:
    builder = _load_builder(monkeypatch)

    assert builder._default_position(0) == DEFAULT_BLOCK_POSITION
    left, top, right, bottom = DEFAULT_BLOCK_POSITION
    assert builder._default_position(4) == (
        left + DEFAULT_HORIZONTAL_SPACING,
        top,
        right + DEFAULT_HORIZONTAL_SPACING,
        bottom,
    )


def test_build_model_creates_blocks_lines_and_simulation(monkeypatch, tmp_path) -> None:
    builder = _load_builder(monkeypatch)
    engine = FakeEngine()
    model_dict = {
        "name": "plain builder model",
        "blocks": {
            "const 1": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "params": {"Value": 5},
            },
            "gain 1": {
                "type": "Gain",
                "lib_path": "simulink/Math Operations/Gain",
                "params": {"Gain": 2},
                "position": [1, 2, 3, 4],
            },
        },
        "connections": [("const 1", 1, "gain 1", 1)],
    }

    result = builder.build_model(
        engine,
        model_dict,
        output_dir=tmp_path,
        open_after_build=True,
        run_simulation=True,
        preload_workspace_variables={"matrix_gain": [[1.0, 0.0]]},
    )

    assert result == {
        "model_name": "plain_builder_model",
        "model_file": str(tmp_path / "plain_builder_model.slx"),
    }
    assert engine.workspace["matrix_gain"] == ("matlab.double", [[1.0, 0.0]])

    add_block_calls = [call for call in engine.calls if call[0] == "add_block"]
    assert add_block_calls == [
        ("add_block", "simulink/Sources/Constant", "plain_builder_model/const_1", 0),
        ("add_block", "simulink/Math Operations/Gain", "plain_builder_model/gain_1", 0),
    ]

    add_line_calls = [call for call in engine.calls if call[0] == "add_line"]
    assert add_line_calls == [
        ("add_line", "plain_builder_model", "const_1/1", "gain_1/1", "autorouting", "on", 0),
    ]

    assert ("open_system", "plain_builder_model", 0) in engine.calls
    assert ("sim", "plain_builder_model", 0) in engine.calls


def test_build_model_handles_scalar_workspace_values_and_skips_optional_actions(monkeypatch, tmp_path) -> None:
    builder = _load_builder(monkeypatch)
    engine = FakeEngine()
    model_dict = {
        "name": "plain builder model",
        "blocks": {
            "const 1": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "params": {"Value": 5},
            },
        },
        "connections": [],
    }

    result = builder.build_model(
        engine,
        model_dict,
        output_dir=tmp_path,
        open_after_build=False,
        run_simulation=False,
        preload_workspace_variables={"scalar_gain": 3.0},
    )

    assert result["model_name"] == "plain_builder_model"
    assert engine.workspace["scalar_gain"] == 3.0
    assert not any(call[0] == "open_system" for call in engine.calls)
    assert not any(call[0] == "sim" for call in engine.calls)
