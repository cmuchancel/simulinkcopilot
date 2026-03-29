# Continuation Prompt: Advance `matlabv2native` Beyond the Phase-1 Scaffold

Use this prompt to continue the native MATLAB backend campaign from the current repo state.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoint:

- baseline checkpoint: `c9d4aab`
- phase-1 scaffold checkpoint: `5d78fec`

Do not restart the campaign from scratch. Continue from the existing additive MATLAB-native scaffold.

## Current State You Must Respect

The repo already has:

- the existing Python backend, still authoritative
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- a new `matlabv2native` phase-1 scaffold

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
- a phase-1 parity harness exists that compares MATLAB preview metadata against the Python-normalized problem
- `matlabv2native.generate(...)` still delegates actual route analysis, build, simulation, and validation to Python

Current phase-1 tests already passed before you start:

```bash
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Result at handoff:

- `4 passed, 3 deselected`

## Mission

Advance `matlabv2native` from a metadata-preview scaffold toward a real native MATLAB backend, without breaking:

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

## Git / Push Discipline

You are continuing on an already-pushed branch. Preserve that discipline.

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

If you get blocked, push the last stable checkpoint before continuing.

## Primary Objective for This Continuation

Implement the **next real native step** in `matlabv2native`:

- native explicit-ODE route support
- native first-order conversion for explicit ODEs
- native Simulink lowering for explicit ODEs
- expanded parity checks beyond metadata

You do not need full native DAE parity immediately. Explicit ODEs come first.

## Required Next Phases

### Phase 2A: Native Explicit-ODE Classification

Implement native MATLAB logic that can determine when a problem is a supported explicit ODE, at minimum for:

- first-order explicit ODEs
- higher-order scalar/vector ODEs that can be converted cleanly to first order

Requirements:

- preserve deterministic behavior
- compare native route classification vs Python route classification
- keep Python delegation as fallback for non-explicit or ambiguous systems

### Phase 2B: Native First-Order Conversion

Implement native MATLAB first-order conversion for explicit ODEs.

Examples that must be supported:

- `diff(x,t) == -x + u`
- `m*diff(x,t,2) + c*diff(x,t) + k*x == u(t)`
- multi-state first-order systems

Requirements:

- deterministic generated state ordering
- clear mapping from original equations to first-order states
- parity checks against the Python first-order representation at the semantic level

### Phase 2C: Native Simulink Lowering for Explicit ODEs

For explicit ODEs handled natively, build the Simulink diagram natively in MATLAB using Simulink APIs.

Requirements:

- readable diagrams
- no irrelevant visual plumbing
- editable user-visible inputs and parameters stay visible
- use native source blocks where possible
- use MATLAB Function fallback only when direct native block mapping is not possible

### Phase 2D: Expanded Parity Harness

Extend `matlabv2native.compareWithPython(...)` so it compares more than metadata.

Add parity checks for:

- route/classification
- first-order state set/order
- source block family chosen for inputs
- simulation traces for explicit ODEs
- validation pass/fail status

Where exact internal representations differ, compare at the semantic level rather than forcing byte-identical structures.

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
6. block family
7. simulation traces
8. validation result

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- parity tests specific to `matlabv2native`

Do not remove existing tests.

You must keep these green:

- existing Python tests you touch
- `matlabv1` integration tests
- `matlabv2native` tests you add

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- document what is now truly native vs still delegated
- document parity coverage and known gaps

If helpful, add a parity ledger doc.

## Failure Conditions

You fail this continuation if you:

- break current Python behavior
- break `matlabv1`
- claim native support without parity tests
- silently change semantics relative to the Python backend
- skip simulation/validation on native-generated diagrams
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which parity cases now pass natively
- what still delegates to Python

## Concrete First Step

Start by implementing native explicit-ODE route detection plus first-order conversion for the simple mass-spring and first-order driven ODE cases, and extend `matlabv2native.compareWithPython(...)` so it reports route parity in addition to metadata parity.

