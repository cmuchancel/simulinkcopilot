# Campaign Prompt: Add a Native MATLAB Numerical Oracle and Widen `matlabv2native` Parity

Use this prompt to continue the native MATLAB backend campaign from the current repo state after the native explicit-ODE lowering checkpoint.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoints:

- baseline checkpoint: `c9d4aab`
- phase-1 scaffold checkpoint: `5d78fec`
- phase-2 explicit-ODE parity preview checkpoint: `c0e6f1b`
- phase-3 native explicit-ODE lowering checkpoint: `5265910`

Do not restart the campaign from scratch. Continue from the existing additive MATLAB-native scaffold and the already-pushed native explicit-ODE lowering work.

## Current State You Must Respect

The repo already has:

- the existing Python backend, still authoritative
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has a real native explicit-ODE build path for current anchor cases

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
- native explicit-ODE eligibility checks exist
- native explicit-ODE Simulink lowering exists for current anchor cases
- native explicit-ODE simulation exists in MATLAB/Simulink
- current native input-source lowering covers:
  - constant
  - step / delayed step
  - unsupported symbolic input expression lowered to a `MATLAB Function` source block
- `matlabv2native.generate(...)` now returns:
  - `BackendKind = "native_explicit_ode"` for native-eligible anchor cases
  - source block family parity against the Python oracle
  - simulation trace parity against the Python oracle model
  - validation status parity against the Python oracle result

## Critical Gap You Must Address

Right now, native explicit-ODE validation does **not** use a direct MATLAB numerical reference solve.

Current validation behavior is:

- build native Simulink model in MATLAB
- build Python-oracle Simulink model through the existing backend
- simulate both models
- compare native traces against the Python-oracle traces
- require the Python-oracle validation to have passed

This is not enough for the long-term native MATLAB backend. The next phase must add a true MATLAB-side numerical oracle so the repo can compare:

1. native MATLAB-generated Simulink model
2. Python-generated oracle Simulink model
3. MATLAB numerical reference solve

The MATLAB numerical reference must become a first-class validation/parity artifact for explicit ODEs.

## Current Focused Tests Already Green at Handoff

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `7 passed, 3 deselected`

## Mission

Advance `matlabv2native` from a native-lowered anchor implementation into a stronger engineering-valid native backend by adding:

- a native MATLAB numerical reference solve for explicit ODEs
- three-way parity checks across native Simulink, Python Simulink, and MATLAB numerical reference
- wider native explicit-ODE input lowering coverage
- stronger semantic parity checks for first-order RHS behavior and source block selection

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Keep using the Python backend as an oracle during migration, but do not treat it as the only oracle once the MATLAB numerical reference exists.
4. Every new native MATLAB capability must have automated parity checks.
5. Every build path that produces a Simulink model must still simulate and validate.
6. If native MATLAB, Python, and MATLAB numerical reference differ semantically, do not hand-wave it. Diagnose the source of divergence and either fix it or explicitly mark the case unsupported/delegated.
7. Do not claim “MATLAB-native validation” unless a real MATLAB numerical reference solve is used.
8. Do not introduce a public build-only escape hatch.

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

- add a true MATLAB numerical oracle for explicit ODEs
- use that oracle inside native validation
- compare native and Python-generated Simulink traces against the same MATLAB reference
- widen native input-source lowering beyond constant/step/fallback anchor coverage
- extend parity reporting so it reflects all three comparison surfaces

You do not need full native DAE parity immediately. Explicit ODEs still come first.

## Required Next Phases

### Phase 4A: Native MATLAB Numerical Oracle for Explicit ODEs

Implement a native MATLAB numerical reference solve for explicit ODEs handled by `matlabv2native`.

Requirements:

- derive the first-order system in MATLAB from the native explicit-ODE preview
- construct a numeric RHS in MATLAB
- use a MATLAB ODE solver such as:
  - `ode45`
  - `ode15s`
  - or a deterministic solver choice rule based on problem characteristics
- use the same:
  - state ordering
  - time span
  - initial conditions
  - parameter values
  - input definition
  as the generated Simulink models
- package the result into a structured artifact that can be reused by validation and parity code

Requirements for solver policy:

- document the solver policy clearly
- if a case is obviously stiff, do not blindly force `ode45`
- if stiffness detection is heuristic, document the heuristic

Do not rely on the Python backend to produce the reference trajectory for this phase.

### Phase 4B: Native Input Evaluation for the MATLAB Numerical Oracle

The MATLAB numerical oracle must evaluate the same supported input families that `matlabv2native` claims to support natively.

At minimum, support in the MATLAB numerical oracle:

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
- unsupported symbolic expressions through a MATLAB function evaluation path when necessary

Requirements:

- the oracle input evaluation must be semantically aligned with the Simulink lowering
- do not let the numerical reference use a broader input semantics than the generated native model without flagging it
- if a symbolic input cannot yet be evaluated reliably in the MATLAB oracle, explicitly mark the case delegated/unsupported

### Phase 4C: Three-Way Validation

Replace the current “native vs Python-oracle only” validation model with a three-way validation structure for native explicit-ODE cases:

1. native Simulink vs MATLAB numerical oracle
2. Python Simulink vs MATLAB numerical oracle
3. native Simulink vs Python Simulink

Requirements:

- the MATLAB numerical oracle must be the primary reference
- keep the native-vs-Python comparison as a secondary parity signal
- validation status should reflect:
  - whether native agrees with MATLAB reference
  - whether Python agrees with MATLAB reference
  - whether native and Python agree with each other
- do not collapse those three signals into one ambiguous boolean

Expose this structure clearly in the `Validation` output.

### Phase 4D: Expand `compareWithPython(...)` or Add a New Comparison API

The current `compareWithPython(...)` is preview-heavy and Python-oriented.

You must either:

- expand `matlabv2native.compareWithPython(...)` to include numerical-reference-aware parity for native-eligible explicit ODEs

or

- introduce a new additive API such as:
  - `matlabv2native.compareAll(...)`
  - `matlabv2native.compareWithReference(...)`

The choice is yours, but it must be:

- additive
- documented
- explicit about which comparisons are preview-only vs build/simulate/validate

For native-eligible explicit ODEs, compare at minimum:

- route/classification
- first-order state set/order
- first-order RHS semantics at the state-equation level where practical
- source block family chosen for inputs
- whether lowering was native or delegated
- native Simulink traces vs MATLAB numerical reference
- Python Simulink traces vs MATLAB numerical reference
- native Simulink traces vs Python Simulink
- validation pass/fail status for all three comparisons

### Phase 4E: Widen Native Input-Source Lowering

Widen native Simulink input lowering beyond the current anchor set.

At minimum cover these natively in the MATLAB builder:

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

- if a native Simulink block exists, use it
- only use MATLAB Function fallback when direct block composition is not possible
- keep user-visible inputs and parameters visible/editable
- compare native block-family choice against the Python backend semantically

### Phase 4F: Reduce Overuse of `MATLAB Function` Blocks in Native RHS Lowering

The current native explicit-ODE build path still uses `MATLAB Function` blocks for many RHS expressions.

You must improve this where feasible.

At minimum:

- identify RHS cases that can be lowered directly with:
  - Sum
  - Product
  - Gain
  - Math Function
  - Trigonometric Function
  - Saturation
  - Dead Zone
- keep using `MATLAB Function` only as a fallback

You do not need to eliminate all RHS fallback usage in this phase, but you must reduce it intentionally and add tests for the cases you convert.

## Required Three-Way Comparison Matrix

At minimum, compare native MATLAB vs Python backend vs MATLAB numerical reference on explicit ODE cases with:

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
8. native vs MATLAB-reference traces
9. Python vs MATLAB-reference traces
10. native vs Python traces
11. validation result for all three surfaces

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

- at least one test proving native validation uses a MATLAB numerical reference instead of only Python oracle comparison
- at least one first-order explicit ODE three-way parity integration test
- at least one second-order mass-spring three-way parity integration test
- at least one parity test showing native vs Python vs MATLAB-reference agreement on source block family and traces
- at least one fallback test proving unsupported symbolic inputs still use a MATLAB Function source block but are still compared against a MATLAB numerical reference when possible

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- document what is now truly native vs still delegated
- document the MATLAB numerical solver policy
- document parity coverage and known gaps
- add a parity ledger doc if that becomes the clearest way to track matrix status

Document explicitly:

- which explicit-ODE cases now have MATLAB numerical reference validation
- which input families lower natively in Simulink
- which input families evaluate natively in the MATLAB numerical oracle
- which cases still delegate to Python
- which parity fields are now compared automatically

## Failure Conditions

You fail this continuation if you:

- break current Python behavior
- break `matlabv1`
- claim MATLAB-native validation without a true MATLAB numerical reference solve
- silently change semantics relative to the Python backend or the MATLAB reference
- skip simulation/validation on native-generated diagrams
- leave large unpushed local changes
- build a reference path that does not actually share the same state ordering and input semantics as the generated models

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which cases now validate against a MATLAB numerical reference
- which three-way parity cases now pass
- what still delegates to Python
- what still lacks a trustworthy MATLAB numerical oracle

## Concrete First Step

Start by adding a MATLAB numerical reference solve for the two anchor cases that already lower natively:

- `diff(x,t) == -x + u(t)`
- `m*diff(x,t,2) + c*diff(x,t) + k*x == u(t)`

For those two cases:

1. derive the first-order system in MATLAB
2. evaluate the input in MATLAB
3. solve the system numerically in MATLAB
4. compare:
   - native Simulink vs MATLAB reference
   - Python Simulink vs MATLAB reference
   - native Simulink vs Python Simulink
5. update the reported validation structure so the MATLAB reference is primary

Only after those anchor cases are three-way green should you widen the input matrix.
