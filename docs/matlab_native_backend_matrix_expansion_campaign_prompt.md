# Campaign Prompt: Expand the Standalone-Native MATLAB Runtime Matrix

Use this prompt to continue the native MATLAB backend campaign from the current repo state after the runtime/parity split checkpoint.

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

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed runtime/parity split work.

## Current State You Must Respect

The repo already has:

- the existing Python backend, which must remain intact for legacy workflows and parity/debug use
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native explicit-ODE Simulink lowering for current anchor cases
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for current anchor cases
  - default runtime execution for native-eligible anchor cases without requiring a Python build/sim
  - explicit Python parity mode through `ParityMode="python"`
  - additive timing fields for preview/build/sim/reference/parity/total wall time

Current standalone-native runtime coverage is still narrow:

- constant input
- step / delayed step
- unsupported symbolic input via `MATLAB Function` source fallback

Current focused tests already green at handoff:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `7 passed, 3 deselected`

## Core Strategic Problem You Must Address

The architecture is now in the right shape, but the standalone-native runtime matrix is too narrow to matter much in practice.

Right now:

- the default native runtime path is real for the anchor cases
- MATLAB numerical-reference validation is real for the anchor cases
- Python has been removed from the hot path for those anchor cases

But:

- most useful input families are not yet runtime-native
- the MATLAB numerical oracle does not yet cover the broader supported family set
- the native builder still overuses `MATLAB Function` blocks for RHS lowering
- the only public comparison API is still Python-oriented and preview-heavy

The next milestone is:

- make `matlabv2native` meaningfully useful as a standalone runtime path across a broader explicit-ODE input matrix
- keep Python parity available, but separate and heavy
- make the runtime-native surface clearly measurable and documented

## Mission

Advance `matlabv2native` from “runtime-native for two anchor cases” to “runtime-native for a meaningful explicit-ODE family set” by doing all of the following:

- widen native Simulink input-source lowering and MATLAB numerical-oracle input evaluation together
- reduce `MATLAB Function` fallback usage in both source lowering and RHS lowering where native block composition exists
- add a dedicated heavy comparison API for native-vs-Python-vs-reference checks
- publish a runtime/parity coverage ledger so supported vs delegated cases are explicit
- keep Python out of the default hot path for cases that are declared runtime-native

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently reintroduce Python into the default runtime path for cases already marked standalone-native.
5. Do not claim runtime-native support for an input family unless both native Simulink lowering and MATLAB numerical-oracle evaluation exist and are tested.
6. Every generated model must still simulate and validate.
7. Do not weaken validation to make widening easier.
8. If a family is not trustworthy yet, keep it delegated or parity-gated and say so explicitly.
9. Do not introduce a public build-only escape hatch.
10. Preserve Git discipline: test, commit, push after each stable phase.

## Git / Push Discipline

You are continuing on an already-pushed branch. Preserve that discipline.

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

If you get blocked, push the last stable checkpoint before continuing.

If the remote or auth breaks, report that explicitly and continue with local commits, but do not pretend pushes happened.

## Primary Objective for This Continuation

Implement the next real runtime-expansion step in `matlabv2native`:

- widen the standalone-native runtime matrix beyond constant/step/fallback
- keep MATLAB-reference validation as the default validation surface
- keep Python parity explicit and separate
- reduce unnecessary `MATLAB Function` usage
- document the resulting coverage clearly

You do not need full native DAE parity immediately. Explicit ODEs still come first.

## Required Next Phases

### Phase 6A: Widen the Runtime-Native Input Matrix

Widen native support in both:

1. native Simulink source lowering
2. MATLAB numerical-oracle input evaluation

At minimum, add these families in both places:

- pulse
- ramp
- sine
- square
- sawtooth
- triangle
- saturation
- dead zone
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`

Requirements:

- do not mark a family runtime-native unless both lowering and oracle support exist
- if a native Simulink block exists, use it
- use `MATLAB Function` fallback only when direct native block composition is not possible
- preserve user-visible/editable inputs and parameters
- keep the default runtime path Python-free for the families you promote to runtime-native

### Phase 6B: Reduce `MATLAB Function` Fallback in RHS Lowering

The current native builder still overuses `MATLAB Function` blocks for RHS expressions.

Reduce this intentionally for explicit ODE anchor-style systems.

At minimum, lower directly where practical with:

- Sum
- Gain
- Product
- reciprocal / division patterns where safe
- Math Function
- Trigonometric Function
- Saturation
- Dead Zone

Requirements:

- keep diagrams readable
- keep `MATLAB Function` only as a fallback
- add tests that prove the converted cases now use native block families

### Phase 6C: Add a Heavy Comparison API

The default runtime path should remain lean. Add or expand a separate heavy comparison API.

You must either:

- expand `matlabv2native.compareWithPython(...)`

or

- add a new additive API such as:
  - `matlabv2native.compareAll(...)`
  - `matlabv2native.compareWithParity(...)`

This API should compare, for native-eligible explicit ODEs:

- route/classification
- first-order state set/order
- first-order RHS semantics where practical
- native source block family
- MATLAB-reference validation results
- Python parity results when requested
- native vs Python trace agreement

Key design rule:

- default runtime path stays lean
- comparison API can stay heavy

### Phase 6D: Add a Runtime/Parity Coverage Ledger

Create a maintained doc that explicitly tracks which families are:

- runtime-native
- MATLAB-reference supported
- Python-parity supported
- still delegated

Start with:

- constant
- step
- delayed step
- pulse
- ramp
- sine
- square
- sawtooth
- triangle
- saturation
- dead zone
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`
- one unsupported symbolic expression using `MATLAB Function` fallback

For each family, track:

1. native source block family
2. native runtime validation against MATLAB reference
3. optional Python parity result
4. whether Python is required in the hot path
5. whether the family is still delegated

### Phase 6E: Strengthen Performance Visibility

You already have timing fields. Make them genuinely useful.

Requirements:

- ensure timing fields are present for runtime-native cases and explicit parity mode
- document what each field measures
- add at least one test that verifies the presence of timing fields in runtime mode
- add at least one test that verifies Python parity timing is only populated when parity mode is requested

Do not hardcode speed thresholds. The goal is visibility, not brittle benchmarks.

## Required Runtime/Parity Matrix

At minimum, advance the matrix to cover:

- constant
- step
- delayed step
- pulse
- ramp
- sine
- saturation
- `atan`
- `exp`
- one unsupported symbolic expression using `MATLAB Function` fallback

If more families can be completed cleanly in the same phase, include them, but do not overclaim partial support.

For each promoted family, prove:

1. native source block family is what you expect
2. native runtime validation passes against MATLAB reference
3. Python is not required in the hot path
4. explicit Python parity remains available

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- parity tests specific to `matlabv2native`
- timing-field contract tests where practical

Do not remove existing tests.

You must keep these green:

- existing Python tests you touch
- `matlabv1` integration tests
- `matlabv2native` tests you add

Minimum expectations for this continuation:

- at least one widened-input integration test that is runtime-native and MATLAB-reference validated
- at least one explicit parity-mode test for a widened input family
- at least one test showing a reduced `MATLAB Function` footprint for an RHS case
- at least one timing-field contract test
- at least one coverage-ledger/doc update committed with the code

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- add a runtime/parity coverage ledger doc if it does not already exist
- document which families are now truly runtime-native
- document which families still require parity mode or delegation
- document any remaining reliance on `MATLAB Function` fallback
- document the comparison API boundary: lean runtime vs heavy parity

Document explicitly:

- which new families no longer require Python during normal execution
- which new families still delegate
- which fields in the result struct indicate runtime mode vs parity mode

## Failure Conditions

You fail this continuation if you:

- break current Python behavior
- break `matlabv1`
- silently reintroduce Python into the default runtime path for runtime-native cases
- claim runtime-native support for a family without MATLAB-reference validation
- widen support in lowering but not in the MATLAB numerical oracle
- leave coverage status implicit instead of documented
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which families are now runtime-native
- which families still require parity mode or delegation
- what `MATLAB Function` usage was eliminated
- what still blocks widening the matrix further

## Concrete First Step

Start by promoting the next smallest, defensible family set to runtime-native:

- `pulse`
- `ramp`
- `sine`

For those families:

1. add native Simulink lowering
2. add MATLAB numerical-oracle evaluation
3. validate them in runtime mode without Python in the loop
4. verify explicit Python parity still works when requested
5. update the coverage ledger

Only after that family set is clean and green should you widen further to square/sawtooth/triangle, saturation/dead-zone, and unary math families like `atan`, `exp`, `log`, and `sqrt`.
