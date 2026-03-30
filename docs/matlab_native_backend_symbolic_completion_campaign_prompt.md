# Campaign Prompt: Finish MATLAB-Symbolic Native Explicit-ODE Coverage

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of finishing the remaining high-value `matlab_symbolic -> Simulink` gaps for explicit ODE workflows.

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

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed symbolic/native-runtime work.

## Scope Lock

This campaign is only about:

- the `matlab_symbolic` front door
- MATLAB users writing symbolic equations and symbolic input expressions
- generating native Simulink models for explicit ODE workflows
- making the generated models readable and truly native

This campaign is not about:

- LaTeX parity
- equation-text parity
- structured ODE-spec parity
- broad Python parity work
- DAE/native algebraic parity

Python still must not regress, but Python is not the target of this campaign. Treat it as legacy/debug scaffolding, not the product goal.

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
  - committed coupled explicit-system runtime coverage
  - direct symbolic recognition and runtime-native support for:
    - constant
    - step / delayed step
    - pulse
    - ramp
    - sine
    - square
    - saturation
    - dead zone
  - runtime-native expression/input-spec support for:
    - sawtooth
    - triangle
  - native affine RHS lowering for simple explicit expressions such as:
    - `-x + u`
    - `x - 2*y`
    - simple constant offsets combined with state/input/parameter signals
  - unsupported symbolic input fallback through `MATLAB Function`

Current focused tests already green at handoff:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `17 passed, 3 deselected, 20 subtests passed`

Current docs to keep updated:

- [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)
- [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)

## Core Strategic Goal

Finish the remaining meaningful MATLAB-symbolic explicit-ODE native coverage so a MATLAB user can write symbolic equations and symbolic input expressions and reliably get:

- a native Simulink model
- readable native source blocks
- readable native RHS blocks
- MATLAB-reference validation
- no Python requirement in the hot path

Do not optimize this campaign around Python parity. Optimize it around shipping a complete and defensible MATLAB-symbolic native path for explicit ODEs.

## Mission

Advance `matlabv2native` from “usable symbolic explicit-ODE native backend” to “nearly complete symbolic explicit-ODE native backend”.

You must focus on:

- remaining symbolic input-family coverage
- symbolic-expression recognition
- native lowering quality
- reducing unnecessary `MATLAB Function` fallback
- keeping the explicit-ODE route strong and honest

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows, even though Python is not the campaign target.
4. Do not silently change semantics while widening MATLAB-symbolic native support.
5. Every new MATLAB-native capability must have automated tests.
6. Every generated model must still simulate and validate.
7. Do not weaken MATLAB-reference validation to make support claims easier.
8. Do not mark a family as runtime-native unless native Simulink lowering and MATLAB numerical-oracle evaluation both exist and are tested.
9. Do not silently reintroduce Python into the default runtime path for runtime-native symbolic cases.
10. Keep `MATLAB Function` fallback only for genuinely unsupported symbolic expressions.

## Git / Push Discipline

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

## Primary Objective For This Campaign

Finish the next remaining MATLAB-symbolic explicit-ODE native families in this order:

1. `sign`
2. `abs`
3. `min/max`
4. `atan`
5. `atan2`
6. `exp`
7. `log`
8. `sqrt`

At the same time:

- keep `sawtooth` / `triangle` honest
- continue reducing unnecessary `MATLAB Function` fallback in the RHS path
- do not waste time on non-symbolic front doors

## Required Major Workstreams

### Workstream 1: Finish The Next Nonlinear Families

Promote these symbolic families in both:

1. native Simulink lowering
2. MATLAB numerical-oracle evaluation

Families:

- `sign`
- `abs`
- `min/max`

Requirements:

- prefer native blocks when they exist
- use `Sign`, `Abs`, `MinMax`, `Sum`, `Gain`, and `Product` before falling back to `MATLAB Function`
- preserve editable user-visible parameters where applicable
- keep the default runtime path Python-free

### Workstream 2: Finish The Unary-Math Families

Promote these symbolic families in both:

1. native Simulink lowering
2. MATLAB numerical-oracle evaluation

Families:

- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`

Requirements:

- use native Math Function / Trigonometric Function blocks where appropriate
- do not claim native support until both lowering and MATLAB-reference evaluation exist

### Workstream 3: Strengthen Symbolic Recognition

For every family you promote, make the symbolic-recognition boundary explicit:

- direct symbolic-native
- struct/input-spec native only
- delegated

The target in this campaign is direct symbolic-native support wherever practical.

Do not spend time making Python parity pretty if that work does not help the MATLAB-symbolic path.

### Workstream 4: Keep Repeating-Sequence Status Honest

For:

- `sawtooth`
- `triangle`

you must do one of:

- harden direct symbolic-native recognition if MATLAB symbolic behavior allows it cleanly

or

- explicitly leave them as expression/input-spec runtime-native only

Do not let this stay vague.

### Workstream 5: Continue Lowering Quality Cleanup

Reduce unnecessary `MATLAB Function` usage in:

- native source lowering
- native RHS lowering

At minimum, keep improving direct native block composition for:

- `Sign`
- `Abs`
- `MinMax`
- `Math Function`
- `Trigonometric Function`
- `Sum`
- `Gain`
- `Product`

If an expression is simple enough to draw with standard Simulink math blocks, do not hide it in a function block.

### Workstream 6: Validation And Runtime Discipline

For every promoted family:

- keep MATLAB numerical reference as the runtime validation oracle
- keep default runtime Python-free
- prove the result in automated tests

If Python parity is missing or imperfect for a family, do not stop the campaign unless it reveals a real semantic bug in the MATLAB-native path.

## Required MATLAB-Symbolic Coverage Matrix

At minimum, maintain/update coverage for these symbolic problem shapes:

- first-order explicit scalar ODE
- second-order scalar ODE reduced to first order
- coupled explicit ODE system
- parameterized explicit ODE
- unsupported symbolic input fallback case

At minimum, maintain/update coverage for these symbolic input families:

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
- sign
- abs
- min/max
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`
- unsupported symbolic expression using `MATLAB Function` fallback

For each family/case, track:

1. runtime-native support
2. MATLAB-reference support
3. symbolic-expression recognition
4. struct-spec native support
5. delegation status
6. native source block family
7. native runtime validation result
8. whether Python is required in the hot path

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- timing-field contract tests where practical

Minimum expectations for this campaign:

- committed tests for every newly promoted symbolic family
- tests proving runtime-native symbolic cases still do not require Python in the hot path
- tests proving symbolic-expression recognition for the families you promote
- tests asserting native block-family choices for at least some promoted source families
- tests asserting simple native RHS expressions stay native and do not regress back to `MATLAB Function`
- tests proving explicit runtime-only or delegated boundaries where support is still incomplete

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current

Document explicitly:

- which symbolic families are runtime-native
- which are direct symbolic-native
- which are struct-spec-only native
- which still delegate
- which still rely on `MATLAB Function` fallback

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- silently reintroduce Python into the default runtime path for runtime-native symbolic cases
- claim symbolic native coverage without tests and docs
- widen Simulink lowering without widening the MATLAB numerical oracle to match
- let `MATLAB Function` fallback keep covering expressions that should now be native
- spread effort into non-symbolic front doors
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which symbolic families are now runtime-native
- which families are direct symbolic-native vs struct-spec-only native
- what `MATLAB Function` usage was eliminated
- what still blocks completion of MATLAB-symbolic explicit-ODE coverage

## Concrete First Step

Start with the highest-value remaining symbolic-native family set:

1. promote `sign`, `abs`, and `min/max`
2. add direct MATLAB symbolic recognition for them where practical
3. lower them with native blocks, not `MATLAB Function`
4. validate them against the MATLAB numerical oracle
5. add tests that inspect the generated model structure
6. update the ledger and architecture doc

Only after that is clean and green should you move to:

- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`

Do not spend this campaign trying to make Python parity mode the center of the design. The target is a complete MATLAB-symbolic native runtime path for explicit ODEs.
