from __future__ import annotations

import math

import pytest

from latex_frontend.symbols import DeterministicCompileError
from simulate.input_specs import build_input_function, normalize_input_specs


def test_build_input_function_overlays_constants_and_step_specs() -> None:
    input_function = build_input_function(
        base_input_function=lambda _time: {"w": -2.0},
        constant_values={"v": 3.5},
        input_specs={"u": "step"},
        t_span=(0.0, 2.0),
    )

    assert input_function(-0.1) == {"w": -2.0, "v": 3.5, "u": 0.0}
    assert input_function(0.0) == {"w": -2.0, "v": 3.5, "u": 1.0}


def test_build_input_function_supports_structured_sine_and_impulse_specs() -> None:
    input_function = build_input_function(
        input_specs={
            "u": {"kind": "sine", "amplitude": 2.0, "frequency": 0.5, "phase": 0.25, "bias": 1.0},
            "f": {"kind": "impulse", "amplitude": 3.0, "start_time": 1.0, "width": 0.2},
        },
        t_span=(0.0, 5.0),
    )

    assert input_function(0.0)["u"] == pytest.approx(1.0 + 2.0 * math.sin(0.25))
    assert input_function(0.5)["f"] == 0.0
    assert input_function(1.1)["f"] == pytest.approx(15.0)
    assert input_function(1.3)["f"] == 0.0


def test_build_input_function_supports_structured_ramp_pulse_and_saturation_specs() -> None:
    input_function = build_input_function(
        input_specs={
            "r": {"kind": "ramp", "slope": 2.0, "start_time": 1.0, "initial_output": -1.0},
            "p": {"kind": "pulse", "amplitude": 3.0, "start_time": 0.5, "width": 0.25, "period": 10.0},
            "s": {
                "kind": "saturation",
                "input": {"kind": "sine", "amplitude": 2.0, "frequency": 1.0, "phase": 0.0, "bias": 0.0},
                "lower_limit": -0.5,
                "upper_limit": 0.75,
            },
        },
        t_span=(0.0, 5.0),
    )

    assert input_function(0.25)["r"] == -1.0
    assert input_function(2.0)["r"] == pytest.approx(1.0)
    assert input_function(0.4)["p"] == 0.0
    assert input_function(0.6)["p"] == 3.0
    assert input_function(1.0)["p"] == 0.0
    assert input_function(math.pi / 2.0)["s"] == pytest.approx(0.75)
    assert input_function(-math.pi / 2.0)["s"] == pytest.approx(-0.5)


def test_build_input_function_rejects_invalid_specs() -> None:
    with pytest.raises(DeterministicCompileError, match="must be a string keyword or an object"):
        build_input_function(input_specs={"u": 5.0})

    with pytest.raises(DeterministicCompileError, match="Unsupported runtime input spec kind"):
        build_input_function(input_specs={"u": "unknown_wave"})


def test_build_input_function_supports_symbolic_expression_specs() -> None:
    input_function = build_input_function(
        input_specs={"u": {"kind": "expression", "expression": "2*heaviside(t - 1) + sin(t)", "time_variable": "t"}},
        t_span=(0.0, 3.0),
    )

    assert input_function(0.0)["u"] == pytest.approx(0.0)
    assert input_function(1.5)["u"] == pytest.approx(2.0 + math.sin(1.5))


def test_normalize_input_specs_recognizes_simple_heaviside_as_step() -> None:
    normalized = normalize_input_specs(
        input_specs={"u": {"kind": "expression", "expression": "heaviside(t - 1.5)", "time_variable": "t"}},
        t_span=(0.0, 4.0),
    )

    assert normalized["u"] == {"kind": "step", "amplitude": 1.0, "start_time": 1.5, "bias": 0.0}

    input_function = build_input_function(input_specs=normalized, t_span=(0.0, 4.0))
    assert input_function(1.0)["u"] == 0.0
    assert input_function(1.5)["u"] == 1.0


def test_normalize_input_specs_recognizes_multi_step_expression_as_native_sum() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "u": {
                "kind": "expression",
                "expression": "2*heaviside(t - 1) + 3*heaviside(t - 2) - 1",
                "time_variable": "t",
            }
        },
        t_span=(0.0, 5.0),
    )

    assert normalized["u"] == {
        "kind": "sum",
        "terms": [
            {"kind": "constant", "value": -1.0},
            {"kind": "step", "amplitude": 2.0, "start_time": 1.0, "bias": 0.0},
            {"kind": "step", "amplitude": 3.0, "start_time": 2.0, "bias": 0.0},
        ],
    }

    input_function = build_input_function(input_specs=normalized, t_span=(0.0, 5.0))
    assert input_function(0.5)["u"] == -1.0
    assert input_function(1.5)["u"] == 1.0
    assert input_function(2.5)["u"] == 4.0


def test_normalize_input_specs_recognizes_step_difference_as_pulse() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "u": {
                "kind": "expression",
                "expression": "2*heaviside(t - 1) - 2*heaviside(t - 1.4) + 0.5",
                "time_variable": "t",
            }
        },
        t_span=(0.0, 5.0),
    )

    assert normalized["u"]["kind"] == "pulse"
    assert normalized["u"]["amplitude"] == pytest.approx(2.0)
    assert normalized["u"]["start_time"] == pytest.approx(1.0)
    assert normalized["u"]["width"] == pytest.approx(0.4)
    assert normalized["u"]["bias"] == pytest.approx(0.5)

    input_function = build_input_function(input_specs=normalized, t_span=(0.0, 5.0))
    assert input_function(0.5)["u"] == pytest.approx(0.5)
    assert input_function(1.2)["u"] == pytest.approx(2.5)
    assert input_function(1.6)["u"] == pytest.approx(0.5)


def test_normalize_input_specs_recognizes_dirac_expression_as_impulse_sum() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "u": {
                "kind": "expression",
                "expression": "2*dirac(t - 1) - 3*dirac(t - 2)",
                "time_variable": "t",
            }
        },
        t_span=(0.0, 5.0),
    )

    assert normalized["u"]["kind"] == "sum"
    terms = normalized["u"]["terms"]
    assert [term["kind"] for term in terms] == ["impulse", "impulse"]
    assert [term["amplitude"] for term in terms] == pytest.approx([2.0, -3.0])
    assert [term["start_time"] for term in terms] == pytest.approx([1.0, 2.0])


def test_normalize_input_specs_recognizes_ramp_and_saturation_expressions() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "r": {
                "kind": "expression",
                "expression": "3*(t - 2)*heaviside(t - 2) - 1",
                "time_variable": "t",
            },
            "s": {
                "kind": "expression",
                "expression": "min(max(2*sin(t), -0.5), 0.75)",
                "time_variable": "t",
            },
            "c": {
                "kind": "expression",
                "expression": "3*cos(2*t - 0.2) + 1",
                "time_variable": "t",
            },
        },
        t_span=(0.0, 5.0),
    )

    assert normalized["r"] == {
        "kind": "ramp",
        "slope": 3.0,
        "start_time": 2.0,
        "initial_output": -1.0,
    }
    assert normalized["s"] == {
        "kind": "saturation",
        "input": {"kind": "sine", "amplitude": 2.0, "frequency": 1.0, "phase": 0.0, "bias": 0.0},
        "lower_limit": -0.5,
        "upper_limit": 0.75,
    }
    assert normalized["c"]["kind"] == "sine"
    assert normalized["c"]["amplitude"] == pytest.approx(3.0)
    assert normalized["c"]["frequency"] == pytest.approx(2.0)
    assert normalized["c"]["phase"] == pytest.approx((math.pi / 2.0) - 0.2)
    assert normalized["c"]["bias"] == pytest.approx(1.0)


def test_normalize_input_specs_recognizes_periodic_nonsinusoidal_and_random_expressions() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "sq": {"kind": "expression", "expression": "2*sign(sin(3*t - 0.1)) + 1", "time_variable": "t"},
            "sw": {"kind": "expression", "expression": "1.5*sawtooth(4*t)", "time_variable": "t"},
            "tri": {"kind": "expression", "expression": "sawtooth(2*t, 0.5)", "time_variable": "t"},
            "ru": {"kind": "expression", "expression": "rand()", "time_variable": "t"},
            "rn": {"kind": "expression", "expression": "randn()", "time_variable": "t"},
        },
        t_span=(0.0, 5.0),
    )

    assert normalized["sq"] == {
        "kind": "square",
        "amplitude": 2.0,
        "frequency": 3.0,
        "phase": -0.1,
        "bias": 1.0,
    }
    assert normalized["sw"]["kind"] == "sawtooth"
    assert normalized["sw"]["amplitude"] == pytest.approx(1.5)
    assert normalized["tri"]["kind"] == "triangle"
    assert normalized["ru"]["kind"] == "random_number"
    assert normalized["rn"]["kind"] == "white_noise"


def test_build_input_function_supports_product_power_piecewise_dead_zone_and_unary_specs() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "poly": {"kind": "expression", "expression": "(t - 1)^2*heaviside(t - 1)", "time_variable": "t"},
            "mix": {"kind": "expression", "expression": "exp(-2*t)*sin(t)", "time_variable": "t"},
            "pw": {
                "kind": "expression",
                "expression": "piecewise((0, t < 1), (2, t < 2), (3, True))",
                "time_variable": "t",
            },
            "dz": {
                "kind": "expression",
                "expression": "piecewise((0, abs(t) < 1), (t - 1, t > 1), (t + 1, True))",
                "time_variable": "t",
            },
            "ab": {"kind": "expression", "expression": "abs(sin(t))", "time_variable": "t"},
            "sg": {"kind": "expression", "expression": "sign(t - 2)", "time_variable": "t"},
        },
        t_span=(-2.0, 4.0),
    )

    assert normalized["poly"]["kind"] == "product"
    assert normalized["mix"]["kind"] == "product"
    assert normalized["pw"]["kind"] == "piecewise"
    assert normalized["dz"]["kind"] == "dead_zone"
    assert normalized["ab"]["kind"] == "abs"
    assert normalized["sg"]["kind"] == "sign"

    input_function = build_input_function(input_specs=normalized, t_span=(-2.0, 4.0))
    assert input_function(0.5)["poly"] == pytest.approx(0.0)
    assert input_function(3.0)["poly"] == pytest.approx(4.0)
    assert input_function(1.0)["mix"] == pytest.approx(math.exp(-2.0) * math.sin(1.0))
    assert input_function(0.5)["pw"] == pytest.approx(0.0)
    assert input_function(1.5)["pw"] == pytest.approx(2.0)
    assert input_function(3.0)["pw"] == pytest.approx(3.0)
    assert input_function(0.25)["dz"] == pytest.approx(0.0)
    assert input_function(1.5)["dz"] == pytest.approx(0.5)
    assert input_function(-1.5)["dz"] == pytest.approx(-0.5)
    assert input_function(math.pi / 2.0)["ab"] == pytest.approx(1.0)
    assert input_function(1.0)["sg"] == pytest.approx(-1.0)
    assert input_function(2.0)["sg"] == pytest.approx(0.0)
    assert input_function(3.0)["sg"] == pytest.approx(1.0)


def test_normalize_input_specs_recognizes_native_trig_math_and_minmax_expression_trees() -> None:
    normalized = normalize_input_specs(
        input_specs={
            "at": {"kind": "expression", "expression": "atan(t)", "time_variable": "t"},
            "sc": {"kind": "expression", "expression": "sec(t)", "time_variable": "t"},
            "lg": {"kind": "expression", "expression": "log(t + 2)", "time_variable": "t"},
            "a2": {"kind": "expression", "expression": "atan2(t, t + 1)", "time_variable": "t"},
            "mm": {"kind": "expression", "expression": "max(sin(t), t - 1)", "time_variable": "t"},
        },
        t_span=(0.0, 4.0),
    )

    assert normalized["at"] == {"kind": "trig_function", "operator": "atan", "input": {"kind": "time"}}
    assert normalized["sc"] == {"kind": "reciprocal_trig_function", "operator": "sec", "input": {"kind": "time"}}
    assert normalized["lg"]["kind"] == "math_function"
    assert normalized["lg"]["operator"] == "log"
    assert normalized["a2"]["kind"] == "binary_trig_function"
    assert normalized["a2"]["operator"] == "atan2"
    assert normalized["mm"]["kind"] == "minmax"
    assert normalized["mm"]["operator"] == "max"

    input_function = build_input_function(input_specs=normalized, t_span=(0.0, 4.0))
    assert input_function(1.0)["at"] == pytest.approx(math.atan(1.0))
    assert input_function(1.0)["sc"] == pytest.approx(1.0 / math.cos(1.0))
    assert input_function(1.0)["lg"] == pytest.approx(math.log(3.0))
    assert input_function(1.0)["a2"] == pytest.approx(math.atan2(1.0, 2.0))
    assert input_function(0.0)["mm"] == pytest.approx(0.0)
