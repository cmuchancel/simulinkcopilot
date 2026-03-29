from __future__ import annotations

import importlib
import sys
import types

from backend.simulink_dict import SUBSYSTEM_BLOCK


class FakeEngine:
    def __init__(self) -> None:
        self.workspace: dict[str, object] = {}
        self.calls: list[tuple[object, ...]] = []
        self._line_counter = 0

    def eval(self, expression: str, nargout: int = 0):
        self.calls.append(("eval", expression, nargout))
        return None

    def load_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("load_system", name, nargout))

    def new_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("new_system", name, nargout))

    def add_block(self, lib_path: str, block_path: str, nargout: int = 0) -> None:
        self.calls.append(("add_block", lib_path, block_path, nargout))

    def set_param(self, *args, nargout: int = 0) -> None:
        self.calls.append(("set_param", *args, nargout))

    def add_line(self, *args, nargout: int = 0):
        self._line_counter += 1
        handle = f"line_{self._line_counter}"
        self.calls.append(("add_line", *args, nargout, handle))
        return handle if nargout == 1 else None

    def open_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("open_system", name, nargout))

    def save_system(self, *args, nargout: int = 0) -> None:
        self.calls.append(("save_system", *args, nargout))

    def get_param(self, path: str, name: str, nargout: int = 0):
        self.calls.append(("get_param", path, name, nargout))
        return 1


def _load_backend_builder(monkeypatch):
    fake_matlab = types.ModuleType("matlab")
    fake_matlab.double = lambda value: ("matlab.double", value)
    fake_matlab_engine = types.ModuleType("matlab.engine")
    fake_matlab.engine = fake_matlab_engine
    monkeypatch.setitem(sys.modules, "matlab", fake_matlab)
    monkeypatch.setitem(sys.modules, "matlab.engine", fake_matlab_engine)
    simulink_engine = importlib.import_module("simulink.engine")
    monkeypatch.setattr(simulink_engine, "_MATLAB_MODULE", fake_matlab, raising=False)
    sys.modules.pop("backend.builder", None)
    return importlib.import_module("backend.builder")


def _hierarchical_model_dict(subsystem_block: str) -> dict[str, object]:
    return {
        "name": "Readable Backend Model",
        "blocks": {
            "subsystem": {
                "type": "Subsystem",
                "lib_path": subsystem_block,
                "system": "root",
                "name": "subsystem stage",
            },
            "in1": {
                "type": "Inport",
                "lib_path": "simulink/Ports & Subsystems/In1",
                "system": "subsystem",
                "params": {"Port": 1},
                "name": "u in",
            },
            "out1": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "subsystem",
                "params": {"Port": 1},
                "name": "y out",
            },
            "gain": {
                "type": "Gain",
                "lib_path": "simulink/Math Operations/Gain",
                "system": "subsystem",
                "params": {"Gain": 2.5},
                "position": [10, 20, 30, 40],
                "name": "gain block",
            },
        },
        "connections": [
            {
                "system": "subsystem",
                "src_block": "in1",
                "src_port": 1,
                "dst_block": "gain",
                "dst_port": 1,
                "label": "u_signal",
            },
            {
                "system": "subsystem",
                "src_block": "gain",
                "src_port": 1,
                "dst_block": "out1",
                "dst_port": 1,
            },
        ],
        "outputs": [{"name": "y", "block": "out1", "port": "1"}],
        "model_params": {"StopTime": "5.0"},
        "workspace_variables": {"matrix_gain": [[1.0, 2.0]], "bias": 3.0},
        "metadata": {"kind": "demo"},
    }


def test_backend_builder_helper_paths(monkeypatch) -> None:
    builder = _load_backend_builder(monkeypatch)
    blocks = _hierarchical_model_dict(SUBSYSTEM_BLOCK)["blocks"]

    assert builder._block_depth("subsystem", blocks) == 0
    assert builder._block_depth("gain", blocks) == 1
    assert builder._full_block_path("demo_model", "gain", blocks) == "demo_model/subsystem_stage/gain_block"
    assert builder._system_path("demo_model", builder.ROOT_SYSTEM, blocks) == "demo_model"
    assert builder._system_path("demo_model", "subsystem", blocks) == "demo_model/subsystem_stage"
    assert builder._port_sort_key(blocks["in1"]) < builder._port_sort_key(blocks["out1"])


def test_build_simulink_model_builds_hierarchy_and_assigns_workspace(monkeypatch, tmp_path) -> None:
    builder = _load_backend_builder(monkeypatch)
    engine = FakeEngine()
    model_dict = _hierarchical_model_dict(SUBSYSTEM_BLOCK)

    result = builder.build_simulink_model(
        engine,
        model_dict,
        output_dir=tmp_path,
        open_after_build=True,
    )

    assert result["model_name"] == "Readable_Backend_Model"
    assert result["model_file"] == str(tmp_path / "Readable_Backend_Model.slx")
    assert result["outputs"] == [{"name": "y", "block": "out1", "port": "1"}]
    assert result["model_params"] == {"StopTime": "5.0"}
    assert result["metadata"] == {"kind": "demo"}

    add_block_paths = [call[2] for call in engine.calls if call[0] == "add_block"]
    assert add_block_paths == [
        "Readable_Backend_Model/subsystem_stage",
        "Readable_Backend_Model/subsystem_stage/u_in",
        "Readable_Backend_Model/subsystem_stage/y_out",
        "Readable_Backend_Model/subsystem_stage/gain_block",
    ]

    assert engine.workspace["matrix_gain"] == ("matlab.double", [[1.0, 2.0]])
    assert engine.workspace["bias"] == 3.0

    line_label_calls = [
        call
        for call in engine.calls
        if call[0] == "set_param" and call[2] == "Name" and call[3] == "u_signal"
    ]
    assert line_label_calls

    opened = [call for call in engine.calls if call[0] == "open_system"]
    assert opened == [("open_system", "Readable_Backend_Model", 0)]

    saved = [call for call in engine.calls if call[0] == "save_system"]
    assert saved

    handles = [call for call in engine.calls if call[0] == "get_param" and call[2] == "Handle"]
    assert len(handles) == 4


def test_build_simulink_model_skips_optional_open(monkeypatch, tmp_path) -> None:
    builder = _load_backend_builder(monkeypatch)
    engine = FakeEngine()

    builder.build_simulink_model(
        engine,
        _hierarchical_model_dict(SUBSYSTEM_BLOCK),
        output_dir=tmp_path,
        open_after_build=False,
    )

    assert not any(call[0] == "open_system" for call in engine.calls)


def test_build_simulink_model_configures_matlab_function_block(monkeypatch, tmp_path) -> None:
    builder = _load_backend_builder(monkeypatch)
    engine = FakeEngine()
    model_dict = {
        "name": "Function Block Model",
        "blocks": {
            "mf": {
                "type": "MATLABFunction",
                "lib_path": "simulink/User-Defined Functions/MATLAB Function",
                "system": "root",
                "name": "u",
                "metadata": {
                    "matlab_function_script": "function y = fcn(t)\ny = atan(t);\n",
                },
            },
            "out": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "root",
                "name": "out_u",
                "params": {"Port": 1},
            },
        },
        "connections": [
            {"system": "root", "src_block": "mf", "src_port": 1, "dst_block": "out", "dst_port": 1, "label": "u"}
        ],
        "outputs": [{"name": "u", "block": "out", "port": "1"}],
    }

    builder.build_simulink_model(engine, model_dict, output_dir=tmp_path, open_after_build=False)

    assert engine.workspace["simucopilot_block_path_tmp"] == "Function_Block_Model/u"
    assert "atan(t)" in engine.workspace["simucopilot_block_script_tmp"]
    assert any(
        call[0] == "eval" and "Stateflow.EMChart" in str(call[1])
        for call in engine.calls
    )
