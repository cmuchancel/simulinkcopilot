"""Deterministic input-source resolution for simulation and Simulink lowering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from simulate.ode_sim import InputFunction


InputSignalSeries = dict[str, dict[str, list[float]]]


@dataclass(frozen=True)
class ResolvedInputSources:
    """Concrete backend input representation for a set of named inputs."""

    constant_values: dict[str, float] | None
    signal_samples: InputSignalSeries | None


def sample_input_signals(
    input_function: InputFunction,
    input_names: Sequence[str],
    t_eval,
) -> InputSignalSeries:
    """Sample deterministic input signals on the provided evaluation grid."""
    time_grid = np.asarray(t_eval, dtype=float)
    return {
        name: {
            "time": [float(time_value) for time_value in time_grid.tolist()],
            "values": [float(input_function(float(time_value)).get(name, 0.0)) for time_value in time_grid],
        }
        for name in input_names
    }


def detect_constant_input_values(
    input_function: InputFunction,
    input_names: Sequence[str],
    *,
    t_span: tuple[float, float],
    tolerance: float = 1e-12,
) -> dict[str, float] | None:
    """Return a constant input vector when the named inputs are time-invariant."""
    if not input_names:
        return {}

    start, stop = t_span
    sample_times = [float(start), float((start + stop) / 2.0), float(stop)]
    baseline = {
        name: float(input_function(sample_times[0]).get(name, 0.0))
        for name in input_names
    }
    for time_value in sample_times[1:]:
        sample = {
            name: float(input_function(time_value).get(name, 0.0))
            for name in input_names
        }
        if any(abs(sample[name] - baseline[name]) > tolerance for name in input_names):
            return None
    return baseline


def resolve_input_sources(
    input_function: InputFunction,
    input_names: Sequence[str],
    *,
    t_span: tuple[float, float],
    t_eval,
    tolerance: float = 1e-12,
) -> ResolvedInputSources:
    """Resolve named inputs to either constants or sampled signals."""
    constant_values = detect_constant_input_values(
        input_function,
        input_names,
        t_span=t_span,
        tolerance=tolerance,
    )
    if constant_values is not None:
        return ResolvedInputSources(constant_values=constant_values, signal_samples=None)
    return ResolvedInputSources(
        constant_values=None,
        signal_samples=sample_input_signals(input_function, input_names, t_eval),
    )
