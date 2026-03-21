from __future__ import annotations

import numpy as np
import pytest

from backend.extract_signals import _to_numpy, extract_simulink_signals
from latex_frontend.symbols import DeterministicCompileError


class FakeExtractEngine:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.workspace: dict[str, object] = {}

    def eval(self, expression: str, nargout: int = 1):
        return self.responses[expression]


def test_to_numpy_converts_sequences() -> None:
    array = _to_numpy([1, 2, 3])
    assert isinstance(array, np.ndarray)
    assert array.dtype == float
    assert array.tolist() == [1.0, 2.0, 3.0]


def test_extract_simulink_signals_returns_time_state_matrix_and_map() -> None:
    responses = {
        "numel(simOutPy.yout.signals)": 2,
        "simOutPy.yout.time": [0.0, 1.0, 2.0],
        "simOutPy.yout.signals(1).values": [1.0, 2.0, 3.0],
        "simOutPy.yout.signals(2).values": [4.0, 5.0, 6.0],
    }
    engine = FakeExtractEngine(responses)

    result = extract_simulink_signals(engine, object(), output_names=["x", "x_dot"])

    assert result["state_names"] == ["x", "x_dot"]
    assert result["t"].tolist() == [0.0, 1.0, 2.0]
    assert result["states"].tolist() == [[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]]
    assert result["signals"]["x"].tolist() == [1.0, 2.0, 3.0]
    assert engine.workspace["simOutPy"] is not None


def test_extract_simulink_signals_rejects_unexpected_signal_count() -> None:
    engine = FakeExtractEngine({"numel(simOutPy.yout.signals)": 1})

    with pytest.raises(DeterministicCompileError, match="Expected 2 Simulink outputs, found 1"):
        extract_simulink_signals(engine, object(), output_names=["x", "x_dot"])


def test_extract_simulink_signals_rejects_empty_time_vector() -> None:
    engine = FakeExtractEngine(
        {
            "numel(simOutPy.yout.signals)": 1,
            "simOutPy.yout.time": [],
        }
    )

    with pytest.raises(DeterministicCompileError, match="empty time vector"):
        extract_simulink_signals(engine, object(), output_names=["x"])


def test_extract_simulink_signals_rejects_signal_length_mismatch() -> None:
    engine = FakeExtractEngine(
        {
            "numel(simOutPy.yout.signals)": 1,
            "simOutPy.yout.time": [0.0, 1.0],
            "simOutPy.yout.signals(1).values": [1.0],
        }
    )

    with pytest.raises(DeterministicCompileError, match="has 1 samples but time has 2"):
        extract_simulink_signals(engine, object(), output_names=["x"])
