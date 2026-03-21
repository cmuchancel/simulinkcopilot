from __future__ import annotations

from unittest import mock

from backend.validate_simulink import compare_simulink_results


def test_compare_simulink_results_only_checks_ode_when_state_space_absent() -> None:
    with mock.patch("backend.validate_simulink.compare_simulations", return_value={"passes": True, "rmse": 0.0}):
        result = compare_simulink_results({"t": []}, {"t": []}, tolerance=1e-6)

    assert result == {
        "vs_ode": {"passes": True, "rmse": 0.0},
        "vs_state_space": None,
        "passes": True,
    }


def test_compare_simulink_results_requires_both_comparisons_to_pass() -> None:
    with mock.patch(
        "backend.validate_simulink.compare_simulations",
        side_effect=[
            {"passes": True, "rmse": 0.0},
            {"passes": False, "rmse": 0.2},
        ],
    ):
        result = compare_simulink_results({"t": []}, {"t": []}, {"t": []}, tolerance=1e-6)

    assert result["vs_ode"]["passes"] is True
    assert result["vs_state_space"]["passes"] is False
    assert result["passes"] is False
