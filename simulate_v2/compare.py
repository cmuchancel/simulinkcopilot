"""Comparison metrics for ODE and state-space trajectories."""

from __future__ import annotations

import numpy as np


DEFAULT_TOLERANCE = 1e-6


def compare_simulations(
    direct_result: dict[str, object],
    state_space_result: dict[str, object],
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, object]:
    """Compute RMSE and max absolute error between two simulations."""
    direct_time = np.asarray(direct_result["t"], dtype=float)
    direct_states = np.asarray(direct_result["states"], dtype=float)
    ss_time = np.asarray(state_space_result["t"], dtype=float)
    ss_states = np.asarray(state_space_result["states"], dtype=float)
    state_names = list(direct_result["state_names"])  # type: ignore[index]

    if direct_states.shape[1] != ss_states.shape[1]:
        raise ValueError("State dimension mismatch between simulation results.")

    if np.array_equal(direct_time, ss_time):
        aligned_ss = ss_states
    else:
        aligned_ss = np.column_stack(
            [np.interp(direct_time, ss_time, ss_states[:, column]) for column in range(ss_states.shape[1])]
        )

    error = direct_states - aligned_ss
    rmse = float(np.sqrt(np.mean(error**2)))
    max_abs_error = float(np.max(np.abs(error)))
    per_state_rmse = {
        state_names[index]: float(np.sqrt(np.mean(error[:, index] ** 2)))
        for index in range(len(state_names))
    }
    per_state_max = {
        state_names[index]: float(np.max(np.abs(error[:, index])))
        for index in range(len(state_names))
    }

    return {
        "rmse": rmse,
        "max_abs_error": max_abs_error,
        "per_state_rmse": per_state_rmse,
        "per_state_max_abs_error": per_state_max,
        "tolerance": tolerance,
        "passes": rmse < tolerance and max_abs_error < tolerance,
    }
