# Campaign Prompt: Close the Next MATLAB-Symbolic Nonlinear Parity Gaps

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of advancing `matlabv2native` toward practical parity with the Python backend for the `matlab_symbolic` front door only.

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

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed symbolic-recognition work.

## Scope Lock

This campaign is specifically about:

- the `matlab_symbolic` front door
- MATLAB users defining symbolic equations and symbolic input expressions in MATLAB
- bringing `matlabv2native` closer to Python-backend coverage for that workflow

Do not spend this campaign on:

- LaTeX parity
- equation-text parity
- structured ODE-spec parity

Those may remain delegated. Keep the campaign tightly scoped to MATLAB symbolic inputs.

## Current State You Must Respect

The repo already has:

- the existing Python backend, which must remain intact
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native explicit-ODE Simulink lowering for the current symbolic native set
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for the current supported native set
  - default runtime execution for current native symbolic cases without requiring Python build/sim
  - explicit Python parity mode through `ParityMode="python"`
  - additive timing fields for preview/build/sim/reference/parity/total wall time
  - committed coupled explicit-system runtime coverage
  - committed coupled explicit-system parity-mode coverage
  - direct symbolic recognition and native runtime/parity coverage for:
    - constant
    - step / delayed step
    - pulse
    - ramp
    - sine
    - square
  - runtime-native expression/input-spec support for:
    - sawtooth
    - triangle
  - unsupported symbolic input fallback through `MATLAB Function`

Current focused tests already green at handoff:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `16 passed, 3 deselected, 18 subtests passed`

Current docs to keep updated:

- [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)
- [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)

## Core Strategic Goal

Bring `matlabv2native` closer to practical parity with the Python backend for MATLAB symbolic workflows by closing the next real symbolic gaps:

- finish the repeating-sequence symbolic boundary honestly
- promote the next nonlinear symbolic source families
- then promote the next unary-math symbolic source families
- keep explicit-ODE route support strong and explicit
- do not overclaim DAE/native algebraic parity

This campaign is not about deleting Python. It is about making the MATLAB-symbolic native path broader and more trustworthy.

## Mission

Advance `matlabv2native` from “waveform-capable symbolic native backend” to “symbolic nonlinear-family native backend”.

You must move the MATLAB-native backend closer to the Python backend in:

- symbolic input-family support
- symbolic-expression recognition
- native lowering quality
- simulation behavior
- MATLAB-reference validation behavior
- parity reporting

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while pursuing MATLAB-symbolic parity.
5. Every new MATLAB-native capability must have automated tests.
6. Every generated model must still simulate and validate.
7. Do not weaken MATLAB-reference validation to make parity easier to claim.
8. Do not mark a symbolic family as runtime-native unless native Simulink lowering and MATLAB numerical-oracle evaluation both exist and are tested.
9. Do not silently reintroduce Python into the default runtime path for runtime-native symbolic cases.
10. Do not claim symbolic parity for a family unless tests and docs prove it.

## Git / Push Discipline

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

## Primary Objective for This Campaign

Close the next MATLAB-symbolic parity gap by doing all of the following:

- decide and document the honest boundary for `sawtooth` / `triangle`
- promote nonlinear symbolic families:
  - `saturation`
  - `dead_zone`
  - `sign`
  - `abs`
  - `min/max`
- then promote unary math symbolic families:
  - `atan`
  - `atan2`
  - `exp`
  - `log`
  - `sqrt`
- keep route support explicit and limited to trustworthy symbolic cases

## Required Major Workstreams

### Workstream 1: Repeating-Sequence Boundary

Settle the current symbolic boundary for:

- `sawtooth`
- `triangle`

You must either:

- make Python parity mode work for their current expression/input-spec path

or

- explicitly leave them runtime-native-only for now and document that boundary in tests and docs

Do not leave this ambiguous.

### Workstream 2: Nonlinear Symbolic Family Promotion

Promote the next symbolic source families in both:

1. native Simulink lowering
2. MATLAB numerical-oracle evaluation

Families:

- `saturation`
- `dead_zone`
- `sign`
- `abs`
- `min/max`

Requirements:

- prefer native Simulink blocks when they exist
- use `MATLAB Function` fallback only when direct composition is not possible
- preserve editable user-visible parameters
- keep default runtime path Python-free for promoted native cases

### Workstream 3: Unary Math Symbolic Family Promotion

Promote the next unary-math symbolic families in both:

1. native Simulink lowering
2. MATLAB numerical-oracle evaluation

Families:

- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`

Requirements:

- compare against Python semantics when parity mode is requested
- do not claim native support without matching oracle coverage

### Workstream 4: Symbolic-Expression Recognition

Strengthen symbolic recognition so promoted nonlinear/math families are detected from MATLAB symbolic expressions where practical.

At minimum, make the recognition boundary explicit for each promoted family:

- direct symbolic-native
- struct/input-spec native only
- delegated

### Workstream 5: Lowering Quality

Reduce unnecessary `MATLAB Function` usage in both:

- native source lowering
- native RHS lowering

Prefer native blocks such as:

- Saturation
- Dead Zone
- Sign
- Abs
- MinMax
- Math Function
- Trigonometric Function
- Sum
- Gain
- Product

### Workstream 6: Validation And Reporting

For promoted symbolic families:

- keep MATLAB numerical reference as the runtime validation oracle
- keep Python parity as optional comparison, not a required runtime dependency
- expose mismatches clearly in the parity surface

If a family is runtime-native but not Python-parity-clean yet, say so explicitly.

## Required MATLAB-Symbolic Parity Matrix

At minimum, maintain coverage for these symbolic problem shapes:

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
3. Python-parity support
4. symbolic-expression recognition
5. struct-spec native support
6. delegation status
7. native source block family
8. native runtime validation result
9. optional parity result

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- parity tests specific to `matlabv2native`
- timing-field contract tests where practical

Minimum expectations for this campaign:

- committed tests for every promoted nonlinear family
- committed tests for every promoted unary-math family
- tests proving runtime-native symbolic cases still do not require Python in the hot path
- tests proving Python parity remains available where claimed
- tests proving symbolic-expression recognition for the families you promote
- tests proving explicit delegation/runtime-only boundaries where support is still incomplete

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current

Document explicitly:

- which symbolic families are runtime-native
- which are direct symbolic-native
- which are struct-spec-only native
- which are runtime-only without Python parity
- which still delegate

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- silently reintroduce Python into the default runtime path for runtime-native symbolic cases
- claim symbolic parity without tests and ledger updates
- widen Simulink lowering without widening the MATLAB numerical oracle to match
- leave the `sawtooth` / `triangle` boundary ambiguous
- leave large unpushed local changes

## Concrete First Step

Start with the next smallest defensible symbolic gap closure:

1. settle the `sawtooth` / `triangle` boundary honestly:
   - either make Python parity mode work for their current expression/input-spec path
   - or explicitly mark them runtime-only in tests/docs
2. then promote:
   - `saturation`
   - `dead_zone`
3. add MATLAB symbolic recognition where practical for those two families
4. add runtime-native tests and validation coverage
5. update the ledger

Only after that is clean and green should you widen further to:

- `sign`
- `abs`
- `min/max`
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`
