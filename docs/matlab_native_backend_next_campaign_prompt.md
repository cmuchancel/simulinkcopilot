# Campaign Prompt: Advance `matlabv2native` from Explicit-ODE Preview to Native Lowering

Use this prompt to continue the native MATLAB backend campaign from the current repo state after the explicit-ODE preview/parity checkpoint.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoints:

- baseline checkpoint: `c9d4aab`
- phase-1 scaffold checkpoint: `5d78fec`
- phase-2 explicit-ODE parity preview checkpoint: `c0e6f1b`

Do not restart the campaign from scratch. Continue from the existing additive MATLAB-native scaffold and the already-pushed explicit-ODE preview work.

## Current State You Must Respect

The repo already has:

- the existing Python backend, still authoritative
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has a real phase-2 explicit-ODE preview/parity layer

Current `matlabv2native` capabilities:

- MATLAB-first public API exists:
  - `matlabv2native_setup`
  - `matlabv2native.setup`
  - `matlabv2native.analyze`
  - `matlabv2native.generate`
  - `matlabv2native.validate`
  - `matlabv2native.compareWithPython`
- MATLAB-side source-type inference exists
- MATLAB-side caller-workspace capture exists
- MATLAB-side equation-text extraction exists
- MATLAB-side preview metadata inference exists for:
  - states
  - inputs
  - parameters
  - time variable
- MATLAB-side explicit-ODE preview exists for MATLAB symbolic equations when `odeToVectorField` succeeds
- MATLAB-side first-order state/order preview exists for those explicit ODEs
- the bridge now exposes Python `first_order` data back to MATLAB
- `matlabv2native.compareWithPython(...)` now compares:
  - states
  - algebraics
  - inputs
  - parameters
  - time variable
  - route
  - first-order state set/order
- `matlabv2native.generate(...)` still delegates actual route analysis, build, simulation, and validation to Python

Current focused tests that already passed before you start:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `5 passed, 3 deselected`

## Mission

Advance `matlabv2native` from an explicit-ODE preview/parity scaffold toward a **real native explicit-ODE backend**, without breaking:

- the Python backend
- the old MATLAB bridge
- `matlabv1`
- the current `matlabv2native` public API

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Keep using the Python backend as the oracle until native MATLAB parity is proven case by case.
4. Every new native MATLAB capability must have automated parity checks.
5. Every build path that produces a Simulink model must still simulate and validate.
6. If native MATLAB and Python differ semantically, do not hand-wave it. Fix it or explicitly mark the case as delegated/unsupported.
7. Do not claim “native lowering” if the generated model still goes through the Python graph builder.

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

Implement the next real native step in `matlabv2native`:

- native Simulink lowering for explicit ODEs handled by the MATLAB-side preview
- native input-source lowering for the supported explicit-ODE input matrix
- parity checks for source block family, simulation traces, and validation status

You do not need full native DAE parity immediately. Explicit ODEs still come first.

## Required Next Phases

### Phase 3A: Native Explicit-ODE Lowering Boundary

Introduce a clear native-lowering boundary inside `matlabv2native`.

Requirements:

- determine when a problem is eligible for native lowering
- require, at minimum:
  - `source_type == matlab_symbolic`
  - native explicit-ODE route preview is available
  - native first-order preview is available
- keep Python delegation as fallback when those conditions are not met
- expose in the result whether the model was:
  - `native_explicit_ode`
  - `python_delegate`

Do not silently route native-eligible problems back through Python without reporting that.

### Phase 3B: Native Simulink Lowering for Explicit ODEs

For native-eligible explicit ODEs, build the Simulink diagram directly in MATLAB using Simulink APIs.

Requirements:

- readable diagrams
- deterministic naming where feasible
- no irrelevant visual plumbing
- editable user-visible inputs and parameters stay visible
- preserve current readability rules already enforced in the Python path
- generate at least:
  - integrator chain for first-order states
  - algebraic RHS blocks for explicit state equations
  - visible outputs for the relevant states
- keep the native model build side-by-side with the Python lowering path

Do not remove or rewrite away the existing Python lowerer.

### Phase 3C: Native Input-Source Lowering

For native-eligible explicit ODEs, lower the supported source families directly in MATLAB to native Simulink blocks.

At minimum cover:

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
- one unsupported symbolic input that must fall back to a MATLAB Function block

Requirements:

- if a native Simulink block exists, use it
- only use MATLAB Function fallback when direct block composition is not possible
- preserve visible/editable inputs and parameters
- compare native block family choice against the Python backend semantically

### Phase 3D: Native Simulation and Validation for Explicit ODEs

Any explicit-ODE model generated natively in MATLAB must:

- simulate
- produce outputs for the relevant states/signals
- validate numerically

During this phase, it is acceptable for the validation oracle to remain the Python/reference solve path, but the generated model itself must be native.

Requirements:

- compare native model simulation traces against the same reference used by the Python path
- report pass/fail validation status in `matlabv2native`
- do not add a public build-only escape hatch

### Phase 3E: Expanded Parity Harness

Extend `matlabv2native.compareWithPython(...)` so it compares more than preview metadata.

Add parity checks for:

- route/classification
- first-order state set/order
- source block family chosen for inputs
- whether the generated model was native or delegated
- simulation traces for explicit ODEs
- validation pass/fail status

Where exact internal structures differ, compare at the semantic level rather than forcing byte-identical representations.

## Required Input Matrix for Native Explicit-ODE Parity

At minimum, compare native MATLAB vs Python on explicit ODE cases with:

- constant input
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
- one unsupported symbolic expression that should lower to a MATLAB Function fallback

For each case, compare:

1. route
2. states
3. inputs
4. parameters
5. input interpretation
6. source block family
7. whether lowering was native or delegated
8. simulation traces
9. validation result

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- parity tests specific to `matlabv2native`
- bridge tests if response contracts change

Do not remove existing tests.

You must keep these green:

- existing Python tests you touch
- `matlabv1` integration tests
- `matlabv2native` tests you add

Minimum expectations for this continuation:

- at least one native-lowered first-order driven ODE integration test
- at least one native-lowered second-order mass-spring integration test
- at least one parity test showing native vs Python source-block-family agreement
- at least one fallback test proving unsupported symbolic inputs still go to MATLAB Function

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- document what is now truly native vs still delegated
- document parity coverage and known gaps
- add a parity ledger doc if that becomes the clearest way to track matrix status

Document explicitly:

- which explicit-ODE cases now lower natively
- which input families lower natively
- which cases still delegate to Python
- which parity fields are now compared automatically

## Failure Conditions

You fail this continuation if you:

- break current Python behavior
- break `matlabv1`
- claim native support without parity tests
- silently change semantics relative to the Python backend
- skip simulation/validation on native-generated diagrams
- leave large unpushed local changes
- build “native” diagrams that still secretly depend on Python lowering

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which explicit-ODE cases now lower natively
- which parity cases now pass
- what still delegates to Python

## Concrete First Step

Start by implementing a true native explicit-ODE build path for the two anchor cases that already have preview parity:

- `diff(x,t) == -x + u(t)`
- `m*diff(x,t,2) + c*diff(x,t) + k*x == u(t)`

Build those diagrams natively in MATLAB, simulate them, and compare them against the existing Python backend on:

- source block family
- state outputs
- validation pass/fail

Only after those two anchor cases are native and green should you widen the input matrix.
