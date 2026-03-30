# Campaign Prompt: Close Direct-Symbolic Repeating-Sequence And DAE Gaps

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of closing the two remaining credibility gaps for the `matlab_symbolic` front door:

- direct-symbolic `sawtooth` / `triangle`
- DAE / algebraic MATLAB-symbolic systems

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoints:

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

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed symbolic/native-runtime work.

## Scope Lock

This campaign is only about:

- the `matlab_symbolic` front door
- direct symbolic-expression intake for waveform/repeating-sequence families
- DAE / algebraic symbolic systems
- native runtime generation quality, route selection, and boundary clarity

Do not broaden this campaign into:

- LaTeX parity
- equation-text parity
- structured ODE-spec parity
- broad Python-parity work
- unrelated performance tuning

Python must not regress, but Python is not the target of this campaign. The target is a complete and honest MATLAB-symbolic story.

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
  - committed complex-system runtime coverage for:
    - cart-pendulum
    - planar quadrotor
    - acrobot
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

Current focused tests/documentation already exist in:

- [docs/matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)
- [docs/matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)
- `backend/tests/test_backend_integration.py`

## Core Strategic Goal

Finish the last two major MATLAB-symbolic gaps:

1. make `sawtooth` and `triangle` truly direct-symbolic native families if MATLAB symbolic behavior allows it cleanly
2. make DAE / algebraic symbolic systems land in an intentional, test-backed route instead of the current vague delegated boundary

This campaign succeeds only if the user can tell, from tests and docs, exactly what happens when they write:

- a raw symbolic `sawtooth(...)` or `triangle(...)`
- a symbolic system with algebraic constraints or mass-matrix style structure

## Mission

Advance `matlabv2native` from “strong explicit-ODE native backend” to “honest and substantially broader MATLAB-symbolic backend.”

You must close gaps in:

- direct symbolic recognition
- route selection
- native lowering quality
- fallback quality
- documentation clarity

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while broadening MATLAB-symbolic support.
5. Every new MATLAB-native capability must have automated tests.
6. Every generated model must still simulate and validate.
7. Do not weaken MATLAB-reference validation to make support claims easier.
8. Do not mark `sawtooth` or `triangle` as direct-symbolic native unless raw symbolic intake is actually tested.
9. Do not claim DAE/native algebraic support unless a real route, lowering strategy, and validation strategy exist and are tested.
10. If DAE support still cannot be made trustworthy in this phase, document and test the exact delegated/fallback boundary instead of hand-waving it.

## Git / Push Discipline

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

## Primary Objectives For This Campaign

Close these gaps in this order:

1. direct-symbolic `sawtooth`
2. direct-symbolic `triangle`
3. DAE / algebraic preview classification
4. DAE / algebraic generation path
5. DAE / algebraic validation and fallback behavior

At the same time:

- keep the existing explicit-ODE native path stable
- keep complex benchmark anchors green
- keep `MATLAB Function` fallback only where it is the intentional design

## Required Major Workstreams

### Workstream 1: Direct-Symbolic `sawtooth` / `triangle`

Close the current gap where these families are runtime-native only through expression/input-spec normalization and are not yet trusted as broad direct-symbolic families.

Requirements:

1. Teach native recognition to handle raw symbolic `sawtooth(...)` and `triangle(...)` forms if MATLAB preserves them in a recognizable canonical form.
2. If MATLAB rewrites them into another symbolic shape, normalize that canonical form back into a native repeating-sequence family.
3. Add native lowering that preserves readable block structure and editable parameters.
4. Add MATLAB-reference validation coverage.
5. Update docs to say either:
   - direct symbolic-native now works
   - or only specific canonical forms are supported

Do not claim broad direct-symbolic support unless the tests prove it.

### Workstream 2: DAE / Algebraic Route Design

The current native analyzer is strongest for explicit ODEs and leaves DAE/algebraic systems vague.

You must make this route intentional.

At minimum:

1. identify the DAE/algebraic shapes currently reaching `matlab_symbolic`
2. classify them into:
   - reducible-to-explicit natively
   - native runtime with intentional algebraic/fallback blocks
   - delegated to Python
   - unsupported with explicit user-facing reason
3. encode that route choice in preview/build results
4. test the route choice
5. document the route choice

If a DAE can be reduced to an explicit first-order system natively and validated honestly, do that.

If a DAE cannot be made native yet, make the delegation explicit and structured instead of accidental.

### Workstream 3: Native DAE / Algebraic Lowering

For the subset of DAE/algebraic systems you choose to support natively, implement a real lowering strategy.

Possible acceptable strategies include:

- symbolic elimination/reduction to explicit ODE before native generation
- mass-matrix aware reduction when cleanly derivable
- intentional algebraic subgraph lowering with standard Simulink blocks
- `MATLAB Function` fallback only for the irreducible algebraic subexpression, not the whole model, when that keeps the model honest and simulatable

Requirements:

1. preserve readable structure where possible
2. validate against a MATLAB numerical reference or another disciplined MATLAB-native oracle
3. keep the route/result metadata explicit

### Workstream 4: Fallback Boundary Quality

Make the fallback behavior explicit and robust for both target gaps.

At minimum:

- if raw symbolic `sawtooth` / `triangle` still cannot be matched, ensure the fallback is deliberate and tested
- if a DAE is not natively supported, ensure the result says why
- do not silently drift between native, delegated, and `MATLAB Function` fallback paths

The user should be able to see whether a model is:

- `native_runtime_only`
- native-with-function-fallback
- delegated
- unsupported

### Workstream 5: Benchmark Anchors

Add at least one benchmark-style regression for each new route boundary:

- one direct-symbolic repeating-sequence benchmark
- one DAE/algebraic benchmark or intentionally delegated DAE benchmark

These should become “don’t regress” anchors just like:

- cart-pendulum
- planar quadrotor
- acrobot

## Required MATLAB-Symbolic Coverage Matrix

At minimum, maintain/update coverage for these shapes:

- first-order explicit scalar ODE
- second-order scalar ODE reduced to first order
- coupled explicit ODE system
- complex nonlinear benchmark systems
- DAE / algebraic symbolic system
- unsupported symbolic fallback case

At minimum, maintain/update coverage for these families/routes:

- sawtooth
- triangle
- reducible DAE
- irreducible DAE/algebraic system
- unsupported/delegated DAE case

For each case, track:

1. route classification
2. runtime-native support
3. MATLAB-reference support
4. direct symbolic recognition
5. struct/input-spec native support
6. fallback/delegation status
7. source/RHS block family
8. validation result
9. whether Python is required in the hot path

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- route/preview tests where practical

Minimum expectations for this campaign:

- a committed test proving direct-symbolic `sawtooth(...)` behavior
- a committed test proving direct-symbolic `triangle(...)` behavior
- native source-block-family assertions for those cases when supported
- a committed DAE/algebraic route test
- at least one committed DAE benchmark-style test
- tests proving whether the DAE case is:
  - natively reduced
  - native with bounded fallback
  - delegated
  - unsupported
- tests proving result metadata makes that boundary explicit

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current

Document explicitly:

- whether `sawtooth` is now direct symbolic-native
- whether `triangle` is now direct symbolic-native
- which canonical symbolic forms are recognized
- which DAE/algebraic routes are now supported natively
- which DAE/algebraic routes still delegate
- where `MATLAB Function` fallback is still intentional

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- claim direct-symbolic `sawtooth` / `triangle` support without tests
- claim DAE/native algebraic support without a real route and validation story
- leave DAE behavior implicit or ambiguous
- silently reintroduce Python into the runtime path for cases claimed native
- widen lowering without widening the validation/oracle surface to match
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- whether `sawtooth` and `triangle` are now direct-symbolic native or still bounded
- which DAE/algebraic routes are now native vs delegated
- what fallback behavior remains intentional
- what still blocks a complete MATLAB-symbolic story

## Concrete First Step

Start with the smaller but high-value direct-symbolic gap:

1. probe raw symbolic `sawtooth(...)` and `triangle(...)` in MATLAB to see their actual canonical symbolic form
2. normalize those forms back into native repeating-sequence specs if possible
3. add committed tests for those direct-symbolic forms
4. update the ledger honestly

Then move immediately to the DAE route:

1. pick one reducible DAE/algebraic benchmark
2. pick one irreducible/algebraic benchmark
3. make the route choice explicit for both
4. add committed tests
5. update the docs

Do not leave this campaign with `sawtooth` / `triangle` still vague and DAE behavior still hand-waved.
