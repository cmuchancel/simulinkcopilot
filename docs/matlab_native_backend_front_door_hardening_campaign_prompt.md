# Campaign Prompt: Harden the MATLAB-Symbolic Front Door End-to-End

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of turning the `matlab_symbolic` front door into a strict, well-diagnosed, high-support entrypoint.

This campaign is not just about widening support. It is about making the front door explicit, deterministic, and honest:

- require the user to provide `State` / `States`
- reject ambiguous or unsupported inputs early
- report exactly what failed, where it failed, why it failed, and how to fix it
- widen native support for as many MATLAB-symbolic input/system families as can be validated honestly
- produce stage-by-stage readouts so failure analysis is inspectable
- add an additive diagnosis layer that can generate a likely-cause explanation from structured diagnostics without requiring human triage during the run

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the already-pushed checkpoints, including the current latest checkpoint:

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
- phase-11 nonlinear symbolic-family checkpoint: `2999600`
- phase-12 unary-math symbolic-family checkpoint: `dbd12d9`
- phase-13 complex benchmark checkpoint: `396cb2d`
- phase-14 acrobot benchmark checkpoint: `638d6e7`
- phase-15 bounded native DAE symbolic route checkpoint: `dc71d2d`
- phase-16 native pure-time RHS lowering checkpoint: `0a9224b`
- phase-17 vector-form symbolic systems checkpoint: `fc8724b`

Do not restart the campaign from scratch. Continue from the additive MATLAB-native scaffold and the already-pushed symbolic/native-runtime work.

## Core Product Decision

The MATLAB-symbolic front door is now intentionally strict.

The user must provide `State` / `States`.

The campaign must remove the possibility of a silent or heuristic "no-state" path for `matlab_symbolic` generation. If the caller does not provide `State` / `States`, the front door must fail explicitly with a user-facing diagnostic that says:

- what is missing
- why it is required
- how to fix it

Do not leave state inference as an accidental convenience path. State order must be user-owned.

## Scope Lock

This campaign is only about:

- the `matlab_symbolic` front door
- strict front-door validation and diagnostics
- required explicit state declaration
- high-quality route classification and failure reporting
- widening native support where validation/oracle coverage can support it
- structured stage-by-stage readouts
- additive deterministic and AI-assisted failure diagnosis

Do not broaden this campaign into:

- LaTeX parity
- equation-text parity
- structured ODE-spec parity
- broad Python-polish work unrelated to front-door trustworthiness
- unrelated UI work
- unrelated performance tuning beyond what is needed for diagnostics or support widening

Python must not regress, but Python is not the target. The target is a hard, explicit, debuggable MATLAB-symbolic front door.

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
  - committed nonlinear benchmark runtime coverage for:
    - cart-pendulum
    - planar quadrotor
    - acrobot
  - bounded reducible DAE support for one algebraic variable solved from one algebraic equation before native explicit-ODE lowering
  - native pure-time RHS lowering for recognized time-only expressions such as `sin(t)` and `t + 1`
  - vector-form symbolic support for plain vector-valued `sym` / `symfun` equation arrays such as:
    - `diff(X,t) == A*X`
    - `diff(X,t) == A*X + B*u(t)`
  - explicit user-provided state-order preservation for those vector-form systems
  - direct symbolic recognition and runtime-native support for:
    - constant
    - step / delayed step
    - pulse
    - ramp
    - sine
    - square
    - saturation
    - dead zone
    - sign
    - abs
    - min/max
    - atan
    - atan2
    - exp
    - log
    - sqrt
  - runtime-native expression/input-spec support for:
    - sawtooth
    - triangle
  - fallback `MATLAB Function` source/RHS lowering for unsupported expressions inside the native explicit-ODE lane
  - delegation outside the current native explicit-ODE lane

Current docs to keep updated:

- [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)
- [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)

Current main test surface:

- `backend/tests/test_backend_integration.py`

## Strategic Goal

Make `matlabv2native` feel like a trustworthy compiler front door instead of a permissive parser with opaque failures.

This campaign succeeds only if all of the following are true:

1. the user must provide `State` / `States`
2. invalid or unsupported input is rejected at the earliest responsible stage
3. every failure identifies:
   - failure stage
   - exact condition
   - support status
   - likely cause
   - suggested fix
4. supported native families are widened aggressively but honestly
5. every stage emits readouts that make the route and failure boundary inspectable
6. an additive diagnosis layer can summarize likely problems automatically from those readouts without needing human intervention during the campaign

## Mission

Advance `matlabv2native` from “native backend with growing support” to “strict, explicit, self-diagnosing MATLAB-symbolic front door.”

You must close gaps in:

- required option validation
- explicit error surfacing
- support-boundary clarity
- route classification diagnostics
- lowering diagnostics
- simulation/reference validation diagnostics
- breadth of supported input families
- fallback explanation quality
- readout/trace visibility
- additive AI-assisted diagnosis

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently change semantics while hardening validation.
5. `State` / `States` must become required for the `matlab_symbolic` front door.
6. Every new MATLAB-native capability must have automated tests.
7. Every generated model must still simulate and validate.
8. Do not weaken MATLAB-reference validation to make support claims easier.
9. Do not overclaim support for inputs or system forms unless tests and validation prove it.
10. If something is unsupported, say so explicitly and explain the closest supported fix.
11. If an internal failure occurs, surface both a user-facing diagnosis and the lower-level raw details needed for debugging.
12. If an AI diagnosis layer cannot be made trustworthy, ship deterministic rule-based diagnosis first and keep the AI layer additive.
13. This campaign must be executable end-to-end without stopping for user clarification unless there is a genuine external blocker such as credentials or unavailable MATLAB features.

## Git / Push Discipline

For every completed phase:

1. run focused tests
2. commit with an intentional message
3. push immediately

Do not accumulate large unpushed changes.

If blocked, push the last stable checkpoint before continuing.

## Primary Objectives For This Campaign

Close these gaps in this order:

1. require explicit `State` / `States`
2. formalize front-door stage diagnostics
3. formalize user-facing error taxonomy and fix guidance
4. widen supported families aggressively but honestly
5. add structured readouts for every major stage
6. add additive diagnosis summarization over those readouts
7. document all boundaries explicitly

At the same time:

- keep the existing native path stable
- keep benchmark anchors green
- keep `MATLAB Function` fallback and delegation intentional

## Required Major Workstreams

### Workstream 1: Make `State` / `States` Mandatory

For `matlab_symbolic`, the caller must explicitly declare states.

Requirements:

1. Fail immediately if `State` / `States` is not provided.
2. Emit a specific diagnostic code for missing state declaration.
3. Explain exactly how to fix it with a concrete example.
4. Do not silently infer state order from equations in generate/build flows.
5. If preview/analyze continues to inspect equations without build, make the boundary explicit in the result or error surface.

At minimum, add diagnostics for:

- missing `State`
- empty `State`
- duplicate state names
- state names that do not match the symbolic system
- state names that reference algebraics or inputs
- state count mismatch
- invalid ordering relative to the scalarized system

### Workstream 2: Build a Front-Door Error Taxonomy

Create an explicit front-door error/diagnostic taxonomy for `matlab_symbolic`.

Every failure should have, at minimum:

- a stable code
- stage name
- severity
- short summary
- detailed explanation
- likely cause
- suggested fix
- support status:
  - supported
  - unsupported
  - delegated
  - internal_error

Stages must include at least:

- option validation
- source-type validation
- caller capture
- symbolic normalization
- scalarization
- state binding
- route classification
- native eligibility
- lowering
- simulation
- MATLAB reference solve
- parity

Do not throw opaque MATLAB exceptions straight to the user without wrapping them in this structure.

### Workstream 3: Add Structured Readouts / Trace Surface

Add stage-by-stage readouts so users and downstream diagnosis can inspect what happened.

At minimum, record:

- source type
- original representation kind
- scalarized equation count
- declared states
- bound states
- algebraics
- inputs
- parameters
- time variable
- route classification
- native eligibility outcome
- native source/RHS block families
- fallback usage
- delegation reason
- MATLAB reference outcome
- parity outcome when requested
- timing per stage
- raw underlying exception text when a stage fails

These readouts must be available in result structs for successful runs and in structured error/diagnostic payloads for failed runs wherever practical.

Do not hide the internal route decisions.

### Workstream 4: Widen Supported Inputs Aggressively But Honestly

Promote as many input and expression families as can be supported natively and validated honestly.

Priority order:

1. complete current direct-symbolic and runtime-native families with better diagnostics
2. widen remaining realistic waveform/input families
3. widen readable native RHS lowering where standard Simulink blocks exist
4. reduce avoidable `MATLAB Function` fallback

At minimum, review and harden support claims for:

- constant
- step / delayed step / biased step / scaled step
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
- atan
- atan2
- exp
- log
- sqrt

Also probe and either support or explicitly reject with good diagnostics:

- cosine
- multi-input affine systems
- parameterized symbolic systems
- matrix/vector nonlinear systems
- impulse-style approximations
- additional canonical MATLAB rewrites of already-supported families

Do not overclaim anything MATLAB itself does not represent cleanly.

### Workstream 5: Harden Unsupported / Delegated Boundaries

Unsupported and delegated cases must be explicit and useful.

For every unsupported or delegated case, tell the user:

- what pattern was recognized
- why it is not natively supported
- whether it is delegated or rejected
- what the supported alternative is, if one exists
- whether rewriting the equations, adding explicit state declarations, or changing front doors would help

Do not allow vague “not eligible” or “failed during build” messages to remain the main user surface.

### Workstream 6: Add Additive Diagnosis Layer

Add a diagnosis layer that summarizes likely problems from structured readouts.

This layer must be additive:

- correctness must not depend on AI
- deterministic structured diagnostics are mandatory
- AI/rule-based summarization is layered on top

Minimum acceptable design:

1. deterministic rule-based diagnosis over the structured readout/error payload
2. optional AI-assisted summary that can consume the same payload and produce:
   - likely root cause
   - likely fix
   - confidence / uncertainty note

If a repo-local or product-available LLM/agent path exists and can be used safely, integrate it.

If a trustworthy integrated AI path does not exist, still implement the full structured payload and deterministic diagnosis surface so the AI layer can be added later without changing the core error model.

Do not block this campaign on model availability.

### Workstream 7: Matrix / Vector Hardening Under the Same Front Door

The current vector-form support must be folded into the same strict front-door rules.

Requirements:

1. explicit `State` order remains mandatory
2. matrix/vector representation kind is reported explicitly
3. scalarization result is reported explicitly
4. flattening order is explicit and test-backed
5. irreducible vector/matrix algebraic cases must diagnose cleanly
6. `symmatrix` must either:
   - be truly supported and tested
   - or be explicitly out of scope with a clean diagnostic

Do not let matrix/vector support remain a half-hidden implementation detail.

### Workstream 8: Benchmark-Style Hardening Anchors

Add committed regression anchors that test not just success paths, but front-door behavior.

At minimum include:

- one missing-`State` hard failure case
- one mismatched-`State` hard failure case
- one supported scalar success case
- one supported vector-form success case
- one supported reducible DAE success case
- one explicit delegated irreducible DAE case
- one unsupported family case with a precise fix suggestion
- one internal-failure wrapping test if a realistic trigger exists

## Required Error / Diagnostic Surface

At minimum, expose or standardize fields equivalent to:

- `Code`
- `Stage`
- `Summary`
- `Details`
- `LikelyCause`
- `SuggestedFix`
- `SupportStatus`
- `RepresentationKind`
- `DeclaredStates`
- `BoundStates`
- `ScalarizedEquationCount`
- `Route`
- `RouteStatus`
- `FallbackUsed`
- `Delegated`
- `UnderlyingErrorIdentifier`
- `UnderlyingErrorMessage`
- `Readout`

If the exact field names differ, that is fine, but the surface must carry this information.

## Required Readout / Trace Matrix

At minimum, every run should be able to explain:

1. what front door was used
2. what symbolic representation was detected
3. whether scalarization occurred
4. which states were declared
5. which states were bound after validation
6. which route was chosen
7. whether native lowering was eligible
8. what support family was recognized for sources and RHS terms
9. whether `MATLAB Function` fallback was used
10. whether delegation occurred
11. whether simulation succeeded
12. whether MATLAB reference validation succeeded
13. whether Python parity was run
14. what stage failed if the run did not complete

## Required Testing

Add or extend tests in:

- MATLAB-engine-backed Python integration tests
- direct MATLAB-side smoke/regression tests where practical
- route/preview tests where practical

Minimum expectations for this campaign:

- a committed test proving `State` is required for `matlab_symbolic`
- committed tests for the main invalid-state failure modes
- committed tests for structured diagnostics on unsupported/delegated cases
- committed tests for stage/readout population on successful native cases
- committed tests for stage/readout population on failed cases where practical
- committed tests for deterministic diagnosis summaries
- committed tests for any AI-diagnosis wrapper in a way that does not require live model availability
- committed tests for widened supported families you promote
- committed tests that vector/matrix supported cases still pass

## Required Documentation

Update docs as you go:

- keep [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md) current
- keep [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md) current

Also add or update a dedicated front-door diagnostics doc if that is the cleanest place to explain the error model.

Document explicitly:

- that `State` / `States` is required
- every major failure class
- every major support/delegation boundary
- which matrix/vector forms are supported
- whether `symmatrix` is supported or out of scope
- what the stage readouts contain
- how deterministic diagnosis works
- whether and how an additive AI-diagnosis layer is used

## Failure Conditions

You fail this campaign if you:

- leave a no-`State` path available for `matlab_symbolic` generation
- keep opaque failures as the main user surface
- claim support without tests and validation
- widen support without documenting the boundary
- add AI dependence without deterministic diagnostics beneath it
- leave vector/matrix behavior implicit
- break current Python behavior
- break `matlabv1`
- leave large unpushed local changes

## Execution Style

Work in small phases. Report after each phase:

- what changed
- what was tested
- what was pushed
- which front-door failure classes are now explicit
- which support families are now native vs delegated vs unsupported
- what readouts are now available
- whether diagnosis is deterministic only or deterministic plus AI-assisted
- what still blocks a truly hardened front door

Do not stop for user input unless there is a real external blocker.

## Concrete First Step

Start by hardening the front door before widening more support:

1. make `State` / `States` mandatory for `matlab_symbolic`
2. add the structured front-door error taxonomy
3. add stage/readout scaffolding
4. add deterministic diagnosis summaries
5. add regression tests for the main missing-state and invalid-state failures
6. update docs honestly

Then immediately widen support only where those diagnostics and readouts are already in place.

Do not leave this campaign with broader support but still-murky failures.
