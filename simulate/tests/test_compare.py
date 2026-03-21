from __future__ import annotations

import pytest

from simulate.compare import compare_simulations


def test_compare_simulations_interpolates_and_reports_per_state_metrics() -> None:
    direct = {
        "t": [0.0, 0.5, 1.0],
        "states": [[0.0, 0.0], [1.0, 2.0], [2.0, 4.0]],
        "state_names": ["x", "x_dot"],
    }
    state_space = {
        "t": [0.0, 1.0],
        "states": [[0.0, 0.0], [2.0, 4.0]],
        "state_names": ["x", "x_dot"],
    }

    result = compare_simulations(direct, state_space, tolerance=1e-9)

    assert result["rmse"] == 0.0
    assert result["max_abs_error"] == 0.0
    assert result["per_state_rmse"] == {"x": 0.0, "x_dot": 0.0}
    assert result["passes"] is True


def test_compare_simulations_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="State dimension mismatch"):
        compare_simulations(
            {"t": [0.0], "states": [[1.0]], "state_names": ["x"]},
            {"t": [0.0], "states": [[1.0, 2.0]], "state_names": ["x", "x_dot"]},
        )
