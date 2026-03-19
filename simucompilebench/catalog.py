"""Benchmark catalog and dataset writer for SimuCompileBench."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from simulate.synthetic_benchmark import (
    DEFAULT_SYNTHETIC_SEED,
    DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    SyntheticSystemSpec,
    generate_synthetic_systems,
)

from .models import BenchmarkSystemSpec


def _state_names(count: int, prefix: str = "x") -> list[str]:
    return [f"{prefix}_{index}" for index in range(1, count + 1)]


def _join_terms(terms: list[str]) -> str:
    if not terms:
        return "0"
    joined = " + ".join(terms)
    return joined.replace("+ -", "- ")


def _derivative_latex(symbol: str, order: int) -> str:
    if order <= 0:
        return symbol
    if order == 1:
        return rf"\dot{{{symbol}}}"
    if order == 2:
        return rf"\ddot{{{symbol}}}"
    return rf"\frac{{d^{order} {symbol}}}{{dt^{order}}}"


def _symbol_config(parameter_names: list[str], *, include_input: bool = False) -> dict[str, str]:
    config = {name: "parameter" for name in parameter_names}
    if include_input:
        config["u"] = "input"
    return config


def _scaled_initial_conditions(states: list[str], *, include_velocity_for: set[str] | None = None) -> dict[str, float]:
    initial_conditions: dict[str, float] = {}
    include_velocity_for = include_velocity_for or set()
    for index, state in enumerate(states, start=1):
        initial_conditions[state] = round(0.02 * ((index % 4) - 1.5), 6)
        if state in include_velocity_for:
            initial_conditions[f"{state}_dot"] = round(0.015 * (index % 3), 6)
    return initial_conditions


def _legacy_spec(item: SyntheticSystemSpec) -> BenchmarkSystemSpec:
    return BenchmarkSystemSpec(
        system_id=item.system_id,
        tier="tier1_verified",
        family=f"legacy::{item.family}",
        latex=item.latex,
        generated_state_count=item.generated_state_count,
        max_order=item.max_order,
        depth=item.depth,
        includes_trig=item.includes_trig,
        nonlinear=item.nonlinear,
        parameter_values=dict(item.parameter_values),
        initial_conditions=dict(item.initial_conditions),
        input_values=dict(item.input_values),
        symbol_config=dict(item.symbol_config),
        classification_mode="configured",
        t_span=item.t_span,
        sample_count=item.sample_count,
        tags=("legacy", "synthetic", item.family),
        simulink_expected=True,
        metadata={
            "expected_behavior": "pass",
            "source": "simulate.synthetic_benchmark",
        },
    )


def legacy_tier_specs(
    *,
    count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    seed: int = DEFAULT_SYNTHETIC_SEED,
) -> list[BenchmarkSystemSpec]:
    """Return the locked legacy synthetic benchmark as tier 1."""
    return [_legacy_spec(item) for item in generate_synthetic_systems(count=count, seed=seed)]


def _dense_linear_spec(count: int, *, include_input: bool) -> BenchmarkSystemSpec:
    states = _state_names(count)
    equations: list[str] = []
    for index, state in enumerate(states):
        terms = [f"-a*{state}"]
        if index > 0:
            terms.append(f"(2/9)*b*{states[index - 1]}")
        if index + 1 < len(states):
            terms.append(f"(1/6)*c*{states[index + 1]}")
        if index > 1:
            terms.append(f"(1/18)*k*{states[index - 2]}")
        if index + 2 < len(states):
            terms.append(f"(1/20)*m*{states[index + 2]}")
        if include_input and index % 3 == 0:
            terms.append("(1/8)*u")
        equations.append(rf"\dot{{{state}}}={_join_terms(terms)}")

    system_id = f"struct_dense_linear_{count}" + ("_input" if include_input else "")
    return BenchmarkSystemSpec(
        system_id=system_id,
        tier="tier2_structural",
        family="scaled_dense_linear",
        latex="\n".join(equations),
        generated_state_count=count,
        max_order=1,
        depth=4,
        includes_trig=False,
        nonlinear=False,
        parameter_values={"a": 0.55, "b": 0.35, "c": 0.28, "k": 0.16, "m": 0.12},
        initial_conditions=_scaled_initial_conditions(states),
        input_values={"u": 0.1} if include_input else {},
        symbol_config=_symbol_config(["a", "b", "c", "k", "m"], include_input=include_input),
        t_span=(0.0, 4.0),
        sample_count=180,
        tags=("structural", "linear", "high_state", "coupled") + (("input",) if include_input else ()),
        metadata={
            "expected_behavior": "pass",
            "state_count_target": count,
            "supports_state_space": True,
        },
    )


def _dense_nonlinear_spec(count: int) -> BenchmarkSystemSpec:
    states = _state_names(count)
    equations: list[str] = []
    for index, state in enumerate(states):
        nxt = states[(index + 1) % len(states)]
        nxt2 = states[(index + 2) % len(states)]
        terms = [
            f"-a*{state}",
            rf"(1/12)*\sin({state}+{nxt})",
            rf"(1/15)*\cos({nxt}-{nxt2})",
            f"(1/90)*(({state}+{nxt})^2)",
        ]
        if index % 4 == 0:
            terms.append("(1/14)*u")
        equations.append(rf"\dot{{{state}}}={_join_terms(terms)}")

    return BenchmarkSystemSpec(
        system_id=f"struct_dense_nonlinear_{count}",
        tier="tier2_structural",
        family="scaled_dense_nonlinear",
        latex="\n".join(equations),
        generated_state_count=count,
        max_order=1,
        depth=5,
        includes_trig=True,
        nonlinear=True,
        parameter_values={"a": 0.4},
        initial_conditions=_scaled_initial_conditions(states),
        input_values={"u": 0.08},
        symbol_config=_symbol_config(["a"], include_input=True),
        t_span=(0.0, 2.5),
        sample_count=160,
        tags=("structural", "nonlinear", "trig", "high_state", "coupled", "input"),
        metadata={
            "expected_behavior": "pass",
            "state_count_target": count,
            "supports_state_space": False,
        },
    )


def _mixed_order_spec(count: int) -> BenchmarkSystemSpec:
    states = _state_names(count)
    equations = [
        rf"\ddot{{{states[0]}}}="
        + _join_terms(
            [
                f"-a*{_derivative_latex(states[0], 1)}",
                f"-b*{states[0]}",
                f"(1/10)*{states[1]}",
                rf"(1/20)*\sin({states[1]}-{states[2]})",
                "(1/18)*u",
            ]
        )
    ]
    for index, state in enumerate(states[1:], start=1):
        neighbor = states[index - 1]
        tail = states[(index + 1) % len(states)]
        equations.append(
            rf"\dot{{{state}}}="
            + _join_terms(
                [
                    f"-c*{state}",
                    f"(1/12)*{neighbor}",
                    f"-(1/16)*{tail}",
                    f"(1/140)*(({state}+{neighbor})^2)",
                ]
            )
        )

    initial_conditions = _scaled_initial_conditions(states, include_velocity_for={states[0]})
    return BenchmarkSystemSpec(
        system_id=f"struct_mixed_order_{count}",
        tier="tier2_structural",
        family="scaled_mixed_order",
        latex="\n".join(equations),
        generated_state_count=count,
        max_order=2,
        depth=5,
        includes_trig=True,
        nonlinear=True,
        parameter_values={"a": 0.6, "b": 0.8, "c": 0.5},
        initial_conditions=initial_conditions,
        input_values={"u": 0.05},
        symbol_config=_symbol_config(["a", "b", "c"], include_input=True),
        t_span=(0.0, 2.5),
        sample_count=150,
        tags=("structural", "mixed_order", "nonlinear", "high_state", "input"),
        metadata={
            "expected_behavior": "pass",
            "state_count_target": count,
            "supports_state_space": False,
        },
    )


def high_state_structural_specs() -> list[BenchmarkSystemSpec]:
    """New large-state structural systems added beyond the legacy distribution."""
    specs: list[BenchmarkSystemSpec] = []
    for count in (8, 10, 12):
        specs.append(_dense_linear_spec(count, include_input=False))
        specs.append(_dense_linear_spec(count, include_input=True))
        specs.append(_mixed_order_spec(count))
    specs.extend([_dense_nonlinear_spec(8), _dense_nonlinear_spec(10), _dense_nonlinear_spec(12)])
    return specs


def _scalar_higher_order_spec(order: int, *, nonlinear: bool) -> BenchmarkSystemSpec:
    symbol = "x"
    higher = _derivative_latex(symbol, order)
    terms = []
    for derivative_order, parameter in zip(range(order - 1, 0, -1), ("a", "b", "c", "k")):
        terms.append(f"-{parameter}*{_derivative_latex(symbol, derivative_order)}")
    terms.append("-m*x")
    if nonlinear:
        terms.append(r"(1/18)*\sin(x)")
    terms.append("u")
    equation = f"{higher}={_join_terms(terms)}"
    initial_conditions = {"x": 0.05, "x_dot": 0.0}
    if order >= 3:
        initial_conditions["x_ddot"] = 0.0
    for derivative_order in range(3, order):
        initial_conditions[f"x_d{derivative_order}"] = 0.0
    return BenchmarkSystemSpec(
        system_id=f"higher_order_{order}" + ("_nonlinear" if nonlinear else "_linear"),
        tier="tier2_structural",
        family="higher_order_scalar",
        latex=equation,
        generated_state_count=1,
        max_order=order,
        depth=4,
        includes_trig=nonlinear,
        nonlinear=nonlinear,
        parameter_values={"a": 0.7, "b": 0.5, "c": 0.3, "k": 0.2, "m": 0.9},
        initial_conditions=initial_conditions,
        input_values={"u": 0.08},
        symbol_config=_symbol_config(["a", "b", "c", "k", "m"], include_input=True),
        t_span=(0.0, 2.0),
        sample_count=140,
        tags=("structural", "higher_order", "input") + (("nonlinear", "trig") if nonlinear else ("linear",)),
        metadata={
            "expected_behavior": "pass",
            "supports_state_space": not nonlinear,
        },
    )


def _coupled_higher_order_spec() -> BenchmarkSystemSpec:
    latex = (
        r"\frac{d^3 x_1}{dt^3}=-a\ddot{x_1}-b\dot{x_1}-c x_1+k x_2+u" "\n"
        r"\dot{x_2}=-m x_2+(1/8)x_1"
    )
    return BenchmarkSystemSpec(
        system_id="higher_order_coupled_pair",
        tier="tier2_structural",
        family="higher_order_coupled",
        latex=latex,
        generated_state_count=2,
        max_order=3,
        depth=4,
        includes_trig=False,
        nonlinear=False,
        parameter_values={"a": 0.8, "b": 0.4, "c": 0.5, "k": 0.3, "m": 0.6},
        initial_conditions={"x_1": 0.08, "x_1_dot": 0.0, "x_1_ddot": 0.0, "x_2": -0.05},
        input_values={"u": 0.07},
        symbol_config=_symbol_config(["a", "b", "c", "k", "m"], include_input=True),
        t_span=(0.0, 2.5),
        sample_count=150,
        tags=("structural", "higher_order", "coupled", "input", "linear"),
        metadata={
            "expected_behavior": "pass",
            "supports_state_space": True,
        },
    )


def _nonlinear_higher_order_pair_spec() -> BenchmarkSystemSpec:
    latex = (
        r"\frac{d^3 x_1}{dt^3}=-a\ddot{x_1}-b\dot{x_1}-c x_1+(1/16)\sin(x_2)+u" "\n"
        r"\dot{x_2}=-m x_2+(1/12)\cos(x_1)"
    )
    return BenchmarkSystemSpec(
        system_id="higher_order_nonlinear_pair",
        tier="tier2_structural",
        family="higher_order_coupled",
        latex=latex,
        generated_state_count=2,
        max_order=3,
        depth=5,
        includes_trig=True,
        nonlinear=True,
        parameter_values={"a": 0.6, "b": 0.3, "c": 0.4, "m": 0.5},
        initial_conditions={"x_1": 0.04, "x_1_dot": 0.0, "x_1_ddot": 0.0, "x_2": 0.06},
        input_values={"u": 0.05},
        symbol_config=_symbol_config(["a", "b", "c", "m"], include_input=True),
        t_span=(0.0, 2.2),
        sample_count=150,
        tags=("structural", "higher_order", "coupled", "input", "nonlinear", "trig"),
        metadata={
            "expected_behavior": "pass",
            "supports_state_space": False,
        },
    )


def higher_order_specs() -> list[BenchmarkSystemSpec]:
    return [
        _scalar_higher_order_spec(3, nonlinear=False),
        _scalar_higher_order_spec(4, nonlinear=False),
        _scalar_higher_order_spec(5, nonlinear=False),
        _scalar_higher_order_spec(4, nonlinear=True),
        _coupled_higher_order_spec(),
        _nonlinear_higher_order_pair_spec(),
    ]


def controlled_system_specs() -> list[BenchmarkSystemSpec]:
    return [
        BenchmarkSystemSpec(
            system_id="controlled_feedback_pair",
            tier="tier2_structural",
            family="controlled_linear",
            latex=r"\dot{x_1}=x_2" "\n" r"\dot{x_2}=-a x_1-b x_2+c(u-k x_1)",
            generated_state_count=2,
            max_order=1,
            depth=3,
            includes_trig=False,
            nonlinear=False,
            parameter_values={"a": 0.9, "b": 0.3, "c": 0.7, "k": 0.4},
            initial_conditions={"x_1": 0.2, "x_2": 0.0},
            input_values={"u": 0.12},
            symbol_config=_symbol_config(["a", "b", "c", "k"], include_input=True),
            t_span=(0.0, 4.0),
            sample_count=180,
            tags=("structural", "controlled", "linear", "input"),
            metadata={"expected_behavior": "pass", "outputs": ["x_1"]},
        ),
        BenchmarkSystemSpec(
            system_id="controlled_cascade_triple",
            tier="tier2_structural",
            family="controlled_linear",
            latex=r"\dot{x_1}=-a x_1+b(u-x_3)" "\n" r"\dot{x_2}=x_1-c x_2" "\n" r"\dot{x_3}=x_2-m x_3",
            generated_state_count=3,
            max_order=1,
            depth=3,
            includes_trig=False,
            nonlinear=False,
            parameter_values={"a": 0.7, "b": 0.6, "c": 0.4, "m": 0.5},
            initial_conditions={"x_1": 0.1, "x_2": -0.05, "x_3": 0.02},
            input_values={"u": 0.08},
            symbol_config=_symbol_config(["a", "b", "c", "m"], include_input=True),
            t_span=(0.0, 4.0),
            sample_count=180,
            tags=("structural", "controlled", "linear", "input", "feedback"),
            metadata={"expected_behavior": "pass", "outputs": ["x_1", "x_3"]},
        ),
        BenchmarkSystemSpec(
            system_id="controlled_quad_chain",
            tier="tier2_structural",
            family="controlled_linear",
            latex=r"\dot{x_1}=x_2" "\n" r"\dot{x_2}=-a x_1-b x_2+c x_3+u" "\n" r"\dot{x_3}=-k x_3+m x_4" "\n" r"\dot{x_4}=-c x_4+x_1",
            generated_state_count=4,
            max_order=1,
            depth=4,
            includes_trig=False,
            nonlinear=False,
            parameter_values={"a": 0.6, "b": 0.25, "c": 0.35, "k": 0.4, "m": 0.3},
            initial_conditions={"x_1": 0.1, "x_2": 0.0, "x_3": -0.08, "x_4": 0.05},
            input_values={"u": 0.1},
            symbol_config=_symbol_config(["a", "b", "c", "k", "m"], include_input=True),
            t_span=(0.0, 4.0),
            sample_count=180,
            tags=("structural", "controlled", "linear", "input", "coupled"),
            metadata={"expected_behavior": "pass", "outputs": ["x_1", "x_3"]},
        ),
        BenchmarkSystemSpec(
            system_id="controlled_nonlinear_pair",
            tier="tier2_structural",
            family="controlled_nonlinear",
            latex=r"\dot{x_1}=x_2" "\n" r"\dot{x_2}=-a x_1-b x_2+(1/12)\sin(x_1)+c u",
            generated_state_count=2,
            max_order=1,
            depth=4,
            includes_trig=True,
            nonlinear=True,
            parameter_values={"a": 0.8, "b": 0.3, "c": 0.5},
            initial_conditions={"x_1": 0.15, "x_2": 0.0},
            input_values={"u": 0.06},
            symbol_config=_symbol_config(["a", "b", "c"], include_input=True),
            t_span=(0.0, 3.0),
            sample_count=170,
            tags=("structural", "controlled", "nonlinear", "trig", "input"),
            metadata={"expected_behavior": "pass", "outputs": ["x_1"]},
        ),
    ]


def _mass_spring_chain_latex(count: int, *, damped: bool) -> str:
    lines: list[str] = []
    for index in range(1, count + 1):
        mass = f"m_{index}"
        state = f"x_{index}"
        accel = _derivative_latex(state, 2)
        terms: list[str] = []
        if index > 1:
            left = f"x_{index - 1}"
            terms.append(f"k({left}-{state})")
            if damped:
                terms.append(f"c({_derivative_latex(left, 1)}-{_derivative_latex(state, 1)})")
        if index < count:
            right = f"x_{index + 1}"
            terms.append(f"-k({state}-{right})")
            if damped:
                terms.append(f"-c({_derivative_latex(state, 1)}-{_derivative_latex(right, 1)})")
        if not terms:
            terms.append("0")
        lines.append(f"{mass}{accel}={_join_terms(terms)}")
    return "\n".join(lines)


def _mass_spring_initial_conditions(count: int) -> dict[str, float]:
    initial_conditions: dict[str, float] = {}
    for index in range(1, count + 1):
        initial_conditions[f"x_{index}"] = round(0.03 * (count - index), 6)
        initial_conditions[f"x_{index}_dot"] = 0.0
    return initial_conditions


def _mass_spring_chain_spec(count: int, *, damped: bool) -> BenchmarkSystemSpec:
    parameter_values = {"k": 1.4, "c": 0.18}
    parameter_values.update({f"m_{index}": 0.9 + 0.05 * index for index in range(1, count + 1)})
    parameter_names = ["k"] + ([ "c"] if damped else []) + [f"m_{index}" for index in range(1, count + 1)]
    return BenchmarkSystemSpec(
        system_id=f"mass_spring_chain_{count}" + ("_damped" if damped else ""),
        tier="tier2_structural",
        family="physical_mass_spring",
        latex=_mass_spring_chain_latex(count, damped=damped),
        generated_state_count=count,
        max_order=2,
        depth=4,
        includes_trig=False,
        nonlinear=False,
        parameter_values=parameter_values,
        initial_conditions=_mass_spring_initial_conditions(count),
        input_values={},
        symbol_config=_symbol_config(parameter_names, include_input=False),
        t_span=(0.0, 4.0),
        sample_count=180,
        tags=("structural", "physical", "mass_spring", "linear", "high_state") + (("damped",) if damped else ()),
        metadata={"expected_behavior": "pass", "supports_state_space": True},
    )


def _rc_ladder_latex(count: int) -> str:
    states = _state_names(count, prefix="v")
    lines: list[str] = []
    for index, state in enumerate(states):
        terms: list[str] = [f"-(2/r)*{state}"]
        if index > 0:
            terms.append(f"(1/r)*{states[index - 1]}")
        else:
            terms.append("(1/r)*u")
        if index + 1 < len(states):
            terms.append(f"(1/r)*{states[index + 1]}")
        lines.append(f"c{_derivative_latex(state, 1)}={_join_terms(terms)}")
    return "\n".join(lines)


def _rc_ladder_spec(count: int) -> BenchmarkSystemSpec:
    return BenchmarkSystemSpec(
        system_id=f"rc_ladder_{count}",
        tier="tier2_structural",
        family="physical_rc_ladder",
        latex=_rc_ladder_latex(count),
        generated_state_count=count,
        max_order=1,
        depth=3,
        includes_trig=False,
        nonlinear=False,
        parameter_values={"r": 1.2, "c": 0.8},
        initial_conditions={f"v_{index}": round(0.02 * index, 6) for index in range(1, count + 1)},
        input_values={"u": 0.05},
        symbol_config=_symbol_config(["r", "c"], include_input=True),
        t_span=(0.0, 3.0),
        sample_count=160,
        tags=("structural", "physical", "rc", "linear", "input"),
        metadata={"expected_behavior": "pass", "supports_state_space": True},
    )


def _rlc_pair_spec() -> BenchmarkSystemSpec:
    latex = r"l\dot{i_1}=-r i_1-v_1+u" "\n" r"c\dot{v_1}=i_1-g v_1"
    return BenchmarkSystemSpec(
        system_id="rlc_pair",
        tier="tier2_structural",
        family="physical_rlc",
        latex=latex,
        generated_state_count=2,
        max_order=1,
        depth=3,
        includes_trig=False,
        nonlinear=False,
        parameter_values={"l": 1.1, "r": 0.6, "c": 0.9, "g": 0.4},
        initial_conditions={"i_1": 0.0, "v_1": 0.1},
        input_values={"u": 0.08},
        symbol_config=_symbol_config(["l", "r", "c", "g"], include_input=True),
        t_span=(0.0, 4.0),
        sample_count=180,
        tags=("structural", "physical", "rlc", "linear", "input"),
        metadata={"expected_behavior": "pass", "supports_state_space": True},
    )


def physical_system_specs() -> list[BenchmarkSystemSpec]:
    return [
        _mass_spring_chain_spec(4, damped=False),
        _mass_spring_chain_spec(5, damped=True),
        _mass_spring_chain_spec(6, damped=True),
        _rc_ladder_spec(4),
        _rc_ladder_spec(6),
        _rlc_pair_spec(),
    ]


def unsupported_hybrid_specs() -> list[BenchmarkSystemSpec]:
    return [
        BenchmarkSystemSpec(
            system_id="hybrid_piecewise_cases",
            tier="tier3_adversarial",
            family="hybrid_unsupported",
            latex=r"\dot{x}=\begin{cases}x,&x>0\\-x,&x\le 0\end{cases}",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=True,
            classification_mode="strict",
            expected_failure_stage="parse",
            expected_failure_substring="Unsupported",
            expected_failure_category="parse_failure",
            simulink_expected=False,
            tags=("adversarial", "hybrid", "piecewise", "unsupported"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="hybrid_saturation",
            tier="tier3_adversarial",
            family="hybrid_unsupported",
            latex=r"\dot{x}=\operatorname{sat}(x)",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=True,
            classification_mode="strict",
            expected_failure_stage="parse",
            expected_failure_substring="Unsupported",
            expected_failure_category="parse_failure",
            simulink_expected=False,
            tags=("adversarial", "hybrid", "saturation", "unsupported"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="hybrid_switching",
            tier="tier3_adversarial",
            family="hybrid_unsupported",
            latex=r"\dot{x}=\max(x,0)",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=True,
            classification_mode="strict",
            expected_failure_stage="parse",
            expected_failure_substring="Unsupported",
            expected_failure_category="parse_failure",
            simulink_expected=False,
            tags=("adversarial", "hybrid", "switching", "unsupported"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="hybrid_sign_logic",
            tier="tier3_adversarial",
            family="hybrid_unsupported",
            latex=r"\dot{x}=\mathrm{sgn}(x)",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=True,
            classification_mode="strict",
            expected_failure_stage="parse",
            expected_failure_substring="Unsupported",
            expected_failure_category="parse_failure",
            simulink_expected=False,
            tags=("adversarial", "hybrid", "logic", "unsupported"),
            metadata={"expected_behavior": "expected_failure"},
        ),
    ]


def adversarial_specs() -> list[BenchmarkSystemSpec]:
    return [
        BenchmarkSystemSpec(
            system_id="adversarial_dae",
            tier="tier3_adversarial",
            family="symbolic_failure",
            latex="x+y=1\n\\dot{x}=y",
            generated_state_count=2,
            max_order=1,
            depth=2,
            includes_trig=False,
            nonlinear=False,
            classification_mode="strict",
            expected_failure_stage="solve",
            expected_failure_substring="algebraic/DAE-like",
            expected_failure_category="symbolic_failure",
            simulink_expected=False,
            tags=("adversarial", "dae"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="adversarial_implicit_derivative",
            tier="tier3_adversarial",
            family="symbolic_failure",
            latex=r"\dot{x}+\sin(\dot{x})=u",
            generated_state_count=1,
            max_order=1,
            depth=2,
            includes_trig=True,
            nonlinear=True,
            input_values={"u": 0.1},
            symbol_config={"u": "input"},
            classification_mode="configured",
            expected_failure_stage="solve",
            expected_failure_substring="implicit nonlinear derivative coupling",
            expected_failure_category="symbolic_failure",
            simulink_expected=False,
            tags=("adversarial", "implicit_derivative"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="adversarial_ambiguous_forcing",
            tier="tier3_adversarial",
            family="symbolic_failure",
            latex=r"\dot{x}=a z",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=False,
            classification_mode="strict",
            expected_failure_stage="state_extraction",
            expected_failure_substring="Ambiguous external-symbol classification",
            expected_failure_category="symbolic_failure",
            simulink_expected=False,
            tags=("adversarial", "ambiguous"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="adversarial_duplicate_derivative",
            tier="tier3_adversarial",
            family="symbolic_failure",
            latex=r"\dot{x}=y" "\n" r"\dot{x}=z",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=False,
            classification_mode="strict",
            expected_failure_stage="solve",
            expected_failure_substring="Overdetermined or inconsistent system",
            expected_failure_category="symbolic_failure",
            simulink_expected=False,
            tags=("adversarial", "duplicate_derivative"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="adversarial_overdetermined_pair",
            tier="tier3_adversarial",
            family="symbolic_failure",
            latex=r"\dot{x}=y" "\n" r"\dot{y}=x" "\n" r"\dot{x}=y+1",
            generated_state_count=2,
            max_order=1,
            depth=2,
            includes_trig=False,
            nonlinear=False,
            classification_mode="strict",
            expected_failure_stage="solve",
            expected_failure_substring="Overdetermined or inconsistent system",
            expected_failure_category="symbolic_failure",
            simulink_expected=False,
            tags=("adversarial", "overdetermined"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="adversarial_graph_fault",
            tier="tier3_adversarial",
            family="graph_fault_injection",
            latex=r"\dot{x}=-a x+b u",
            generated_state_count=1,
            max_order=1,
            depth=1,
            includes_trig=False,
            nonlinear=False,
            parameter_values={"a": 0.5, "b": 0.3},
            initial_conditions={"x": 0.1},
            input_values={"u": 0.05},
            symbol_config=_symbol_config(["a", "b"], include_input=True),
            classification_mode="configured",
            expected_failure_stage="graph_validation",
            expected_failure_category="graph_invalid",
            simulink_expected=False,
            graph_fault="drop_node",
            tags=("adversarial", "graph_fault"),
            metadata={"expected_behavior": "expected_failure"},
        ),
        BenchmarkSystemSpec(
            system_id="adversarial_numerical_blowup",
            tier="tier3_adversarial",
            family="numerical_instability",
            latex=r"\dot{x}=x^2",
            generated_state_count=1,
            max_order=1,
            depth=2,
            includes_trig=False,
            nonlinear=True,
            parameter_values={},
            initial_conditions={"x": 2.0},
            input_values={},
            classification_mode="strict",
            t_span=(0.0, 1.0),
            sample_count=160,
            expected_failure_stage="ode_simulation",
            expected_failure_substring="Required step size is less than spacing between numbers",
            expected_failure_category="numerical_instability",
            simulink_expected=False,
            tags=("adversarial", "numerical_instability", "nonlinear"),
            metadata={"expected_behavior": "expected_failure"},
        ),
    ]


def build_simucompilebench_specs(
    *,
    legacy_count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    legacy_seed: int = DEFAULT_SYNTHETIC_SEED,
    include_legacy: bool = True,
) -> list[BenchmarkSystemSpec]:
    """Build the full benchmark catalog."""
    specs: list[BenchmarkSystemSpec] = []
    if include_legacy:
        specs.extend(legacy_tier_specs(count=legacy_count, seed=legacy_seed))
    specs.extend(high_state_structural_specs())
    specs.extend(higher_order_specs())
    specs.extend(controlled_system_specs())
    specs.extend(physical_system_specs())
    specs.extend(unsupported_hybrid_specs())
    specs.extend(adversarial_specs())
    return specs


def write_benchmark_dataset(
    specs: list[BenchmarkSystemSpec],
    *,
    root_dir: str | Path = "benchmark",
    data_path: str | Path = "data/simucompilebench_systems.json",
) -> dict[str, object]:
    """Write the benchmark dataset to a tiered on-disk structure."""
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    for tier in ("tier1_verified", "tier2_structural", "tier3_adversarial"):
        tier_dir = root / tier
        if tier_dir.exists():
            shutil.rmtree(tier_dir)
        tier_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, object]] = []
    for spec in specs:
        target_dir = root / spec.tier / spec.system_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "equations.tex").write_text(spec.latex + "\n", encoding="utf-8")
        metadata = spec.to_metadata()
        (target_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        manifest.append(metadata | {"equations_path": str((target_dir / 'equations.tex').as_posix())})

    root_manifest = {
        "systems": manifest,
        "tier_counts": {
            tier: sum(1 for spec in specs if spec.tier == tier)
            for tier in ("tier1_verified", "tier2_structural", "tier3_adversarial")
        },
    }
    (root / "index.json").write_text(json.dumps(root_manifest, indent=2, sort_keys=True), encoding="utf-8")

    data_output = Path(data_path)
    data_output.parent.mkdir(parents=True, exist_ok=True)
    data_output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return root_manifest
