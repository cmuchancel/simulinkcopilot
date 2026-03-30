# Campaign Prompt: Close the Next MATLAB-Native Parity Gaps in `matlabv2native`

Use this prompt to continue the native MATLAB backend campaign from the current repo state after the `pulse` / `ramp` / `sine` parity-expansion checkpoint.

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

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed parity-expansion work.

## Current State You Must Respect

The repo already has:

- the existing Python backend, which must remain intact and authoritative for legacy and parity/debug use
- the existing MATLAB bridge to Python
- `matlabv1`, which must keep working
- `matlabv2native`, which now has:
  - native symbolic explicit-ODE preview
  - native eligibility checks
  - native explicit-ODE Simulink lowering for current supported native cases
  - native MATLAB/Simulink simulation
  - a MATLAB ODE numerical reference for current supported native cases
  - default runtime execution for current native cases without requiring Python build/sim
  - explicit Python parity mode through `ParityMode="python"`
  - additive timing fields for preview/build/sim/reference/parity/total wall time
  - committed coupled explicit-system runtime coverage
  - committed runtime-native support for:
    - constant
    - step / delayed step
    - pulse
    - ramp
    - sine
    - unsupported symbolic input via `MATLAB Function` source fallback

Current focused tests already green at handoff:

```bash
.venv/bin/python -m pytest pipeline/tests/test_matlab_bridge.py -q
SIMULINKCOPILOT_RUN_MATLAB_TESTS=1 .venv/bin/python -m pytest backend/tests/test_backend_integration.py -q -k "matlabv1 or matlabv2native"
```

Results at handoff:

- `15 passed`
- `10 passed, 3 deselected, 6 subtests passed`

The parity ledger already exists at:

- [docs/matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)

## Core Strategic Gap You Must Address

`matlabv2native` is now credible for a small native runtime set, but the next parity gap is no longer the architecture. It is breadth and front-door quality.

The main unresolved issues are:

- widened families like `pulse`, `ramp`, and `sine` are parity-close mainly through the caller-workspace input-spec struct path, not broad symbolic-expression normalization parity yet
- the next waveform families are still missing:
  - `square`
  - `sawtooth`
  - `triangle`
- coupled explicit systems have committed runtime-native coverage, but parity-mode coverage is still weaker than it should be
- the public heavy comparison surface is still not strong enough for broad parity inspection
- front-door behavior is still uneven:
  - `matlab_symbolic` is the main native path
  - equation text is still partial/delegated
  - LaTeX is still delegated
  - structured ODE specs are still delegated

The next milestone is:

- promote the next waveform family set to runtime-native
- improve symbolic front-door recognition for widened native families
- strengthen parity-mode coverage, especially for coupled explicit systems
- make the comparison/reporting surface strong enough to inspect mismatches without bloating the default runtime path

## Mission

Advance `matlabv2native` from “small runtime-native set with parity ledger” to “broader waveform-capable native backend with clearer symbolic/front-door parity”.

You must move the MATLAB-native backend closer to the Python backend in:

- waveform family coverage
- symbolic-expression recognition
- coupled-system parity coverage
- comparison/reporting quality
- front-door clarity

You must keep the architecture additive.

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while widening parity.
5. Every new MATLAB-native capability must have automated parity checks against Python or an explicit documented reason why the comparison is not yet meaningful.
6. Every generated model must still simulate and validate.
7. Do not weaken MATLAB-reference validation just to claim wider runtime-native support.
8. Do not mark a family as runtime-native unless both native Simulink lowering and MATLAB numerical-oracle evaluation exist and are tested.
9. Do not silently reintroduce Python into the default runtime path for runtime-native cases.
10. Do not claim symbolic/front-door parity for a family unless the test coverage actually proves it.

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

Close the next parity gap after `pulse` / `ramp` / `sine` promotion by doing all of the following:

- promote `square`, `sawtooth`, and `triangle` to runtime-native when technically justified
- improve symbolic-expression recognition so widened waveform families do not rely only on struct-style input specs
- strengthen coupled explicit-system parity coverage in parity mode
- expand the heavy comparison surface without bloating the default runtime path
- keep the parity ledger accurate and explicit

## Required Major Workstreams

### Workstream 1: Parity Ledger Maintenance

Keep the parity ledger current as the source of truth.

Update it before and after each promotion step.

At minimum, explicitly track for each family:

- runtime-native
- MATLAB-reference supported
- Python parity supported
- symbolic-expression native recognition
- struct-input-spec native recognition
- delegated

For the waveform families, track at minimum:

- constant
- step
- delayed step
- pulse
- ramp
- sine
- square
- sawtooth
- triangle
- unsupported symbolic expression via `MATLAB Function` fallback

### Workstream 2: Waveform Family Promotion

Promote the next waveform family set to runtime-native:

- square
- sawtooth
- triangle

Requirements:

- implement native Simulink source lowering
- implement MATLAB numerical-oracle evaluation
- keep default runtime path Python-free for those promoted cases
- add explicit Python parity tests
- preserve readable diagrams and editable parameters

If one of these families cannot be promoted cleanly yet, document the reason and leave it delegated rather than overclaiming support.

### Workstream 3: Symbolic-Expression Recognition Parity

Improve native symbolic-expression recognition for widened families so the backend is not limited to caller-workspace struct-style input specs.

At minimum, strengthen native recognition for:

- pulse
- ramp
- sine

Then extend the same approach to newly promoted waveform families where feasible:

- square
- sawtooth
- triangle

Requirements:

- do not claim broad symbolic parity unless the matcher is actually reliable
- compare recognized family/type against the Python backend where meaningful
- if a family is runtime-native only through struct-style input specs, say so explicitly in docs and tests

### Workstream 4: Coupled Explicit-System Parity

The runtime-native coupled explicit case now has committed coverage. The next step is to make parity-mode coverage equally explicit.

Requirements:

- add committed parity-mode tests for at least one coupled explicit system
- compare:
  - route/classification
  - first-order state set/order
  - source block family
  - native runtime traces vs MATLAB reference
  - Python traces vs MATLAB reference
  - native vs Python traces

Do not limit coupled-system confidence to runtime-only smoke behavior.

### Workstream 5: Heavy Comparison API

The default runtime API should remain lean. Strengthen the heavy comparison surface separately.

You must either:

- expand `matlabv2native.compareWithPython(...)`

or

- add a new additive API such as:
  - `matlabv2native.compareAll(...)`
  - `matlabv2native.compareWithParity(...)`

For native-eligible explicit ODEs, the heavy comparison API should compare where meaningful:

- route/classification
- first-order state set/order
- native-recognized input family/type
- source block family
- runtime mode vs parity mode
- native runtime traces vs MATLAB reference
- Python traces vs MATLAB reference
- native vs Python traces
- validation surfaces

Mismatches should be explicit and structured enough to support tests and ledger updates.

### Workstream 6: Front-Door Clarity

Do not broaden native claims without clarifying front-door behavior.

At minimum:

- make `matlab_symbolic` behavior explicit and well-tested
- keep equation text behavior explicit:
  - native where truly supported
  - delegated where not
- keep LaTeX explicitly delegated unless real native support is added
- keep structured ODE specs explicitly delegated unless real native support is added

If you improve equation-text intake during this phase, add parity tests and update the ledger. If not, document the boundary clearly.

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
- ramp
- sine
- square
- sawtooth
- triangle
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

- committed runtime-native integration coverage for `square`, `sawtooth`, and `triangle` if promoted
- explicit Python parity tests for any newly promoted waveform families
- at least one committed coupled explicit-system parity-mode test
- at least one test proving widened symbolic-expression recognition works natively for an already-promoted family such as `sine` or `ramp`
- tests proving runtime-native cases still do not require Python in the hot path
- tests proving Python parity remains available explicitly
- timing-field tests ensuring Python parity timing is only populated when parity mode is requested

If a family cannot be promoted cleanly in this phase, add a test that proves the delegation boundary instead of silently leaving it ambiguous.

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current
- document which waveform families are:
  - runtime-native
  - MATLAB-reference supported
  - Python-parity supported
  - symbolic-recognition supported
  - struct-spec-only native
  - delegated
- document the heavy comparison API boundary: lean runtime vs heavy parity
- document coupled explicit-system parity status explicitly

Document explicitly:

- which cases no longer require Python during normal execution
- which families still require struct-style input specs for native operation
- which families are truly native from symbolic-expression intake
- which cases still delegate

## Failure Conditions

You fail this campaign if you:

- break current Python behavior
- break `matlabv1`
- silently reintroduce Python into the default runtime path for runtime-native cases
- claim waveform or symbolic parity without tests and ledger updates
- widen Simulink lowering without widening the MATLAB numerical oracle to match
- leave coupled-system parity implicit instead of committed
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which waveform families are now parity-close or parity-complete
- which families are runtime-native
- which families are symbolic-native vs struct-spec-only native
- which coupled-system parity cases now pass
- what still blocks broader parity

## Concrete First Step

Start by making the next parity jump concrete and test-backed:

1. promote `square`, `sawtooth`, and `triangle` if they can be supported cleanly in both:
   - native Simulink lowering
   - MATLAB numerical-oracle evaluation
2. add explicit Python parity tests for those waveform families
3. add a committed coupled explicit-system parity-mode test
4. strengthen symbolic-expression native recognition for at least one already-promoted family:
   - `sine`
   - or `ramp`
5. update the parity ledger to distinguish:
   - symbolic-native
   - struct-spec-only native
   - delegated

Only after that is clean and green should you widen further to nonlinear source families such as `saturation`, `dead_zone`, `sign`, `abs`, `min/max`, and unary math families such as `atan`, `atan2`, `exp`, `log`, and `sqrt`.
