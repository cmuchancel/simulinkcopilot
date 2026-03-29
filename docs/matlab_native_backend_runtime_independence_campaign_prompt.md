# Campaign Prompt: Move `matlabv2native` Toward a Standalone MATLAB Runtime Path

Use this prompt to continue the native MATLAB backend campaign from the current repo state after the MATLAB-reference anchor checkpoint.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoints:

- baseline checkpoint: `c9d4aab`
- phase-1 scaffold checkpoint: `5d78fec`
- phase-2 explicit-ODE parity preview checkpoint: `c0e6f1b`
- phase-3 native explicit-ODE lowering checkpoint: `5265910`
- phase-4 MATLAB-reference anchor checkpoint: `da5e18a`

Do not restart the campaign from scratch. Continue from the existing additive MATLAB-native scaffold and the already-pushed native explicit-ODE reference-oracle work.

## Current State You Must Respect

The repo already has:

- the existing Python backend, still authoritative for legacy and parity use
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native explicit-ODE Simulink lowering for current anchor cases
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for current anchor cases
  - three-way validation for those anchor cases:
    - native Simulink vs MATLAB reference
    - Python Simulink vs MATLAB reference
    - native Simulink vs Python Simulink

Current native anchor input coverage is still narrow:

- constant
- step / delayed step
- unsupported symbolic expression via `MATLAB Function` source fallback

Current focused tests already green at handoff:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `7 passed, 3 deselected`

## Core Strategic Problem You Must Address

`matlabv2native` is still not a true standalone runtime path for native-eligible problems.

Even for native explicit-ODE anchor cases, the normal runtime path still calls the Python backend in order to:

- build a Python oracle model
- simulate that Python oracle model
- use Python-derived first-order/model metadata as a cross-check

That is acceptable for migration, but it is not the end-state.

The next major milestone is:

- for native-eligible cases, the default runtime path should be MATLAB-native
- Python should remain available for parity, tests, and debug workflows
- Python should not remain on the default execution path for supported native cases

This milestone is about moving from:

- “native plus Python in the hot path”

to:

- “native in the hot path, Python in parity/debug workflows”

## Mission

Advance `matlabv2native` toward a **standalone MATLAB-native framework** for supported explicit-ODE cases by doing all of the following:

- remove Python from the default runtime path for native-eligible cases
- keep Python available as an explicit oracle/parity mode
- widen native input-source lowering and MATLAB numerical-oracle coverage enough to support a meaningful explicit-ODE matrix
- reduce reliance on `MATLAB Function` blocks where native block composition exists
- add runtime/performance visibility so the speed tradeoff is measurable

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while removing Python from the runtime path.
5. Every new native MATLAB capability must have automated tests.
6. Every build path that produces a Simulink model must still simulate and validate.
7. Do not replace validation with weaker checks just to gain speed.
8. If a case is not trustworthy without Python yet, keep it delegated or parity-gated and say so explicitly.
9. Do not introduce a public build-only escape hatch.
10. Do not pretend a case is “standalone native” if it still requires Python during normal execution.

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

Implement the next real native-runtime step in `matlabv2native`:

- for native-eligible explicit-ODE cases, stop requiring a Python build/sim in the default `generate` / `validate` path
- keep Python available as an explicit parity mode
- expand native lowering/oracle coverage enough that this is technically defensible
- expose performance/timing information so the runtime tradeoffs are visible

You do not need full native DAE parity immediately. Explicit ODEs still come first.

## Required Next Phases

### Phase 5A: Split Runtime Mode From Parity Mode

Introduce a clean distinction between:

- default native runtime execution
- explicit parity/debug execution

Requirements:

- for native-eligible explicit-ODE cases, the default `matlabv2native.generate(...)` and `matlabv2native.validate(...)` path must not require a Python build/sim
- Python comparison must remain available through one of:
  - an explicit public comparison API
  - an internal debug/parity mode
  - test-only parity helpers
- the result object must clearly indicate:
  - `native_runtime_only`
  - `native_with_python_parity`
  - `python_delegate`

Do not silently keep Python in the hot path while claiming native runtime independence.

### Phase 5B: Standalone Native Validation for Supported Cases

For native-eligible explicit-ODE cases supported by the current native input matrix, make the MATLAB numerical reference the primary validation mechanism in the default runtime path.

Requirements:

- native Simulink vs MATLAB numerical reference must be sufficient for default validation
- Python validation must no longer be required for those supported cases during default execution
- Python parity may still run in tests or explicit comparison flows
- validation output must clearly distinguish:
  - runtime validation surfaces
  - optional parity surfaces

### Phase 5C: Widen Native Input-Source Lowering and Oracle Coverage Together

The next widening step must happen in both places together:

1. native Simulink source lowering
2. MATLAB numerical-oracle input evaluation

At minimum, add these families natively in both places:

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

- do not claim native runtime support for an input family unless both the Simulink lowering and the MATLAB numerical oracle support it reliably
- if a native Simulink block exists, use it
- only use `MATLAB Function` fallback when direct native block composition is not possible
- preserve user-visible/editable inputs and parameters

### Phase 5D: Reduce `MATLAB Function` Fallback in Native RHS Lowering

The current native explicit-ODE builder still overuses `MATLAB Function` blocks for RHS expressions.

Reduce this where direct block composition exists.

At minimum, lower directly with native blocks where possible for:

- sums
- gains
- products
- reciprocal / division patterns where safe
- math-function blocks
- trigonometric function blocks
- saturation
- dead zone

Requirements:

- keep `MATLAB Function` only as a fallback
- do not make the diagrams less readable
- add tests for the cases you convert

### Phase 5E: Add a Native Comparison API Separate From Default Runtime

The repo now needs a clean place for heavy comparison flows.

You must either:

- expand `matlabv2native.compareWithPython(...)`

or

- add a new additive API such as:
  - `matlabv2native.compareAll(...)`
  - `matlabv2native.compareWithParity(...)`

This API should be the place where Python-oracle parity remains first-class.

Requirements:

- compare route/classification
- compare first-order state set/order
- compare first-order RHS semantics where practical
- compare source block family
- compare native runtime traces vs MATLAB reference
- compare Python traces vs MATLAB reference
- compare native vs Python traces
- report all mismatches explicitly

The key design rule is:

- default runtime path should stay lean
- comparison API can stay heavy

### Phase 5F: Add Performance Instrumentation

If the goal is a usable MATLAB-native runtime path, performance must become measurable.

Add timing instrumentation for at least:

- native preview/classification
- native model build
- native Simulink simulation
- MATLAB numerical reference solve
- optional Python parity build/sim
- total end-to-end wall time

Requirements:

- include timing fields in the result struct
- keep the fields additive and non-breaking
- document what each timing covers
- add at least one regression/integration assertion that timings are present for native-eligible cases

Do not promise absolute speed targets in code. Just make performance visible and comparable.

## Required Runtime/Parity Matrix

At minimum, produce a matrix for native-eligible explicit ODEs showing whether each family is:

- native runtime supported
- MATLAB-reference supported
- Python parity supported
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
4. whether Python is still required in the hot path

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- parity tests specific to `matlabv2native`
- performance/timing contract tests where practical

Do not remove existing tests.

You must keep these green:

- existing Python tests you touch
- `matlabv1` integration tests
- `matlabv2native` tests you add

Minimum expectations for this continuation:

- at least one test proving native-eligible anchor cases no longer require Python in the default runtime path
- at least one test proving Python parity is still available explicitly
- at least one test for native runtime validation against MATLAB reference without Python in the loop
- at least one timing-field contract test for native-eligible cases
- at least one widened-input integration test that is runtime-native and MATLAB-reference validated

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- document the split between runtime mode and parity mode
- document which cases are truly standalone native
- document which cases still require Python parity to be trustworthy
- document the MATLAB numerical solver policy
- document the timing/performance fields
- add a parity/runtime coverage ledger if that is the clearest representation

Document explicitly:

- which cases no longer require Python during normal execution
- which cases still delegate
- which input families are runtime-native
- which input families are parity-only
- which fields in the result struct indicate runtime mode vs parity mode

## Failure Conditions

You fail this continuation if you:

- break current Python behavior
- break `matlabv1`
- silently leave Python in the default native runtime path
- weaken validation just to remove Python
- claim standalone-native support without a trustworthy MATLAB reference path
- leave timing/performance invisible
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which cases are now standalone-native in the runtime path
- which cases still require parity mode or delegation
- what performance/timing visibility was added
- what still blocks removal of Python from more cases

## Concrete First Step

Start by removing Python from the default runtime path for the two anchor cases that already have:

- native lowering
- native Simulink simulation
- MATLAB numerical reference validation

Those anchor cases are:

- `diff(x,t) == -x + u(t)`
- `m*diff(x,t,2) + c*diff(x,t) + k*x == u(t)`

For those two cases:

1. make default `matlabv2native.generate(...)` and `matlabv2native.validate(...)` run without requiring Python build/sim
2. keep an explicit parity path available for Python comparison
3. preserve MATLAB-reference validation
4. add timing fields
5. prove this in tests

Only after those anchor cases are standalone-native in the default runtime path should you widen the runtime-native matrix.
