# Campaign Prompt: Bring `matlabv2native` Up to Parity With the Python Backend

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of bringing `matlabv2native` up to practical parity with the existing Python backend while keeping the architecture additive.

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

- the existing Python backend, which must remain intact and authoritative for legacy and parity/debug use
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native explicit-ODE Simulink lowering for current anchor cases
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for current anchor cases
  - default runtime execution for native-eligible anchor cases without requiring Python build/sim
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

## Core Strategic Goal

Bring `matlabv2native` up to practical parity with the Python backend for the repo’s currently supported workflows, while keeping:

- the Python backend intact
- `matlabv1` intact
- runtime-native MATLAB execution as the long-term target for supported cases
- Python parity available as an explicit comparison/debug path

This campaign is not about deleting Python immediately. It is about reaching the point where:

- the MATLAB-native backend supports the same meaningful user-facing input families and route classes as the Python backend
- the same problems can be run through both backends
- parity differences are explicit, tested, and shrinking
- the runtime-native MATLAB path is trustworthy for the cases it claims to support

## Mission

Advance `matlabv2native` from a narrow explicit-ODE runtime-native path into a broad, test-backed MATLAB-native backend that is as close as possible to the Python backend in:

- supported input families
- front-door input formats
- equation normalization and classification
- first-order conversion
- source block selection
- model structure quality
- simulation behavior
- validation behavior
- user-facing results

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while pursuing parity.
5. Every new MATLAB-native capability must have automated parity checks against Python or an explicit reason why the comparison is not yet meaningful.
6. Every generated model must still simulate and validate.
7. Do not weaken validation to make parity easier to claim.
8. If a case is not trustworthy in MATLAB-native form yet, keep it delegated or parity-gated and say so explicitly.
9. Do not introduce a public build-only escape hatch.
10. Do not claim parity for a family, route, or front door unless it is reflected in tests and docs.

## Git / Push Discipline

You are continuing on an already-pushed branch. Preserve that discipline.

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

If you get blocked, push the last stable checkpoint before continuing.

If the remote or auth breaks, report that explicitly and continue with local commits, but do not pretend pushes happened.

## Primary Objective for This Campaign

Bring `matlabv2native` up to speed with the Python backend by closing the parity gap across:

- front-door intake
- route support
- input-source family support
- native lowering quality
- validation behavior
- comparison/reporting

You do not need to make MATLAB-native the only backend. You do need to make it broad, explicit, and testable enough that it is a real peer to the Python backend.

## Required Major Workstreams

### Workstream 1: Parity Ledger and Gap Inventory

Before broadening support further, build and maintain a parity ledger that compares MATLAB-native vs Python backend across:

- source/front-door types
- route classes
- input families
- lowering strategy
- validation surfaces
- runtime-vs-parity availability

This ledger must be committed and updated as work progresses.

At minimum, track:

- `matlab_symbolic`
- equation text
- LaTeX
- structured ODE specs
- explicit ODE
- higher-order ODE reduced to first order
- coupled explicit systems
- ambiguous / delegated classes

And input families at minimum:

- constant
- step
- delayed step
- pulse
- impulse approximation
- ramp
- sine
- cosine
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
- unsupported symbolic expression via `MATLAB Function` fallback

### Workstream 2: Front-Door Parity

Bring `matlabv2native` closer to parity with the Python backend for front-door input intake.

At minimum, assess and implement parity or explicit delegation behavior for:

- MATLAB symbolic equations
- MATLAB-style equation text
- structured ODE specs
- LaTeX

Requirements:

- if a front door cannot be supported natively yet, delegate explicitly and document it
- if a front door is supported natively, add parity tests against Python
- do not let the public API behave ambiguously about whether a request was truly native or delegated

### Workstream 3: Route/Class Support Parity

Bring route support closer to the Python backend.

At minimum:

- strengthen explicit ODE support beyond the anchor cases
- add committed tests for coupled explicit systems
- identify where the Python backend supports cases that `matlabv2native` still delegates
- decide, case by case, whether to:
  - implement natively
  - delegate intentionally
  - mark unsupported for now

Do not overclaim DAE/native algebraic parity unless it is actually built and validated.

### Workstream 4: Input Family Parity

Widen runtime-native support in both:

1. native Simulink source lowering
2. MATLAB numerical-oracle input evaluation

Bring MATLAB-native support up toward the Python backend for the current meaningful family set:

- pulse
- impulse approximation
- ramp
- sine
- cosine
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

Requirements:

- do not mark a family runtime-native unless both lowering and oracle support exist
- if a native Simulink block exists, use it
- use `MATLAB Function` fallback only when direct native block composition is not possible
- preserve user-visible/editable inputs and parameters
- keep the default runtime path Python-free for families promoted to runtime-native

### Workstream 5: Lowering Quality Parity

Reduce the gap between the MATLAB-native builder and the Python builder in model readability and block choice.

At minimum:

- reduce `MATLAB Function` block overuse in source lowering
- reduce `MATLAB Function` block overuse in RHS lowering
- lower directly with native blocks where possible:
  - Sum
  - Gain
  - Product
  - reciprocal / division patterns where safe
  - Math Function
  - Trigonometric Function
  - Saturation
  - Dead Zone
- avoid irrelevant visual plumbing
- preserve user-visible/editable parameters and inputs

Add tests that verify native block-family choices for converted cases.

### Workstream 6: Validation Parity

Strengthen validation behavior so MATLAB-native is comparable to Python in a disciplined way.

For native-eligible explicit-ODE cases:

- keep MATLAB numerical reference as the primary runtime validation surface
- keep Python parity as an explicit secondary surface
- expose, compare, and document:
  - native vs MATLAB reference
  - Python vs MATLAB reference
  - native vs Python

Where Python and MATLAB-native differ:

- diagnose the source
- fix the discrepancy
- or explicitly record the divergence in the parity ledger

### Workstream 7: Comparison API Parity

The default runtime path should remain lean. Add or expand a heavy comparison API suitable for parity work.

You must either:

- expand `matlabv2native.compareWithPython(...)`

or

- add a new additive API such as:
  - `matlabv2native.compareAll(...)`
  - `matlabv2native.compareWithParity(...)`

This API should compare, for native-eligible problems where meaningful:

- route/classification
- first-order state set/order
- first-order RHS semantics where practical
- native source block family
- native runtime traces vs MATLAB reference
- Python traces vs MATLAB reference
- native vs Python traces
- validation result surfaces

Requirements:

- runtime API stays lean
- comparison API can stay heavy
- mismatches must be explicit and machine-readable enough for tests

### Workstream 8: Performance Visibility

Keep performance measurable as parity broadens.

Requirements:

- preserve additive timing fields in result structs
- document what each field measures
- add tests that ensure timing fields are present for runtime-native cases
- add tests that ensure Python parity timing is only populated when parity mode is requested

Do not hardcode absolute speed thresholds. Visibility matters more than promises.

## Required Parity Matrix

At minimum, build and maintain automated parity coverage for:

### Problem Shapes

- first-order explicit scalar ODE
- second-order scalar ODE reduced to first order
- coupled explicit ODE system
- parameterized explicit ODE
- unsupported-but-valid symbolic input fallback case

### Input Families

- constant
- step
- delayed step
- pulse
- impulse approximation
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
- unsupported symbolic expression using `MATLAB Function` fallback

For each family/case, track:

1. whether MATLAB-native runtime support exists
2. whether MATLAB numerical-oracle support exists
3. whether Python parity support exists
4. whether the family still delegates
5. native source block family
6. native runtime validation result
7. optional Python parity result
8. whether Python is required in the hot path

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

Minimum expectations for this campaign:

- committed integration coverage for at least one coupled explicit native-runtime case
- widened-input integration coverage for runtime-native cases
- explicit parity-mode tests for widened families
- tests proving runtime-native cases do not require Python in the hot path
- tests proving Python parity remains available explicitly
- tests for timing-field presence and parity-mode timing behavior
- tests verifying reduced `MATLAB Function` usage for at least some converted RHS/source cases

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- add and maintain a parity ledger doc
- document which families are:
  - runtime-native
  - MATLAB-reference supported
  - parity-only
  - delegated
- document which front doors are:
  - native
  - delegated
  - unsupported
- document the comparison API boundary: lean runtime vs heavy parity

Document explicitly:

- which cases no longer require Python during normal execution
- which cases still delegate
- which cases are parity-only
- which result fields indicate runtime mode vs parity mode

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- silently reintroduce Python into the default runtime path for runtime-native cases
- claim parity without tests and ledger updates
- widen support in lowering without widening the MATLAB numerical oracle to match
- leave coverage status implicit instead of documented
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which fronts/families are now parity-close or parity-complete
- which cases are runtime-native
- which cases still require parity mode or delegation
- what `MATLAB Function` usage was eliminated
- what still blocks broader parity

## Concrete First Step

Start by making the next parity jump concrete and test-backed:

1. add committed integration coverage for a coupled explicit native-runtime case
2. promote the next smallest defensible family set to runtime-native:
   - `pulse`
   - `ramp`
   - `sine`
3. add MATLAB numerical-oracle support for those families
4. add explicit Python parity tests for those families
5. create and commit the parity ledger

Only after that is clean and green should you widen further to square/sawtooth/triangle, saturation/dead-zone, and unary math families such as `atan`, `atan2`, `exp`, `log`, and `sqrt`.
