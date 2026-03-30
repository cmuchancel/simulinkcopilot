# Campaign Prompt: Bring `matlabv2native` to Full MATLAB-Symbolic Parity

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of bringing `matlabv2native` up to practical parity with the Python backend **for the `matlab_symbolic` front door only**.

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

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed runtime/parity work.

## Scope Lock

This campaign is **not** about repo-wide parity across every public front door.

This campaign is specifically about:

- the `matlab_symbolic` front door
- MATLAB users defining symbolic equations and symbolic input expressions in MATLAB
- bringing `matlabv2native` as close as possible to Python-backend coverage for that workflow

You do **not** need to spend this campaign on:

- LaTeX parity
- equation-text parity
- structured ODE-spec parity

Those may remain delegated if needed. Do not let non-symbolic front doors dilute the campaign.

## Current State You Must Respect

The repo already has:

- the existing Python backend, which must remain intact and authoritative for legacy and explicit parity/debug use
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native explicit-ODE Simulink lowering for the current supported native set
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for the current supported native set
  - default runtime execution for current native symbolic cases without requiring Python build/sim
  - explicit Python parity mode through `ParityMode="python"`
  - additive timing fields for preview/build/sim/reference/parity/total wall time
  - committed coupled explicit-system runtime coverage
  - committed coupled explicit-system parity-mode coverage
  - committed runtime-native / parity coverage for:
    - constant
    - step / delayed step
    - pulse
    - ramp
    - sine
    - square
    - unsupported symbolic input via `MATLAB Function` fallback

Current focused tests already green at handoff:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `13 passed, 3 deselected, 8 subtests passed`

The current parity ledger already exists at:

- [docs/matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)

The current architecture/status doc already exists at:

- [docs/matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)

## Core Strategic Goal

Bring `matlabv2native` up to practical parity with the Python backend **for MATLAB symbolic inputs**.

That means the same meaningful MATLAB symbolic problems should be able to:

- normalize the same way
- classify the same way
- lower to the same semantic source/block families
- simulate to the same engineering result
- validate against the same MATLAB numerical reference surface
- compare cleanly against the Python backend when parity mode is requested

This campaign is not about deleting Python immediately. It is about making the MATLAB-symbolic native path broad and trustworthy enough that it is a real peer to the Python backend for MATLAB symbolic workflows.

## Mission

Advance `matlabv2native` from “partial native parity for MATLAB symbolic explicit ODEs” to “broad native parity for MATLAB symbolic workflows”.

You must move the MATLAB-native backend closer to the Python backend in:

- MATLAB symbolic route support
- MATLAB symbolic expression normalization
- input family support for symbolic inputs
- native lowering quality
- simulation behavior
- validation behavior
- parity reporting

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while pursuing MATLAB-symbolic parity.
5. Every new MATLAB-native capability must have automated parity checks against Python or an explicit documented reason why the comparison is not yet meaningful.
6. Every generated model must still simulate and validate.
7. Do not weaken MATLAB-reference validation to make parity easier to claim.
8. Do not mark a MATLAB symbolic family/route as runtime-native unless native Simulink lowering and MATLAB numerical-oracle evaluation both exist and are tested.
9. Do not silently reintroduce Python into the default runtime path for runtime-native symbolic cases.
10. Do not claim MATLAB-symbolic parity for a family or route unless the tests and docs actually prove it.

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

Close the remaining parity gap for **MATLAB symbolic inputs** by doing all of the following:

- complete the remaining waveform families for symbolic native runtime
- complete the nonlinear/math family set for symbolic native runtime
- improve symbolic-expression recognition so the native path no longer depends mainly on struct-style input specs for widened families
- strengthen route support for MATLAB symbolic systems beyond the current explicit-ODE sweet spot where practical
- strengthen parity reporting so mismatches are easy to inspect
- keep the parity ledger explicit and honest

## Required Major Workstreams

### Workstream 1: MATLAB-Symbolic Parity Ledger

Refocus the parity ledger around the MATLAB symbolic scope.

Keep it current as the source of truth for MATLAB symbolic parity.

At minimum, explicitly track for each symbolic family:

- runtime-native
- MATLAB-reference supported
- Python parity supported
- symbolic-expression native recognition
- struct-input-spec native recognition
- delegated

And for each symbolic route/problem shape:

- native preview
- runtime-native
- MATLAB-reference supported
- Python parity supported
- delegated

### Workstream 2: Complete Explicit-ODE Input Family Parity for MATLAB Symbolic

Bring the remaining meaningful symbolic input families up toward Python parity.

At minimum, complete the following in both:

1. native Simulink source lowering
2. MATLAB numerical-oracle evaluation

Families to close:

- `sawtooth`
- `triangle`
- `cosine`
- `impulse approximation`
- `saturation`
- `dead_zone`
- `sign`
- `abs`
- `min/max`
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`

Requirements:

- do not claim runtime-native support for a symbolic family unless both native lowering and the MATLAB numerical oracle support it reliably
- if a native Simulink block exists, use it
- only use `MATLAB Function` fallback when direct native block composition is not possible
- keep default runtime path Python-free for families promoted to runtime-native

### Workstream 3: Symbolic-Expression Recognition Parity

This is the most important missing piece for the MATLAB symbolic scope.

The current native path is strongest when caller-workspace inputs resolve to struct-style input specs. That is not enough for full MATLAB symbolic parity.

Improve native symbolic-expression recognition so widened families are detected directly from symbolic expressions where practical.

At minimum, strengthen native recognition for:

- pulse
- ramp
- sine
- square
- sawtooth
- triangle
- saturation / dead-zone style piecewise patterns where practical
- min/max
- unary math families such as `atan`, `atan2`, `exp`, `log`, `sqrt`

Requirements:

- compare recognized family/type against Python where meaningful
- do not overclaim broad symbolic parity unless the matcher is actually reliable
- if a family still requires struct-style input specs for trustworthy native handling, document that explicitly in tests and the ledger

### Workstream 4: MATLAB-Symbolic Route/Class Parity

The current native path is strongest for explicit ODEs.

Bring MATLAB-symbolic route support closer to the Python backend by:

- strengthening explicit ODE support across more symbolic input families
- keeping committed coupled explicit-system runtime and parity coverage broad
- identifying which MATLAB symbolic routes the Python backend supports that `matlabv2native` still delegates
- deciding, case by case, whether to:
  - implement natively
  - delegate intentionally
  - mark unsupported for now

Do not overclaim DAE/native algebraic parity unless it is actually built and validated.

If DAE/descriptor-style symbolic systems stay delegated during this campaign, document that clearly instead of hand-waving it.

### Workstream 5: Lowering Quality Parity

Reduce the gap between the MATLAB-native builder and the Python builder for MATLAB symbolic workflows.

At minimum:

- reduce `MATLAB Function` overuse in native source lowering
- reduce `MATLAB Function` overuse in native RHS lowering
- lower directly with native blocks where possible:
  - Sum
  - Gain
  - Product
  - reciprocal / division patterns where safe
  - Math Function
  - Trigonometric Function
  - Saturation
  - Dead Zone
  - Sign
  - MinMax
  - Repeating Sequence
- preserve readable diagrams
- preserve editable user-visible parameters and inputs

Add tests that verify native block-family choices for converted cases.

### Workstream 6: Validation Parity for MATLAB Symbolic

Strengthen validation behavior so MATLAB-symbolic native results are comparable to Python in a disciplined way.

For runtime-native symbolic cases:

- keep MATLAB numerical reference as the primary runtime validation surface
- keep Python parity as an explicit secondary surface
- expose, compare, and document:
  - native vs MATLAB reference
  - Python vs MATLAB reference
  - native vs Python

Where Python and MATLAB-native differ:

- diagnose the source
- fix the discrepancy
- or explicitly record the divergence in the ledger

### Workstream 7: Heavy Comparison API for MATLAB Symbolic

The default runtime path should remain lean. Strengthen the heavy comparison surface for MATLAB symbolic parity work.

You must either:

- expand `matlabv2native.compareWithPython(...)`

or

- add a new additive API such as:
  - `matlabv2native.compareAll(...)`
  - `matlabv2native.compareWithParity(...)`

For native-eligible MATLAB-symbolic problems, compare where meaningful:

- route/classification
- first-order state set/order
- symbolic input-family recognition
- source block family
- runtime mode vs parity mode
- native runtime traces vs MATLAB reference
- Python traces vs MATLAB reference
- native vs Python traces
- validation surfaces

Mismatches must be explicit and structured enough to support tests and ledger updates.

### Workstream 8: Performance Visibility

Keep performance measurable while symbolic parity broadens.

Requirements:

- preserve additive timing fields in result structs
- document what each timing field measures
- add tests that timing fields are present for runtime-native symbolic cases
- add tests that Python parity timing is only populated when parity mode is requested

Do not hardcode absolute speed thresholds. Visibility matters more than promises.

## Required MATLAB-Symbolic Parity Matrix

At minimum, build and maintain automated parity coverage for these MATLAB symbolic problem shapes:

- first-order explicit scalar ODE
- second-order scalar ODE reduced to first order
- coupled explicit ODE system
- parameterized explicit ODE
- unsupported-but-valid symbolic input fallback case

At minimum, build and maintain automated parity coverage for these MATLAB symbolic input families:

- constant
- step
- delayed step
- pulse
- ramp
- sine
- square
- sawtooth
- triangle
- impulse approximation
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

1. whether MATLAB-native runtime support exists
2. whether MATLAB numerical-oracle support exists
3. whether Python parity support exists
4. whether symbolic-expression native recognition exists
5. whether struct-input-spec native recognition exists
6. whether the family still delegates
7. native source block family
8. native runtime validation result
9. optional Python parity result
10. whether Python is required in the hot path

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

- committed integration coverage for every promoted symbolic family
- explicit Python parity-mode tests for every promoted symbolic family
- committed coupled explicit-system parity-mode coverage stays green
- tests proving runtime-native symbolic cases do not require Python in the hot path
- tests proving Python parity remains available explicitly
- tests proving symbolic-expression recognition, not just struct-style input specs, for the widened families you claim
- tests for timing-field presence and parity-mode timing behavior
- tests verifying reduced `MATLAB Function` usage for at least some converted source/RHS cases

If a symbolic family cannot be promoted cleanly in this campaign, add a test that proves the delegation boundary instead of leaving it ambiguous.

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current
- document which MATLAB symbolic families are:
  - runtime-native
  - MATLAB-reference supported
  - Python-parity supported
  - symbolic-recognition supported
  - struct-spec-only native
  - delegated
- document which MATLAB symbolic routes are:
  - runtime-native
  - parity-supported
  - delegated
- document the comparison API boundary: lean runtime vs heavy parity

Document explicitly:

- which symbolic cases no longer require Python during normal execution
- which families still require struct-style input specs for native operation
- which families are truly native from symbolic-expression intake
- which symbolic routes still delegate

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- silently reintroduce Python into the default runtime path for runtime-native symbolic cases
- claim MATLAB-symbolic parity without tests and ledger updates
- widen Simulink lowering without widening the MATLAB numerical oracle to match
- leave symbolic-expression recognition status implicit instead of documented
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which MATLAB symbolic families are now parity-close or parity-complete
- which symbolic routes are runtime-native
- which families are symbolic-native vs struct-spec-only native
- which cases still require parity mode or delegation
- what `MATLAB Function` usage was eliminated
- what still blocks MATLAB-symbolic parity

## Concrete First Step

Start with the highest-value symbolic gap closure, not a broad rewrite.

1. finish `sawtooth` and `triangle` cleanly for MATLAB symbolic runtime and parity
2. finish symbolic-expression recognition for the currently widened waveform set:
   - pulse
   - ramp
   - sine
   - square
3. keep coupled explicit-system parity-mode coverage green
4. update the ledger to distinguish:
   - symbolic-native
   - struct-spec-only native
   - delegated
5. only after that move into the nonlinear/math families:
   - saturation
   - dead_zone
   - sign
   - abs
   - min/max
   - atan
   - atan2
   - exp
   - log
   - sqrt

Do not spread effort across non-symbolic front doors during this campaign unless you need a very small adjustment to keep shared code healthy.
