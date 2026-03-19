"""Validation helpers for Simulink-vs-Python simulation comparisons."""

from __future__ import annotations

from simulate_v2.compare import compare_simulations


def compare_simulink_results(
    simulink_result: dict[str, object],
    ode_result: dict[str, object],
    state_space_result: dict[str, object] | None = None,
    *,
    tolerance: float,
) -> dict[str, object]:
    """Compare Simulink trajectories against Python reference simulations."""
    vs_ode = compare_simulations(ode_result, simulink_result, tolerance=tolerance)
    vs_state_space = (
        compare_simulations(state_space_result, simulink_result, tolerance=tolerance)
        if state_space_result is not None
        else None
    )
    overall_pass = vs_ode["passes"] and (vs_state_space["passes"] if vs_state_space is not None else True)
    return {
        "vs_ode": vs_ode,
        "vs_state_space": vs_state_space,
        "passes": overall_pass,
    }
