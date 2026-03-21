from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-matlab",
        action="store_true",
        default=False,
        help="Run MATLAB/Simulink-backed tests.",
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slower integration tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "matlab: requires a local MATLAB/Simulink engine")
    config.addinivalue_line("markers", "slow: longer-running integration coverage")
    config.addinivalue_line("markers", "property: property-based randomized tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_matlab = config.getoption("--run-matlab") or os.getenv("SIMULINKCOPILOT_RUN_MATLAB_TESTS") == "1"
    run_slow = (
        config.getoption("--run-slow")
        or run_matlab
        or os.getenv("SIMULINKCOPILOT_RUN_SLOW_TESTS") == "1"
    )

    skip_matlab = pytest.mark.skip(
        reason="requires --run-matlab or SIMULINKCOPILOT_RUN_MATLAB_TESTS=1"
    )
    skip_slow = pytest.mark.skip(
        reason="requires --run-slow or SIMULINKCOPILOT_RUN_SLOW_TESTS=1"
    )

    for item in items:
        if "matlab" in item.keywords and not run_matlab:
            item.add_marker(skip_matlab)
            continue
        if "slow" in item.keywords and not run_slow:
            item.add_marker(skip_slow)
