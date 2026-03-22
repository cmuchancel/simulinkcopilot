# DAE Support Architecture

This repo does not claim broad arbitrary DAE support. It supports a narrow, explicit set of semi-explicit DAE routes and rejects unsupported structures with specific diagnostics.

Input note:

- The repo now accepts multiple front doors (`latex`, `matlab_symbolic`, `matlab_equation_text`, `matlab_ode_function`).
- That broadens input coverage, not DAE-theory coverage.
- All supported front doors normalize into the same shared IR before the DAE classifier runs.

## Supported Classes

- `explicit_ode`
  No algebraic structure remains after symbolic analysis.
- `reducible_semi_explicit_dae`
  Algebraic variables can be solved deterministically and substituted away before the explicit ODE path.
- `nonlinear_preserved_semi_explicit_dae`
  First-order semi-explicit systems of the form `x' = f(x, z, u, p, t)` and `0 = g(x, z, u, p, t)` for the currently supported nonlinear preserved subset.
- `linear_descriptor_dae`
  Descriptor-form artifacts for first-order linear semi-explicit DAEs, with preserved-constraint lowering support where the descriptor route is selected.
- `unsupported_dae`
  Higher-index, structurally singular, non-square, or otherwise unsupported algebraic systems.

## Decision Tree

1. Parse and normalize the supported front-door input into one shared normalized problem.
2. Extract:
   - differential states
   - derivative-derived states
   - inputs
   - parameters
   - algebraic-variable candidates
3. Partition equations into:
   - dynamic equations
   - explicit algebraic helper definitions
   - true algebraic constraints
4. Inline explicit helper definitions.
5. Attempt deterministic semi-explicit DAE reduction.
   - if all algebraic structure disappears, the system becomes `explicit_ode` or `reducible_semi_explicit_dae`
   - if residual algebraic constraints remain, continue to preserved-form checks
6. Build preserved-form metadata for supported first-order semi-explicit systems.
   - if the preserved form is valid and nonlinear, classify as `nonlinear_preserved_semi_explicit_dae`
   - if a linear descriptor artifact is available for the preserved form, the descriptor route is available
   - if the preserved form is invalid or unsupported, classify as `unsupported_dae`

## Route Summary

### Explicit ODE route

Used for:
- `explicit_ode`
- `reducible_semi_explicit_dae`

Artifacts:
- solved derivatives
- first-order system
- explicit nonlinear form
- optional state-space system when linear
- deterministic graph dictionary

Validation:
- Python ODE simulation
- optional Python state-space simulation
- optional Simulink comparison

### Preserved nonlinear DAE route

Used for:
- `nonlinear_preserved_semi_explicit_dae`

Artifacts:
- typed semi-explicit DAE system
- preserved algebraic residual equations
- preserved graph with `algebraic_chains`

Validation:
- consistent initialization
- algebraic residual evaluation
- local algebraic-variable solve during Python simulation
- optional Simulink comparison against Python DAE trajectories

Assumptions:
- first-order differential states only
- square algebraic subsystem
- structurally assignable algebraic residuals
- local numeric algebraic solve is acceptable for the supported subset

### Descriptor route

Used for:
- descriptor-form linear semi-explicit DAEs where the descriptor artifact is the correct lowering target
- reducible linear semi-explicit balance cases that still expose a descriptor artifact even when the explicit ODE route is selected for simulation

Artifacts:
- descriptor matrices
- differential/algebraic variable partition
- preserved algebraic-constraint lowering path

Validation:
- descriptor artifact construction
- optional Simulink lowering/build
- Python validation parity on the supported subset through the DAE-native validation path

## Explicit Unsupported Boundary

The repo currently rejects:

- higher-index DAEs without index reduction
- fully implicit DAEs outside the supported semi-explicit normal form
- structurally singular or non-square preserved algebraic subsystems
- systems whose variable partitioning is ambiguous
- implicit nonlinear derivative coupling with non-unique solves

These rejections are intentional. The code should fail explicitly rather than silently widening support claims.
