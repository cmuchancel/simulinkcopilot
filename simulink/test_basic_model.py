"""Minimal end-to-end Simulink model creation smoke test."""

from __future__ import annotations


import pytest

from repo_paths import GENERATED_MODELS_ROOT
from simulink.constants import CONSTANT_BLOCK, GAIN_BLOCK, SCOPE_BLOCK
from simulink.engine import start_engine
from simulink.utils import ensure_output_dir, format_position

pytestmark = [pytest.mark.matlab, pytest.mark.slow]


def test_basic_model_smoke() -> None:
    eng = start_engine(retries=3, retry_delay_seconds=3.0)
    output_dir = ensure_output_dir(GENERATED_MODELS_ROOT)
    model_name = "basic_python_simulink_model"
    model_file = output_dir / f"{model_name}.slx"

    try:
        eng.load_system("simulink", nargout=0)
        eng.eval(
            f"if bdIsLoaded('{model_name}'), close_system('{model_name}', 0); end",
            nargout=0,
        )

        eng.new_system(model_name, nargout=0)
        eng.open_system(model_name, nargout=0)

        eng.add_block(CONSTANT_BLOCK, f"{model_name}/const1", nargout=0)
        eng.set_param(f"{model_name}/const1", "Value", "1", nargout=0)
        eng.set_param(f"{model_name}/const1", "Position", format_position([40, 50, 90, 80]), nargout=0)

        eng.add_block(GAIN_BLOCK, f"{model_name}/gain1", nargout=0)
        eng.set_param(f"{model_name}/gain1", "Gain", "2", nargout=0)
        eng.set_param(f"{model_name}/gain1", "Position", format_position([180, 45, 260, 85]), nargout=0)

        eng.add_block(SCOPE_BLOCK, f"{model_name}/scope1", nargout=0)
        eng.set_param(f"{model_name}/scope1", "Position", format_position([340, 40, 390, 90]), nargout=0)

        eng.add_line(model_name, "const1/1", "gain1/1", "autorouting", "on", nargout=0)
        eng.add_line(model_name, "gain1/1", "scope1/1", "autorouting", "on", nargout=0)

        eng.set_param(model_name, "SimulationCommand", "update", nargout=0)
        eng.save_system(model_name, str(model_file), nargout=0)
        eng.sim(model_name, nargout=0)
        assert model_file.exists(), f"Expected {model_file} to exist after build."
    finally:
        eng.quit()
