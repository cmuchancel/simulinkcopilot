from __future__ import annotations

from pathlib import Path

from backend import matlab_layout_renderer as renderer_module
from backend.simulink_dict import SUBSYSTEM_BLOCK, validate_simulink_model_dict


class _FakeMatlabEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def open_system(self, name: str, nargout: int = 0) -> None:
        self.calls.append(("open_system", name, nargout))

    def eval(self, expression: str, nargout: int = 0) -> None:
        self.calls.append(("eval", expression, nargout))

    def close_system(self, name: str, flag: int, nargout: int = 0) -> None:
        self.calls.append(("close_system", name, flag, nargout))


def _demo_model() -> dict[str, object]:
    return {
        "name": "matlab_render_demo",
        "blocks": {
            "subsystem": {
                "type": "Subsystem",
                "lib_path": SUBSYSTEM_BLOCK,
                "system": "root",
                "name": "dynamics",
                "position": [560, 40, 780, 180],
                "metadata": {"layout_role": "subsystem", "inport_count": 1, "outport_count": 1},
            },
            "src": {
                "type": "Constant",
                "lib_path": "simulink/Sources/Constant",
                "system": "root",
                "name": "u",
                "position": [40, 90, 150, 130],
                "params": {"Value": "1"},
                "metadata": {"layout_role": "source", "trace_expression": "u"},
            },
            "out": {
                "type": "Outport",
                "lib_path": "simulink/Ports & Subsystems/Out1",
                "system": "root",
                "name": "y",
                "position": [860, 90, 970, 130],
                "params": {"Port": 1},
                "metadata": {"layout_role": "output", "trace_expression": "y"},
            },
        },
        "connections": [
            {"system": "root", "src_block": "src", "src_port": "1", "dst_block": "subsystem", "dst_port": "1", "label": "u"},
            {"system": "root", "src_block": "subsystem", "src_port": "1", "dst_block": "out", "dst_port": "1", "label": "y"},
        ],
        "outputs": [{"name": "y", "block": "out", "port": "1"}],
    }


def test_export_simulink_system_image_emits_expected_matlab_commands(tmp_path: Path) -> None:
    engine = _FakeMatlabEngine()

    rendered = renderer_module.export_simulink_system_image(
        engine,
        system_path="demo'model/sub'system",
        output_path=tmp_path / "subsystem.png",
    )

    assert rendered == str((tmp_path / "subsystem.png").resolve())
    assert engine.calls[0] == ("open_system", "demo'model/sub'system", 0)
    assert "ZoomFactor" in engine.calls[2][1]
    assert "print('-sdemo''model/sub''system'" in engine.calls[4][1]


def test_render_backend_model_with_matlab_uses_root_and_subsystem_paths(monkeypatch, tmp_path: Path) -> None:
    model = validate_simulink_model_dict(_demo_model())
    engine = _FakeMatlabEngine()

    def fake_build_simulink_model(eng, normalized_model, *, output_dir, open_after_build=False):
        assert eng is engine
        assert normalized_model == model
        return {
            "model_name": "demo_model",
            "model_file": str(Path(output_dir) / "demo_model.slx"),
            "outputs": normalized_model["outputs"],
            "model_params": normalized_model.get("model_params", {}),
            "metadata": normalized_model.get("metadata", {}),
        }

    monkeypatch.setattr(renderer_module, "build_simulink_model", fake_build_simulink_model)

    rendered = renderer_module.render_backend_model_with_matlab(
        engine,
        model,
        output_dir=tmp_path,
    )

    assert rendered.model_name == "demo_model"
    assert set(rendered.renders) == {"root", "subsystem"}
    open_calls = [call for call in engine.calls if call[0] == "open_system"]
    assert open_calls[0][1] == "demo_model"
    assert open_calls[1][1] == "demo_model/dynamics"
    assert ("close_system", "demo_model", 0, 0) in engine.calls


def test_build_block_path_names_disambiguates_duplicate_sibling_names() -> None:
    blocks = {
        "first": {"name": "gain_y", "system": "root"},
        "second": {"name": "gain_y", "system": "root"},
        "third": {"name": "gain_y", "system": "subsystem"},
        "subsystem": {"name": "dyn", "system": "root"},
    }

    names = renderer_module._build_block_path_names(blocks)

    assert names["first"] == "gain_y"
    assert names["second"] == "gain_y__2"
    assert names["third"] == "gain_y"
