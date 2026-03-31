# Campaign Prompt: Add Matrix / Vector MATLAB-Symbolic System Support

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of making `matlabv2native` handle matrix- and vector-form MATLAB symbolic systems, not just scalar equation lists.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoints, including the current latest checkpoint:

- baseline checkpoint: `c9d4aab`
- phase-1 scaffold checkpoint: `5d78fec`
- phase-2 explicit-ODE parity preview checkpoint: `c0e6f1b`
- phase-3 native explicit-ODE lowering checkpoint: `5265910`
- phase-4 MATLAB-reference anchor checkpoint: `da5e18a`
- phase-5 runtime/parity split checkpoint: `f2899d0`
- phase-6 parity-expansion checkpoint: `2891a9b`
- phase-7 square/coupled parity checkpoint: `f43229c`
- phase-8 symbolic-recognition checkpoint: `0979fca`
- phase-9 nonlinear symbolic source checkpoint: `d9833b3`
- phase-10 native affine RHS checkpoint: `2ef2957`
- phase-11 nonlinear symbolic-family checkpoint: `2999600`
- phase-12 unary-math symbolic-family checkpoint: `dbd12d9`
- phase-13 complex benchmark checkpoint: `396cb2d`
- phase-14 acrobot benchmark checkpoint: `638d6e7`
- phase-15 bounded native DAE symbolic route checkpoint: `dc71d2d`
- phase-16 native pure-time RHS lowering checkpoint: `0a9224b`

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed symbolic/native-runtime work.

## Scope Lock

This campaign is only about:

- the `matlab_symbolic` front door
- matrix / vector symbolic equation intake
- scalarization of matrix-form systems into the existing native pipeline
- preserving user-declared state ordering and system structure
- routing matrix-form systems into the existing explicit-ODE and bounded-DAE native paths when valid

Do not broaden this campaign into:

- LaTeX parity
- equation-text parity
- structured ODE-spec parity
- broad Python-parity work
- unrelated UI or performance tuning

Python must not regress, but Python is not the target. The target is making MATLAB users able to write matrix/vector symbolic systems naturally and still get the native path.

## Current State You Must Respect

The repo already has:

- the existing Python backend, which must remain intact
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for supported native cases
  - default runtime execution for supported symbolic native cases without requiring Python build/sim
  - explicit Python parity mode through `ParityMode="python"`
  - additive timing fields for preview/build/sim/reference/parity/total wall time
  - committed nonlinear benchmark runtime coverage for:
    - cart-pendulum
    - planar quadrotor
    - acrobot
  - bounded reducible DAE support for one algebraic variable solved from one algebraic equation before native explicit-ODE lowering
  - native pure-time RHS lowering for recognized time-only expressions such as `sin(t)` and `t + 1`
  - direct symbolic recognition and runtime-native support for:
    - constant
    - step / delayed step
    - pulse
    - ramp
    - sine
    - square
    - saturation
    - dead zone
    - sign
    - abs
    - min/max
    - atan
    - atan2
    - exp
    - log
    - sqrt
  - runtime-native expression/input-spec support for:
    - sawtooth
    - triangle
  - fallback `MATLAB Function` source/RHS lowering for unsupported expressions inside the native explicit-ODE lane
  - delegation outside the current native explicit-ODE lane

Current docs to keep updated:

- [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)
- [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)

Current main test surface:

- `backend/tests/test_backend_integration.py`

## Core Strategic Goal

Make `matlabv2native` accept matrix- and vector-form MATLAB symbolic systems and normalize them into the existing native pipeline.

The campaign succeeds only if a MATLAB user can write something like:

```matlab
syms x1(t) x2(t) x3(t) x4(t) x5(t)
X = [x1; x2; x3; x4; x5];
A = [...];
eqns = diff(X,t) == A*X;
out = matlabv2native.generate(eqns, 'State', {'x1','x2','x3','x4','x5'});
```

and the system:

- understands that as a 5-state system
- preserves the intended state order
- scalarizes it correctly
- routes it into the native explicit-ODE path when valid

This campaign is not complete if matrix systems still require the user to rewrite everything manually into scalar equation lists.

## Mission

Advance `matlabv2native` from “scalar symbolic equations only” to “matrix/vector symbolic systems normalized into the same native backend.”

You must close gaps in:

- matrix/vector symbolic intake
- scalarization / flattening
- state-order preservation
- route classification after scalarization
- validation coverage and documentation clarity

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while widening MATLAB-symbolic intake.
5. Every new MATLAB-native capability must have automated tests.
6. Every generated model must still simulate and validate.
7. Do not weaken MATLAB-reference validation to make support claims easier.
8. Do not claim broad matrix-symbolic support unless scalarization and route behavior are actually tested.
9. Do not overclaim `symmatrix` or other MATLAB object classes if MATLAB representation details make them impractical; document the exact accepted forms instead.
10. If a matrix-form system lands outside the current explicit-ODE / bounded-DAE native path, make the delegation or unsupported reason explicit.

## Git / Push Discipline

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

## Primary Objectives For This Campaign

Close these gaps in this order:

1. matrix/vector symbolic intake normalization
2. user-declared scalar state order preservation for matrix systems
3. native explicit-ODE route support for scalarized matrix systems
4. bounded DAE route support after scalarization where valid
5. explicit delegation/unsupported metadata for matrix systems outside the native route

At the same time:

- keep the existing scalar symbolic path stable
- keep the complex benchmark anchors green
- keep `MATLAB Function` fallback and delegation intentional

## Required Major Workstreams

### Workstream 1: Probe Actual MATLAB Matrix-Symbolic Forms

Before implementing anything, determine which matrix/vector forms MATLAB actually hands to the native layer cleanly.

At minimum probe:

- column-vector equation arrays:
  - `eqns = [diff(x1,t)==...; diff(x2,t)==...]`
- vector-state forms:
  - `X = [x1; x2; ...]; diff(X,t) == F(X,t)`
- matrix multiplication forms:
  - `diff(X,t) == A*X + B*u`
- whether MATLAB presents these as plain `sym` arrays, symbolic equalities, or something else
- whether `symmatrix` is relevant here or a distraction

Document the exact accepted representations.

Do not guess.

### Workstream 2: Matrix / Vector Scalarization Layer

Add an additive normalization layer before the current native preview path.

That layer must:

1. detect accepted matrix/vector symbolic equation forms
2. flatten them into scalar symbolic equations
3. flatten or resolve the corresponding scalar state basis
4. preserve a deterministic, user-visible state order
5. pass the scalarized result into the existing native explicit-ODE / bounded-DAE preview and lowering path

Requirements:

- preserve the user-provided order when `State` / `States` is explicitly passed
- if state order is inferred, make the inference deterministic and documented
- do not silently alphabetize matrix systems if the user gave a state list

### Workstream 3: Explicit-ODE Matrix Route

For matrix/vector symbolic systems that become explicit ODEs after scalarization:

1. ensure native preview classifies them as explicit ODEs
2. ensure native lowering and simulation work
3. ensure MATLAB-reference validation works
4. ensure result structs expose the correct flattened first-order state order

At minimum support:

- linear matrix systems like `diff(X,t) == A*X`
- affine matrix systems like `diff(X,t) == A*X + B*u`
- coupled nonlinear vector systems written in vector form, if MATLAB symbolic representation remains flattenable

### Workstream 4: Matrix + DAE Boundary

After scalarization, route matrix/vector systems through the current bounded-DAE logic when valid.

At minimum:

1. test one reducible matrix/vector algebraic system that becomes native after elimination
2. test one matrix/vector algebraic system that should still delegate
3. make route/result metadata explicit

Do not overclaim broad matrix DAE support if only a subset is real.

### Workstream 5: Result Metadata And User-Facing Clarity

For matrix/vector symbolic systems, make sure the result surface is explicit about:

- original representation kind
- scalarized equation count
- flattened state order
- route classification
- whether the system stayed native, used bounded fallback, delegated, or is unsupported

If adding a small new metadata field makes this clearer, do it additively.

### Workstream 6: Benchmark-Style Anchors

Add at least two committed regression anchors:

- one matrix/vector explicit-ODE benchmark that builds natively
- one matrix/vector DAE/algebraic benchmark that is either natively reduced or explicitly delegated

These should become “don’t regress” anchors like the current scalar benchmark systems.

## Required MATLAB-Symbolic Coverage Matrix

At minimum, maintain/update coverage for these shapes:

- scalar explicit ODE
- coupled explicit ODE system
- matrix/vector explicit ODE system
- matrix/vector affine system with external input
- reducible matrix/vector DAE/algebraic system
- irreducible matrix/vector algebraic system

For each case, track:

1. accepted MATLAB symbolic representation
2. scalarization support
3. route classification
4. runtime-native support
5. MATLAB-reference support
6. fallback/delegation status
7. flattened state order behavior
8. validation result
9. whether Python is required in the hot path

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- route/preview tests where practical

Minimum expectations for this campaign:

- a committed test for a 3-to-5-state vector-form explicit ODE system
- a committed test for a matrix-form linear system like `diff(X,t) == A*X`
- a committed test that explicit `State` order is preserved for matrix/vector intake
- a committed test for a matrix/vector affine input system
- a committed reducible matrix/vector DAE route test
- a committed irreducible matrix/vector delegated-route test
- tests proving result metadata exposes the flattened state order and route boundary

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current

Document explicitly:

- which matrix/vector MATLAB symbolic forms are accepted
- whether `symmatrix` is actually supported or intentionally out of scope
- how scalarization works
- how state order is determined
- which matrix/vector routes are native vs delegated
- which matrix/vector DAE/algebraic routes are still bounded or delegated

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- claim matrix/vector support without tests
- silently reorder user-provided states
- widen intake without validating the scalarized/native result
- make route behavior for matrix systems implicit or ambiguous
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which matrix/vector forms are now accepted
- which routes are now native vs delegated
- how flattened state order behaves
- what still blocks broad matrix-symbolic support

## Concrete First Step

Start with the smallest defensible matrix/vector slice:

1. probe actual MATLAB symbolic representations for:
   - `diff(X,t) == A*X`
   - `diff(X,t) == A*X + B*u`
2. implement scalarization for accepted vector-form explicit ODEs
3. add a committed regression test for a 3-to-5-state matrix/vector system
4. preserve explicit user-declared state order
5. update the docs honestly

Only after that is clean and green should you widen to matrix/vector DAE/algebraic cases.
