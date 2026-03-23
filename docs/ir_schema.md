# Shared Normalized IR Schema

All supported front doors normalize into one shared problem wrapper before any downstream classification or DAE routing.

The current schema lives in [pipeline/normalized_problem.py](../pipeline/normalized_problem.py).

## `NormalizedProblem`

Conceptual shape:

```text
NormalizedProblem
- ir_version
- source_type
- source_metadata
- time_variable
- states
- algebraics
- inputs
- parameters
- equations
- assumptions
- derivative_order_info
- canonical_form_metadata
```

Field intent:

- `ir_version`
  Schema version string for diagnostics and future compatibility.
- `source_type`
  One of:
  - `latex`
  - `matlab_symbolic`
  - `matlab_equation_text`
  - `matlab_ode_function`
- `source_metadata`
  Provenance only. Examples: source path, synthetic inline name, front-door label.
- `time_variable`
  Declared independent variable when explicitly provided.
- `states`
  Declared differential state bases or first-order states, depending on the source payload.
- `algebraics`
  Declared algebraic variables.
- `inputs`
  Declared input symbols.
- `parameters`
  Declared parameters or known constants.
- `equations`
  Canonical equations backed by the existing deterministic expression-node IR.
- `assumptions`
  Source-specific hints or future metadata, not a second semantics pipeline.
- `derivative_order_info`
  Deterministic derivative-order map gathered from canonical equations.
- `canonical_form_metadata`
  Simple normalized-problem diagnostics such as whether the input is a semi-explicit candidate.

## `CanonicalEquation`

Conceptual shape:

```text
CanonicalEquation
- lhs_kind
- lhs_symbol
- lhs_expression
- rhs_expression
- original_text
- source_index
```

Field intent:

- `lhs_kind`
  One of:
  - `derivative`
  - `algebraic_zero`
  - `assignment`
  - `expression`
- `lhs_symbol`
  Convenience symbol name when the lhs is a simple symbol or derivative base.
- `lhs_expression`
  Canonical deterministic lhs expression node.
- `rhs_expression`
  Canonical deterministic rhs expression node.
- `original_text`
  Optional original front-door string for diagnostics.
- `source_index`
  Optional equation index for diagnostics.

## Relation to Existing IR

The normalized schema does not replace the existing expression-node IR. It wraps it.

Core semantic equation representation remains:

- [EquationNode](../ir/expression_nodes.py)
- [ExpressionNode](../ir/expression_nodes.py)

This is intentional:

- front doors do syntax adaptation
- normalized problems carry declared metadata and provenance
- downstream compilation still consumes the same deterministic equation IR

## Downstream Contract

After normalization, the path is shared:

1. normalize to `NormalizedProblem`
2. merge declared symbol roles into configured symbol metadata
3. classify/reduce/preserve through the existing symbolic pipeline
4. validate the supported route
5. lower to graph or descriptor artifact
6. build or simulate when requested

There is no separate classifier or validator per source type.

## Example

These all normalize to the same core equation structure:

- LaTeX: `\dot{x} = -x + u`
- MATLAB symbolic: `diff(x,t) == -x + u`
- MATLAB text: `xdot = -x + u`
- MATLAB ODE function: `rhs = ["-x(1) + u(1)"]`

The normalized canonical equation becomes the same deterministic derivative equation:

```text
D1_x = -x + u
```

with differing `source_type` and provenance only.
