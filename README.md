# Deterministic Equation-to-Simulink Compiler

This repo is a deterministic symbolic compiler backend for restricted equation inputs and a narrow, explicit class of semi-explicit DAEs. It currently accepts LaTeX plus three MATLAB-native front doors, normalizes all supported inputs into one shared IR, and keeps the downstream classifier, reducer, validator, and Simulink lowering paths shared. It is designed to be reproducible, inspectable, and strict enough to support deterministic Simulink model generation without hand-waving over unsupported systems.

## Repo Layout

- `backend/`, `canonicalize/`, `eqn2sim_gui/`, `ir/`, `latex_frontend/`, `pipeline/`, `simulate/`, `simucompilebench/`, `simulink/`, `states/`
  Core implementation modules.
- `scripts/`
  Supported CLI entrypoints. Run these with `python3 -m scripts.<name>`.
- `workspace/`
  Non-code assets, bundled examples, generated models, reports, benchmark data, demos, and the manuscript bundle.
- `tests/`
  Cross-cutting integration and smoke tests.

Repo conventions are documented in [CODING_STANDARDS.md](/Users/chancelavoie/Desktop/simulinkcopilot/CODING_STANDARDS.md).

The current pipeline:

1. accepts one of four front doors:
   - `latex`
   - `matlab_symbolic`
   - `matlab_equation_text`
   - `matlab_ode_function`
2. normalizes supported source inputs into one shared `NormalizedProblem` schema
3. converts front-end equations into canonical expression nodes
4. extracts differential states, derivative-derived states, inputs, parameters, and algebraic variables deterministically
5. classifies the system as explicit ODE, reducible semi-explicit DAE, descriptor-capable semi-explicit DAE artifact, nonlinear preserved semi-explicit DAE, or unsupported DAE
6. reduces explicit and reducible systems through the explicit ODE path
7. preserves supported first-order semi-explicit DAE constraints in typed DAE artifacts when reduction is not the intended route
8. derives linear descriptor/state-space artifacts where applicable
9. lowers explicit systems into deterministic graph dictionaries and supported preserved DAEs into preserved graph/descriptor artifacts
10. converts graph or descriptor artifacts into Simulink-ready model dictionaries
11. builds a real `.slx` model through the MATLAB engine when requested
12. validates graph, descriptor, and Simulink model structure
13. simulates explicit ODE systems directly in Python
14. validates supported preserved DAEs in Python with consistent initialization, residual checks, and differential-state trajectories
15. compares Python and Simulink trajectories for the supported route that was selected

See [docs/input_frontends.md](/Users/chancelavoie/Desktop/simulinkcopilot/docs/input_frontends.md) for the front-door payloads and [docs/ir_schema.md](/Users/chancelavoie/Desktop/simulinkcopilot/docs/ir_schema.md) for the shared normalized schema.

## Deterministic Guarantees

- No LLMs, no probabilistic parsing, no random IDs.
- Unsupported syntax raises explicit errors.
- Symbol classification uses deterministic rules and optional explicit configuration.
- Graph lowering uses stable IDs and structural common-subexpression reuse.
- Report generation is machine-readable and reproducible.

## Supported Front Doors

- `latex`
  Existing restricted LaTeX grammar path.
- `matlab_symbolic`
  MATLAB Symbolic Math Toolbox-style equation strings such as `diff(x,t) == -x + z`.
- `matlab_equation_text`
  MATLAB-ish equation strings such as `xdot = z` and `0 = z + sin(x)`.
- `matlab_ode_function`
  Structured exported RHS specifications only. Opaque MATLAB function handles are intentionally rejected.

Important scope note:

- This change broadens input coverage, not DAE theory coverage.
- All supported front doors normalize into the same internal IR.
- The downstream support boundary for ODEs and DAEs is unchanged unless explicitly documented elsewhere.

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
- higher-index DAEs without index reduction
- fully implicit DAEs outside the supported semi-explicit normal form
- structurally singular or non-square preserved algebraic subsystems
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
- `algebraic_chains` for preserved semi-explicit DAE graphs

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

- validated explicit first-order graphs lower deterministically into Simulink block dictionaries
- supported preserved semi-explicit DAE graphs lower into Simulink block dictionaries with algebraic-constraint structure
- descriptor-form artifacts can lower to Simulink without forcing the algebraic constraint structure through the explicit ODE graph path
- models are built through `matlab.engine`
- explicit ODE examples are simulated in Simulink and compared against Python ODE and, when available, state-space runs
- supported preserved DAEs can be validated against Python-side DAE execution on their supported subset
- outputs are extracted from `Simulink.SimulationOutput.yout`

Current backend constraints:

- derivatives with respect to variables other than `t` are still unsupported
- high-index DAEs remain unsupported
- Python-side DAE validation is limited to the supported semi-explicit subset
- nonlinear state-space conversion remains unsupported

## Supported System Classes

- linear first-order systems
- linear higher-order systems reduced to first order
- coupled multi-state linear systems
- mixed first/second-order systems
- explicit nonlinear polynomial systems
- reducible semi-explicit DAEs with deterministic algebraic elimination
- first-order nonlinear preserved semi-explicit DAEs with Python-side validation and Simulink lowering
- first-order linear semi-explicit DAEs with descriptor artifacts and preserved-constraint lowering support

## DAE Support

The repo supports a narrow, explicit set of DAE routes:

- `explicit_ode`
  No algebraic structure remains after parsing/classification.
- `reducible_semi_explicit_dae`
  Algebraic variables can be solved deterministically and substituted away before the explicit ODE path.
- `nonlinear_preserved_semi_explicit_dae`
  First-order semi-explicit DAEs of the form `x' = f(x, z, u, p, t)`, `0 = g(x, z, u, p, t)` are preserved through a DAE-native path for a supported nonlinear subset.
- `linear_descriptor_dae`
  Linear descriptor artifacts exist for first-order linear semi-explicit DAEs, and preserved-constraint descriptor lowering is supported where that route is selected.
- `unsupported_dae`
  Higher-index, non-square, structurally singular, or otherwise unsupported algebraic structures are rejected explicitly.

See [docs/dae_support.md](/Users/chancelavoie/Desktop/simulinkcopilot/docs/dae_support.md) for the route decision tree and the exact support boundary.

## CLI

Run the full pipeline from a LaTeX file:

```bash
python3 -m pipeline.run_pipeline --input workspace/examples/mass_spring_damper.tex
```

Or pass LaTeX directly:

```bash
python3 -m pipeline.run_pipeline --equations $'m\\ddot{x}+c\\dot{x}+kx=u'
```

Run a MATLAB-symbolic payload:

```bash
python3 -m pipeline.run_pipeline \
  --input-payload-json /tmp/matlab_symbolic_payload.json \
  --no-simulink
```

Useful flags:

- `--source-type latex|matlab_symbolic|matlab_equation_text|matlab_ode_function`
- `--input-payload-json /tmp/input_payload.json`
- `--show-ir`
- `--show-first-order`
- `--show-state-space`
- `--write-graph-json /tmp/model_graph.json`
- `--validate-graph`
- `--run-sim`
- `--simulink` (default)
- `--no-simulink`
- `--runtime-json /tmp/runtime.json`
- `--equations $'m\\ddot{x}+c\\dot{x}+kx=u'`
- `--equations-name inline_system`
- `--parameter m_1=10.0 --parameter k=100.0`
- `--initial x=1.0 --initial x_dot=0.0`
- `--input-value u=1.5`
- `--t-span 0 10 --sample-count 1000`
- `--symbol-role F_drive=input --symbol-role m_cart=parameter`
- `--state theta --state theta_dot --state x --state x_dot`
- `--simulink-output-dir /repo/root/workspace/bedillion_demo`
- `--report-json /tmp/pipeline_report.json`

Example with fully inline CLI runtime overrides:

```bash
python3 -m pipeline.run_pipeline \
  --equations $'(m_1 + m_2)\\ddot{x} + \\frac{m_2 l}{2}\\cos(\\theta)\\ddot{\\theta} - \\frac{m_2 l}{2}\\sin(\\theta)\\dot{\\theta}^2 + kx = 0\n\\frac{m_2 l}{2}\\cos(\\theta)\\ddot{x} + \\frac{1}{4}(m_2 l^2 + 4I)\\ddot{\\theta} + \\frac{m_2 g l}{2}\\sin(\\theta) = 0' \
  --equations-name cart_pendulum_inline \
  --parameter m_1=10.0 \
  --parameter m_2=2.0 \
  --parameter l=1.0 \
  --parameter I=0.17 \
  --parameter g=9.81 \
  --parameter k=100.0 \
  --initial x=1.0 \
  --initial x_dot=0.0 \
  --initial theta=0.7853981633974483 \
  --initial theta_dot=0.0 \
  --state theta \
  --state theta_dot \
  --state x \
  --state x_dot \
  --t-span 0 10 \
  --sample-count 1000 \
  --simulink-output-dir /repo/root/workspace/bedillion_demo
```

If you want a parser-only run without generating the `.slx`, add `--no-simulink`.

Examples:

```bash
python3 -m pipeline.run_pipeline --input workspace/examples/mass_spring_damper.tex --show-ir --write-graph-json workspace/reports/mass_spring_graph.json
python3 -m pipeline.run_pipeline --input workspace/examples/nonlinear_pendulum.tex --show-first-order --validate-graph
python3 -m pipeline.run_pipeline --input workspace/examples/mass_spring_damper.tex --simulink-output-dir workspace/bedillion_demo
```

## Tests

Install test dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Run the fast deterministic suite:

```bash
python3 -m scripts.run_tests
```

Run the full suite, including slow and MATLAB-backed tests:

```bash
python3 -m scripts.run_tests --run-slow --run-matlab
```

## Bundled Examples

Run all curated examples:

```bash
python3 -m scripts.run_examples
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

Generate the bundled regression-report set:

```bash
python3 -m scripts.generate_regression_reports
```

This writes:

- `workspace/reports/phase2_report.json`
- `workspace/reports/phase2_report.md`
- `workspace/reports/phase3_report.json`
- `workspace/reports/phase3_report.md`

## Limitations and Next Steps

Current limitations:

- no plain multi-letter symbol mode
- state-space generation is linear-only
- only a narrow semi-explicit DAE subset is supported
- high-index DAEs are not reduced
- fully implicit DAEs outside the supported normal form are rejected
- no implicit nonlinear derivative solving
- descriptor-preserving support is stronger as an artifact/lowering path than as a default route for reducible linear semi-explicit DAEs

Natural next steps:

- extend the frontend with additional deterministic math functions
- add richer symbol metadata/value configuration
- broaden preserved-constraint DAE coverage without weakening unsupported-boundary diagnostics
- add more failure-focused regression cases
