from __future__ import annotations

import numpy as np

from simulate.input_sources import (
    detect_constant_input_values,
    resolve_input_sources,
    sample_input_signals,
)


def test_detect_constant_input_values_handles_multi_input_vectors() -> None:
    input_function = lambda _t: {"u_1": 2.0, "u_2": -1.5}

    assert detect_constant_input_values(input_function, ["u_1", "u_2"], t_span=(0.0, 3.0)) == {
        "u_1": 2.0,
        "u_2": -1.5,
    }


def test_detect_constant_input_values_rejects_varying_multi_input_vectors() -> None:
    input_function = lambda t: {"u_1": t, "u_2": 1.0 - t}

    assert detect_constant_input_values(input_function, ["u_1", "u_2"], t_span=(0.0, 3.0)) is None


def test_sample_and_resolve_input_sources_preserve_multi_input_order() -> None:
    input_function = lambda t: {"u_1": t, "u_2": 2.0 * t}
    t_eval = np.array([0.0, 0.5, 1.0], dtype=float)

    samples = sample_input_signals(input_function, ["u_1", "u_2"], t_eval)
    assert samples == {
        "u_1": {"time": [0.0, 0.5, 1.0], "values": [0.0, 0.5, 1.0]},
        "u_2": {"time": [0.0, 0.5, 1.0], "values": [0.0, 1.0, 2.0]},
    }

    resolved = resolve_input_sources(
        input_function,
        ["u_1", "u_2"],
        t_span=(0.0, 1.0),
        t_eval=t_eval,
    )
    assert resolved.constant_values is None
    assert resolved.signal_samples == samples
