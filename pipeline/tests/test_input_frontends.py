from __future__ import annotations

import math

import pytest

from ir.equation_dict import equation_to_string
from latex_frontend.symbols import DeterministicCompileError
from pipeline.input_frontends import normalize_problem
from pipeline.run_pipeline import run_pipeline_payload, run_pipeline_problem
from states.extract_states import analyze_normalized_problem


def _problem_signature(problem) -> dict[str, object]:
    return {
        "time_variable": problem.time_variable,
        "states": tuple(problem.states),
        "algebraics": tuple(problem.algebraics),
        "inputs": tuple(problem.inputs),
        "parameters": tuple(problem.parameters),
        "equations": tuple(equation_to_string(equation) for equation in problem.equation_nodes()),
        "derivative_order_info": dict(problem.derivative_order_info),
    }


def _classification(problem) -> str:
    mode = "configured" if problem.declared_symbol_config() else "strict"
    return analyze_normalized_problem(problem, mode=mode).dae_system.classification.kind


def test_normalized_problem_matches_across_latex_and_matlab_symbolic_for_explicit_ode() -> None:
    latex_problem = normalize_problem(
        {
            "source_type": "latex",
            "text": r"\dot{x}=-x+u",
            "states": ["x"],
            "inputs": ["u"],
            "time_variable": "t",
        }
    )
    matlab_symbolic_problem = normalize_problem(
        {
            "source_type": "matlab_symbolic",
            "equations": ["diff(x,t) == -x + u"],
            "states": ["x"],
            "inputs": ["u"],
            "time_variable": "t",
        }
    )

    assert _problem_signature(latex_problem) == _problem_signature(matlab_symbolic_problem)
    assert _classification(latex_problem) == "explicit_ode"
    assert _classification(matlab_symbolic_problem) == "explicit_ode"


def test_normalized_problem_matches_across_latex_and_matlab_equation_text_for_reducible_dae() -> None:
    latex_problem = normalize_problem(
        {
            "source_type": "latex",
            "text": r"\dot{x}=z" + "\n" + r"z+\sin(x)=0",
            "states": ["x"],
            "algebraics": ["z"],
        }
    )
    matlab_text_problem = normalize_problem(
        {
            "source_type": "matlab_equation_text",
            "equations": ["xdot = z", "0 = z + sin(x)"],
            "states": ["x"],
            "algebraics": ["z"],
        }
    )

    assert _problem_signature(latex_problem) == _problem_signature(matlab_text_problem)
    assert _classification(latex_problem) == "reducible_semi_explicit_dae"
    assert _classification(matlab_text_problem) == "reducible_semi_explicit_dae"


def test_preserved_nonlinear_dae_matches_across_latex_symbolic_and_text_front_doors() -> None:
    payloads = [
        {
            "source_type": "latex",
            "text": r"\dot{x}=-x+z" + "\n" + r"z^3+z-x=0",
            "states": ["x"],
            "algebraics": ["z"],
        },
        {
            "source_type": "matlab_symbolic",
            "equations": ["diff(x,t) == -x + z", "0 == z^3 + z - x"],
            "states": ["x"],
            "algebraics": ["z"],
            "time_variable": "t",
        },
        {
            "source_type": "matlab_equation_text",
            "equations": ["xdot = -x + z", "0 = z^3 + z - x"],
            "states": ["x"],
            "algebraics": ["z"],
        },
    ]
    problems = [normalize_problem(payload) for payload in payloads]

    signatures = {_problem_signature(problem)["equations"] for problem in problems}
    classifications = {_classification(problem) for problem in problems}

    assert len(signatures) == 1
    assert classifications == {"nonlinear_preserved_semi_explicit_dae"}


def test_multi_argument_functions_match_across_latex_symbolic_and_text_front_doors() -> None:
    payloads = [
        {
            "source_type": "latex",
            "text": r"\dot{x}=\atan2(u,a)+\min(u,b)+\max(c,d)+\sat(u,l,h)",
            "states": ["x"],
            "inputs": ["u"],
            "parameters": ["a", "b", "c", "d", "l", "h"],
            "time_variable": "t",
        },
        {
            "source_type": "matlab_symbolic",
            "equations": ["diff(x,t) == atan2(u,a) + min(u,b) + max(c,d) + sat(u,l,h)"],
            "states": ["x"],
            "inputs": ["u"],
            "parameters": ["a", "b", "c", "d", "l", "h"],
            "time_variable": "t",
        },
        {
            "source_type": "matlab_equation_text",
            "equations": ["xdot = atan2(u,a) + min(u,b) + max(c,d) + sat(u,l,h)"],
            "states": ["x"],
            "inputs": ["u"],
            "parameters": ["a", "b", "c", "d", "l", "h"],
            "time_variable": "t",
        },
    ]

    problems = [normalize_problem(payload) for payload in payloads]
    signatures = [_problem_signature(problem) for problem in problems]

    assert signatures[0] == signatures[1] == signatures[2]
    rendered = signatures[0]["equations"][0]
    assert "atan2(a, u)" in rendered or "atan2(u, a)" in rendered
    assert "Min" in rendered
    assert "Max" in rendered
    assert "sat(u, l, h)" in rendered


def test_matlab_ode_function_matches_latex_for_simple_explicit_ode() -> None:
    latex_problem = normalize_problem(
        {
            "source_type": "latex",
            "text": r"\dot{x_1}=-x_1+u_1" + "\n" + r"\dot{x_2}=x_1-x_2",
            "states": ["x_1", "x_2"],
            "inputs": ["u_1"],
            "time_variable": "t",
        }
    )
    ode_function_problem = normalize_problem(
        {
            "source_type": "matlab_ode_function",
            "function_spec": {
                "representation": "vector_rhs",
                "state_vector_name": "x",
                "input_vector_name": "u",
                "rhs": ["-x(1) + u(1)", "x(1) - x(2)"],
            },
            "state_names": ["x_1", "x_2"],
            "input_names": ["u_1"],
            "time_variable": "t",
        }
    )

    assert _problem_signature(latex_problem) == _problem_signature(ode_function_problem)
    assert _classification(ode_function_problem) == "explicit_ode"


@pytest.mark.parametrize(
    ("payload", "expected_kind"),
    [
        (
            {
                "source_type": "matlab_symbolic",
                "equations": ["diff(x,t) == -x + u"],
                "states": ["x"],
                "inputs": ["u"],
                "time_variable": "t",
            },
            "explicit_ode",
        ),
        (
            {
                "source_type": "matlab_equation_text",
                "equations": ["xdot = z", "0 = z + sin(x)"],
                "states": ["x"],
                "algebraics": ["z"],
            },
            "reducible_semi_explicit_dae",
        ),
        (
            {
                "source_type": "matlab_symbolic",
                "equations": ["diff(x,t) == -x + z", "0 == z^3 + z - x"],
                "states": ["x"],
                "algebraics": ["z"],
                "time_variable": "t",
            },
            "nonlinear_preserved_semi_explicit_dae",
        ),
        (
            {
                "source_type": "matlab_equation_text",
                "equations": ["xdot + y = u", "x + y = 1"],
                "states": ["x"],
                "algebraics": ["y"],
                "inputs": ["u"],
            },
            "reducible_semi_explicit_dae",
        ),
    ],
)
def test_route_classification_matches_supported_front_door_examples(payload: dict[str, object], expected_kind: str) -> None:
    assert _classification(normalize_problem(payload)) == expected_kind


def test_higher_order_preserved_dae_remains_rejected() -> None:
    problem = normalize_problem(
        {
            "source_type": "matlab_symbolic",
            "equations": ["diff(x,t,2) + y == 0", "0 == y + sin(y) - x"],
            "states": ["x"],
            "algebraics": ["y"],
            "time_variable": "t",
        }
    )

    assert _classification(problem) == "unsupported_dae"


def test_matlab_symbolic_normalization_rewrites_function_of_time_symbols() -> None:
    problem = normalize_problem(
        {
            "source_type": "matlab_symbolic",
            "equations": ["m*diff(x(t), t, t) + c*diff(x(t), t) + k*x(t) == u(t)"],
        }
    )

    signature = _problem_signature(problem)
    assert signature["time_variable"] == "t"
    assert signature["equations"] == ("D1_x*c + D2_x*m + k*x = u",)


def test_opaque_matlab_ode_function_is_rejected_honestly() -> None:
    with pytest.raises(DeterministicCompileError, match="opaque function handles"):
        normalize_problem(
            {
                "source_type": "matlab_ode_function",
                "function_spec": {
                    "representation": "opaque_function_handle",
                },
                "state_names": ["x"],
            }
        )


def test_ambiguous_matlab_derivative_alias_is_rejected() -> None:
    with pytest.raises(DeterministicCompileError, match="state derivative or an ordinary variable"):
        normalize_problem(
            {
                "source_type": "matlab_equation_text",
                "equations": ["xdot = -x"],
            }
        )


def test_nonsquare_algebraic_subsystem_is_rejected() -> None:
    problem = normalize_problem(
        {
            "source_type": "matlab_symbolic",
            "equations": [
                "diff(x,t) == z",
                "0 == z - x",
                "0 == z + x - 1",
            ],
            "states": ["x"],
            "algebraics": ["z"],
            "time_variable": "t",
        }
    )

    assert _classification(problem) == "unsupported_dae"


def test_end_to_end_explicit_ode_matches_across_latex_and_matlab_ode_function() -> None:
    latex_result = run_pipeline_problem(
        normalize_problem(
            {
                "source_type": "latex",
                "text": r"\dot{x_1}=-x_1+u_1" + "\n" + r"\dot{x_2}=x_1-x_2",
                "states": ["x_1", "x_2"],
                "inputs": ["u_1"],
            }
        ),
        run_sim=True,
        run_simulink=False,
        runtime_override={
            "initial_conditions": {"x_1": 0.5, "x_2": -0.25},
            "input_values": {"u_1": 1.0},
            "t_span": [0.0, 1.0],
            "sample_count": 6,
        },
    )
    matlab_result = run_pipeline_payload(
        {
            "source_type": "matlab_ode_function",
            "function_spec": {
                "representation": "vector_rhs",
                "state_vector_name": "x",
                "input_vector_name": "u",
                "rhs": ["-x(1) + u(1)", "x(1) - x(2)"],
            },
            "state_names": ["x_1", "x_2"],
            "input_names": ["u_1"],
            "time_variable": "t",
        },
        run_sim=True,
        run_simulink=False,
        runtime_override={
            "initial_conditions": {"x_1": 0.5, "x_2": -0.25},
            "input_values": {"u_1": 1.0},
            "t_span": [0.0, 1.0],
            "sample_count": 6,
        },
    )

    assert latex_result["dae_classification"]["kind"] == "explicit_ode"
    assert matlab_result["dae_classification"]["kind"] == "explicit_ode"
    assert latex_result["comparison"]["passes"] is True
    assert matlab_result["comparison"]["passes"] is True
    assert tuple(matlab_result["first_order"]["states"]) == ("x_1", "x_2")


def test_end_to_end_reducible_dae_matches_across_latex_and_matlab_equation_text() -> None:
    latex_problem = normalize_problem(
        {
            "source_type": "latex",
            "text": r"\dot{x}=z" + "\n" + r"z+\sin(x)=0",
            "states": ["x"],
            "algebraics": ["z"],
        }
    )
    matlab_payload = {
        "source_type": "matlab_equation_text",
        "equations": ["xdot = z", "0 = z + sin(x)"],
        "states": ["x"],
        "algebraics": ["z"],
    }
    runtime_override = {
        "initial_conditions": {"x": 0.2},
        "t_span": [0.0, 0.25],
        "sample_count": 6,
    }

    latex_result = run_pipeline_problem(latex_problem, run_sim=True, run_simulink=False, runtime_override=runtime_override)
    matlab_result = run_pipeline_payload(matlab_payload, run_sim=True, run_simulink=False, runtime_override=runtime_override)

    assert latex_result["dae_classification"]["kind"] == "reducible_semi_explicit_dae"
    assert matlab_result["dae_classification"]["kind"] == "reducible_semi_explicit_dae"
    assert latex_result["dae_validation"]["simulation_success"] is True
    assert matlab_result["dae_validation"]["simulation_success"] is True
    assert latex_result["ode_result"] is not None
    assert matlab_result["ode_result"] is not None
    assert math.isclose(
        latex_result["consistent_initialization"].algebraic_initial_conditions["z"],
        matlab_result["consistent_initialization"].algebraic_initial_conditions["z"],
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def test_end_to_end_preserved_nonlinear_dae_matches_across_latex_and_matlab_symbolic() -> None:
    runtime_override = {
        "initial_conditions": {"x": 0.2, "z": 0.2},
        "t_span": [0.0, 0.25],
        "sample_count": 6,
    }
    latex_result = run_pipeline_problem(
        normalize_problem(
            {
                "source_type": "latex",
                "text": r"\dot{x}=-x+z" + "\n" + r"z^3+z-x=0",
                "states": ["x"],
                "algebraics": ["z"],
            }
        ),
        run_sim=True,
        run_simulink=False,
        runtime_override=runtime_override,
    )
    matlab_result = run_pipeline_payload(
        {
            "source_type": "matlab_symbolic",
            "equations": ["diff(x,t) == -x + z", "0 == z^3 + z - x"],
            "states": ["x"],
            "algebraics": ["z"],
            "time_variable": "t",
        },
        run_sim=True,
        run_simulink=False,
        runtime_override=runtime_override,
    )

    assert latex_result["dae_classification"]["kind"] == "nonlinear_preserved_semi_explicit_dae"
    assert matlab_result["dae_classification"]["kind"] == "nonlinear_preserved_semi_explicit_dae"
    assert latex_result["dae_validation"]["simulation_success"] is True
    assert matlab_result["dae_validation"]["simulation_success"] is True
    assert latex_result["graph"] is not None
    assert matlab_result["graph"] is not None


def test_end_to_end_linear_descriptor_capable_balance_matches_across_latex_and_matlab_text() -> None:
    runtime_override = {
        "initial_conditions": {"x": 0.2, "y": 0.8},
        "input_values": {"u": 1.0},
        "t_span": [0.0, 0.25],
        "sample_count": 6,
    }
    latex_result = run_pipeline_problem(
        normalize_problem(
            {
                "source_type": "latex",
                "text": r"\dot{x}+y=u" + "\n" + r"x+y=1",
                "states": ["x"],
                "algebraics": ["y"],
                "inputs": ["u"],
            }
        ),
        run_sim=True,
        run_simulink=False,
        runtime_override=runtime_override,
    )
    matlab_result = run_pipeline_payload(
        {
            "source_type": "matlab_equation_text",
            "equations": ["xdot + y = u", "x + y = 1"],
            "states": ["x"],
            "algebraics": ["y"],
            "inputs": ["u"],
        },
        run_sim=True,
        run_simulink=False,
        runtime_override=runtime_override,
    )

    assert latex_result["dae_classification"]["kind"] == "reducible_semi_explicit_dae"
    assert matlab_result["dae_classification"]["kind"] == "reducible_semi_explicit_dae"
    assert latex_result["descriptor_system"] is not None
    assert matlab_result["descriptor_system"] is not None
    assert latex_result["comparison"]["passes"] is True
    assert matlab_result["comparison"]["passes"] is True
