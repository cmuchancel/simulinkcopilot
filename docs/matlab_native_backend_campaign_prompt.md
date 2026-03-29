# Campaign Prompt: Build a Native MATLAB Backend Beside the Existing Python Backend

Use this prompt when assigning a long-running implementation campaign to build a native MATLAB backend for this repo.

## Prompt

You are working inside the `simulinkcopilot` repository. Your task is to build a **native MATLAB backend** for the equation-to-Simulink pipeline **in addition to** the existing Python backend.

This is an additive architecture project. You must **not** delete, replace, or destabilize the current Python pipeline while building the MATLAB-native path.

The end state should be:

- the existing Python backend still works
- the existing MATLAB bridge to the Python backend still works
- a new native MATLAB backend exists beside it
- both backends can be run on the same inputs
- both backends can be compared for input interpretation, route selection, generated structure, and validation behavior

You must work like a careful systems engineer, not like a demo hacker.

## Non-Negotiable Constraints

1. Do not remove or rewrite away the current Python backend.
2. Do not break current user-facing workflows while introducing the MATLAB-native backend.
3. Treat the current Python backend as the oracle during migration until native MATLAB parity is demonstrated.
4. Every new MATLAB-native capability must have parity checks against the Python backend.
5. Every build path that produces a Simulink model must still simulate and validate.
6. Do not silently diverge semantics between the MATLAB backend and Python backend.
7. If semantics differ, stop, diagnose, and fix or explicitly mark the case unsupported in the MATLAB-native backend.

## Git / Push Discipline

You must preserve progress aggressively.

Before major implementation work:

1. Create or confirm a feature branch dedicated to the MATLAB-native backend campaign.
2. Make an initial baseline commit that preserves the current working state.
3. Push that baseline immediately.

During the campaign:

1. Work in small, defensible phases.
2. After each completed phase:
   - run the relevant tests
   - commit with an intentional message
   - push the branch
3. Do not accumulate large unpushed refactors.
4. If blocked for more than one phase, push the latest stable checkpoint before continuing.

If pushing is impossible because the remote or auth is unavailable, report that explicitly and continue with local commits, but do not pretend pushes happened.

## Primary Objective

Build a new native MATLAB backend, likely under a package such as `matlab/+matlabv2native` or similar, that can:

1. accept the same supported input families as the Python backend
2. normalize and classify equations natively in MATLAB
3. generate deterministic Simulink diagrams natively from MATLAB
4. simulate and validate those models
5. compare MATLAB-native results against the Python backend on the same problems

The new backend must be **standalone from the MATLAB user’s perspective**, while remaining additive to the repo architecture.

## Required Deliverable Shape

Implement a native MATLAB backend with clear separation between:

- MATLAB-facing API
- MATLAB-native parsing / normalization
- MATLAB-native symbol classification
- MATLAB-native equation canonicalization
- MATLAB-native first-order conversion
- MATLAB-native input-source recognition and lowering
- MATLAB-native Simulink model builder
- MATLAB-native validation / comparison harness
- MATLAB-vs-Python parity harness

The old path must remain available.

## Required Public API

Create a native MATLAB package with a clean public surface, for example:

- `matlabv2native.setup`
- `matlabv2native.analyze`
- `matlabv2native.generate`
- `matlabv2native.validate`
- `matlabv2native.compareWithPython`

You may choose a slightly different naming scheme if it is cleaner, but it must be:

- MATLAB-first
- explicit
- documented
- additive

Do not remove `matlabv1` or the older wrappers.

## Required Scope

Implement the native MATLAB backend in phases, but the overall campaign must target the whole supported workflow.

### Phase 1: Architecture and Safe Scaffolding

Deliver:

- new MATLAB-native package structure
- no-op or thin-shell public entrypoints
- clear internal module boundaries
- docs describing how the native backend differs from `matlabv1`

Must preserve all existing behavior.

### Phase 2: Native MATLAB Input Intake

Support the same front-door families the repo currently supports, as applicable:

- symbolic MATLAB equations
- MATLAB-style equation text
- LaTeX if realistically supportable in MATLAB
- structured ODE specs

If LaTeX cannot be supported natively in the first cut, keep it routed to Python and document that boundary clearly.

### Phase 3: Native MATLAB Symbol Classification

Implement deterministic classification of:

- states
- derivative-derived states
- inputs
- parameters
- algebraics
- time variable

This must match the Python backend as closely as possible.

### Phase 4: Native MATLAB Input Signal Recognition

Recognize the same meaningful input families currently supported by the Python path, including at minimum:

- constant
- step
- shifted step
- impulse approximation
- pulse / window
- ramp
- sine / cosine
- square
- sawtooth
- triangle
- saturation
- dead zone
- abs
- sign
- relay
- min / max
- native trig / inverse trig / math-function mappings where possible
- unsupported symbolic expressions lowered to a MATLAB Function block fallback

### Phase 5: Native MATLAB Simulink Lowering

Generate diagrams natively in MATLAB using Simulink APIs.

Requirements:

- deterministic naming where feasible
- readable diagrams
- avoid irrelevant visual plumbing
- keep editable user-visible inputs and parameters visible
- use native source blocks when a native block exists
- only use MATLAB Function fallback when native block composition is not possible

### Phase 6: Native MATLAB Simulation and Validation

Any generated Simulink model must:

- simulate
- produce outputs for the relevant states/signals
- validate numerically

If a native MATLAB analytical/reference solve is practical, use it. If not, compare against the Python reference solver while the native backend matures.

### Phase 7: MATLAB-vs-Python Parity Harness

Create a formal parity harness that runs the same problems through:

- Python backend
- native MATLAB backend

and compares:

- inferred input symbols
- inferred parameters
- inferred state variables
- route / classification
- recognized input-spec type
- generated model block families
- numerical simulation results

This parity harness is mandatory.

## Required Comparison Matrix

You must compare the MATLAB backend and Python backend on a broad matrix of inputs.

At minimum include:

- explicit first-order ODEs
- second-order symbolic ODEs reduced to first order
- parameterized systems
- constant input
- step input
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
- min/max
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`
- one unsupported-but-valid symbolic input that should fall back to MATLAB Function

For each case, compare:

1. symbol classification
2. input interpretation
3. generated source block choice
4. simulation traces
5. pass/fail validation status

## Required Testing

You must add tests in both MATLAB-facing and Python-facing forms where useful.

Minimum expectations:

- MATLAB-engine-backed integration tests in Python
- direct MATLAB-side smoke or regression tests where practical
- parity tests comparing both backends on the same cases
- tests that prove the old Python path still works
- tests that prove `matlabv1` still works

Do not rely on ad hoc manual testing only.

## Required Documentation

Update docs incrementally as the implementation matures.

Required documentation topics:

- architecture of the native MATLAB backend
- public MATLAB API
- what is native vs still delegated
- parity status vs Python backend
- unsupported cases and why
- how to run parity tests
- how to run native MATLAB validation

Maintain an explicit parity ledger if helpful.

## Failure Conditions

You fail this campaign if you do any of the following:

- break the existing Python backend
- silently change current user workflows without preserving compatibility
- claim parity without automated comparison
- add native MATLAB behavior that disagrees with Python without flagging it
- skip simulation/validation on generated diagrams
- introduce a native backend that cannot be tested repeatably

## Execution Style

Work in small phases. Be explicit. Preserve working states often.

At the end of each phase, report:

- what changed
- what was tested
- what was pushed
- what parity cases pass
- what remains divergent

## Suggested First Steps

1. Create and push a baseline branch checkpoint.
2. Add the native MATLAB package scaffold and docs.
3. Build a parity harness before large native rewrites.
4. Start with explicit ODE support first.
5. Use the Python backend as the reference oracle until the MATLAB-native path is proven.

## Final Goal

Produce a robust, additive, test-backed, native MATLAB backend that can stand beside the Python backend, with explicit parity checks proving whether both interpret the same inputs the same way and produce the same engineering result.

