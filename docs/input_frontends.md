# Input Front Doors

This repo now supports four parallel front doors:

- `latex`
- `matlab_symbolic`
- `matlab_equation_text`
- `matlab_ode_function`

These are syntax adapters only. They do not create separate downstream math pipelines.

All supported inputs normalize into the same shared [NormalizedProblem schema](/Users/chancelavoie/Desktop/simulinkcopilot/docs/ir_schema.md), then reuse the same downstream stages:

1. normalize
2. classify
3. reduce or preserve
4. validate
5. lower or build artifact

Important scope note:

- This change broadens input coverage, not DAE-theory coverage.
- The existing ODE and DAE support boundary is unchanged.
- Unsupported cases still fail honestly and deterministically.

## `latex`

Existing restricted LaTeX input.

Examples:

```latex
\dot{x} = -x + u
```

```latex
\dot{x} = -x + z
z^3 + z - x = 0
```

## `matlab_symbolic`

MATLAB Symbolic Math Toolbox-style equation strings.

Supported examples:

```json
{
  "source_type": "matlab_symbolic",
  "equations": [
    "diff(x,t) == -x + z + u",
    "0 == z^3 + z - x"
  ],
  "states": ["x"],
  "algebraics": ["z"],
  "inputs": ["u"],
  "parameters": [],
  "time_variable": "t"
}
```

Notes:

- `diff(x,t)` and `diff(x,t,2)` are normalized into the same derivative IR used by the LaTeX path.
- `==` and `=` are both accepted as equality operators.
- Multiple time variables inside `diff(...)` are rejected.

## `matlab_equation_text`

MATLAB-ish equation strings that are still structured enough to parse deterministically.

Supported examples:

```json
{
  "source_type": "matlab_equation_text",
  "equations": [
    "xdot = z",
    "0 = z + sin(x)"
  ],
  "states": ["x"],
  "algebraics": ["z"],
  "inputs": [],
  "parameters": [],
  "time_variable": "t"
}
```

Supported first-order derivative aliases include:

- `xdot`
- `x_dot`
- `dxdt`

Important constraint:

- If derivative naming is ambiguous, the parser rejects the input and asks for explicit states or a `derivative_map`.
- The parser does not guess whether a token is a derivative or an ordinary variable.

## `matlab_ode_function`

This route is only for structured exported ODE-function specifications.

Supported `component_expressions` shape:

```json
{
  "source_type": "matlab_ode_function",
  "function_spec": {
    "representation": "component_expressions",
    "outputs": ["dx1", "dx2"],
    "expressions": [
      "-x1 + u1",
      "x1 - x2"
    ]
  },
  "state_names": ["x1", "x2"],
  "input_names": ["u1"],
  "parameter_names": [],
  "time_variable": "t"
}
```

Supported `vector_rhs` shape:

```json
{
  "source_type": "matlab_ode_function",
  "function_spec": {
    "representation": "vector_rhs",
    "state_vector_name": "x",
    "input_vector_name": "u",
    "rhs": [
      "-x(1) + u(1)",
      "x(1) - x(2)"
    ]
  },
  "state_names": ["x1", "x2"],
  "input_names": ["u1"],
  "parameter_names": [],
  "time_variable": "t"
}
```

Explicitly unsupported:

- opaque function handles
- arbitrary MATLAB source parsing
- black-box closures with no inspectable exported RHS

Typical rejection:

```text
matlab_ode_function currently supports only structured exported RHS expressions, not opaque function handles or arbitrary MATLAB source.
```

## Shared Behavior

Equivalent systems written through different front doors should converge to the same core normalized representation and the same downstream route classification.

Examples:

Explicit ODE:

- LaTeX: `\dot{x} = -x + u`
- MATLAB symbolic: `diff(x,t) == -x + u`
- MATLAB text: `xdot = -x + u`
- MATLAB ODE function: `rhs = ["-x(1) + u(1)"]`

Reducible semi-explicit DAE:

- LaTeX: `\dot{x} = z`, `z + \sin(x) = 0`
- MATLAB symbolic: `diff(x,t) == z`, `0 == z + sin(x)`
- MATLAB text: `xdot = z`, `0 = z + sin(x)`

Preserved nonlinear semi-explicit DAE:

- LaTeX: `\dot{x} = -x + z`, `z^3 + z - x = 0`
- MATLAB symbolic: `diff(x,t) == -x + z`, `0 == z^3 + z - x`
- MATLAB text: `xdot = -x + z`, `0 = z^3 + z - x`

## Diagnostics

Representative precise failures:

- `matlab_equation_text parse failed: could not determine whether 'xdot' is a state derivative or an ordinary variable; provide explicit states/derivative map`
- `matlab_ode_function currently supports only structured exported RHS expressions, not opaque function handles or arbitrary MATLAB source`
- `matlab_symbolic parse failed: diff() uses multiple time variables [...]`

See [docs/dae_support.md](/Users/chancelavoie/Desktop/simulinkcopilot/docs/dae_support.md) for the downstream ODE/DAE route boundary.
