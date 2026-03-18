# Deterministic LaTeX ODE Compiler

This repo is a deterministic symbolic compiler backend for restricted LaTeX ODEs. It is designed to be reproducible, inspectable, and strict enough to support a later deterministic Simulink graph builder.

The current pipeline:

1. normalizes supported LaTeX variants into a narrow grammar
2. tokenizes and parses equations into explicit expression nodes
3. serializes equations into canonical Python dictionaries
4. extracts state candidates, derivative-derived states, inputs, and parameters deterministically
5. solves for highest-order derivatives
6. reduces systems to explicit first-order form
7. derives linear state-space form when the first-order system is linear
8. lowers the first-order system into a deterministic graph dictionary
9. converts the graph dictionary into a Simulink-ready model dictionary
10. builds a real `.slx` model through the MATLAB engine
11. validates the graph dictionary and Simulink model structure
12. simulates the explicit first-order system
13. simulates the state-space system when available
14. simulates the generated Simulink model for supported linear examples
15. compares trajectories with RMSE and max absolute error

## Deterministic Guarantees

- No LLMs, no probabilistic parsing, no random IDs.
- Unsupported syntax raises explicit errors.
- Symbol classification uses deterministic rules and optional explicit configuration.
- Graph lowering uses stable IDs and structural common-subexpression reuse.
- Report generation is machine-readable and reproducible.

## Supported Grammar

Supported frontend constructs:

- equations separated by newlines
- `+`, `-`, `*`, `/`, `^`
- unary minus
- implicit multiplication such as `2x`, `k(x-y)`, `m\frac{dx}{dt}`
- grouping with `()` and `{}`
- `\dot{x}`, `\ddot{x}`
- `\frac{d^n x}{dt^n}` for explicit integer `n`
- nested fractions
- indexed symbols such as `x_1`, `x_2`, `k_12`
- `\left` and `\right` normalization

Important constraint:

- plain multi-letter identifiers are intentionally not treated as single symbols because the frontend preserves deterministic implicit multiplication behavior from Phase 1. Use single-letter or indexed names like `w_0`, `x_1`, `a_3`.

Unsupported by design:

- arbitrary LaTeX environments
- unknown LaTeX commands
- derivatives with respect to variables other than `t`
- DAE-like algebraic constraints
- implicit nonlinear derivative coupling with non-unique solves
- nonlinear systems in state-space conversion

## Symbol Metadata

The extraction layer classifies symbols into:

- `state_candidate`
- `derivative_derived_state`
- `input`
- `parameter`
- `independent_variable`
- `known_constant`
- `unknown_unresolved`

Two modes are available:

- `strict`: infer using only deterministic math rules
- `configured`: resolve ambiguity with a user JSON config

Example config:

```json
{
  "a": "parameter",
  "b": "input"
}
```

## Graph Dictionary

The compiler lowers first-order systems into a deterministic graph dictionary with:

- `nodes`
- `edges`
- `outputs`
- `state_chains` for first-order system graphs

Supported graph ops:

- `constant`
- `symbol_input`
- `state_signal`
- `add`
- `sum`
- `mul`
- `gain`
- `div`
- `pow`
- `negate`
- `integrator`

Example shape:

```python
{
    "kind": "first_order_system_graph",
    "name": "mass_spring_damper",
    "nodes": [
        {"id": "integrator_x", "op": "integrator", "inputs": ["state_x_dot_rhs"], "state": "x"},
        {"id": "state_x", "op": "state_signal", "inputs": ["integrator_x"], "state": "x"},
    ],
    "edges": [
        {"src": "state_x_dot_rhs", "dst": "integrator_x", "dst_port": 0},
        {"src": "integrator_x", "dst": "state_x", "dst_port": 0},
    ],
    "outputs": {"x": "state_x"},
    "state_chains": [
        {"state": "x", "signal": "state_x", "integrator": "integrator_x", "rhs": "state_x_dot_rhs"}
    ],
}
```

This graph format is the bridge to a later deterministic Simulink exporter.

## Simulink Backend

The backend modules live in [backend/](/Users/chancelavoie/Desktop/simulinkcopilot/backend):

- [graph_to_simulink.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/graph_to_simulink.py)
- [simulink_dict.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/simulink_dict.py)
- [block_library.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/block_library.py)
- [builder.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/builder.py)
- [simulate_simulink.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/simulate_simulink.py)
- [extract_signals.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/extract_signals.py)
- [validate_simulink.py](/Users/chancelavoie/Desktop/simulinkcopilot/backend/validate_simulink.py)

Current backend behavior:

- validated first-order graphs lower deterministically into Simulink block dictionaries
- models are built through `matlab.engine`
- linear examples are simulated in Simulink and compared against both Python ODE and Python state-space runs
- outputs are extracted from `Simulink.SimulationOutput.yout`

Current backend constraints:

- the validated backend path is currently for linear examples
- runtime inputs must currently be constant for backend validation
- nonlinear state-space conversion remains unsupported

## Supported System Classes

- linear first-order systems
- linear higher-order systems reduced to first order
- coupled multi-state linear systems
- mixed first/second-order systems
- explicit nonlinear polynomial systems

## CLI

Run the full pipeline:

```bash
python3 pipeline/run_pipeline.py --input examples/mass_spring_damper.tex
```

Useful flags:

- `--show-ir`
- `--show-first-order`
- `--show-state-space`
- `--write-graph-json /tmp/model_graph.json`
- `--validate-graph`
- `--run-sim`
- `--simulink`
- `--simulink-output-dir generated_models/backend_models`
- `--report-json /tmp/pipeline_report.json`

Examples:

```bash
python3 pipeline/run_pipeline.py --input examples/mass_spring_damper.tex --show-ir --write-graph-json reports/mass_spring_graph.json
python3 pipeline/run_pipeline.py --input examples/nonlinear_pendulum.tex --show-first-order --validate-graph
python3 pipeline/run_pipeline.py --input examples/mass_spring_damper.tex --simulink --simulink-output-dir generated_models/backend_models
```

## Tests

Run the full unit suite:

```bash
python3 -m unittest discover -v
```

## Bundled Examples

Run all curated examples:

```bash
python3 examples/run_examples.py
```

Examples include:

- `mass_spring_damper.tex`
- `coupled_system.tex`
- `two_mass_coupled.tex`
- `three_mass_coupled.tex`
- `damped_forced_system.tex`
- `driven_oscillator.tex`
- `nonlinear_pendulum.tex`
- `third_order_system.tex`
- `mixed_parameter_forms.tex`

## Regression Report

Generate the Phase 2 benchmark-style report:

```bash
python3 reports/generate_phase3_report.py
```

This writes:

- `reports/phase2_report.json`
- `reports/phase2_report.md`
- `reports/phase3_report.json`
- `reports/phase3_report.md`

## Limitations and Next Steps

Current limitations:

- no trigonometric/function frontend support yet
- no plain multi-letter symbol mode
- state-space generation is linear-only
- no DAE support
- no implicit nonlinear derivative solving
- Simulink backend validation currently assumes constant inputs

Natural next steps:

- extend the frontend with additional deterministic math functions
- add richer symbol metadata/value configuration
- extend the Simulink backend beyond the current linear/constant-input validation path
- add more failure-focused regression cases
