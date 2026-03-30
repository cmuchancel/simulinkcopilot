# Campaign Prompt: Finish The MATLAB-Symbolic Native Tail

Use this prompt to continue the native MATLAB backend campaign from the current repo state after the symbolic math-family native lowering pass.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the current repo state after the MATLAB-symbolic native runtime now covers:

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
- `atan`
- `atan2`
- `exp`
- `log`
- `sqrt`

and after simple affine RHS expressions such as `-x + u` lower with native math blocks instead of defaulting to a `MATLAB Function` block.

## Scope Lock

This campaign is only about:

- the `matlab_symbolic` front door
- explicit ODE workflows
- readable native Simulink generation
- closing the remaining honest tail of the MATLAB-native path

Do not spend this campaign on:

- LaTeX
- equation text
- structured ODE specs
- DAE / descriptor parity
- making Python parity the design center

Python must stay unbroken, but it is not the target.

## Remaining Real Gaps

The main remaining MATLAB-symbolic gaps are now:

1. `sawtooth` / `triangle` are still expression/input-spec runtime-native rather than truly robust direct-symbolic-native
2. `cosine` is not yet claimed and tested as a first-class symbolic family even though the native sine-like path is nearby
3. impulse-style symbolic inputs are still missing
4. some readable math expressions may still fall back to `MATLAB Function` in places where native block composition should exist
5. the docs and ledger must stay explicit about what is truly direct-symbolic-native vs what is only runtime-native through expression/input-spec shaping

## Mission

Finish the MATLAB-symbolic explicit-ODE native tail without broadening scope.

You must focus on:

- hardening the repeating-sequence symbolic boundary honestly
- promoting `cosine` if the native path is truly there
- deciding whether impulse approximation belongs in this native scope now
- eliminating any remaining unnecessary `MATLAB Function` fallback in simple source/RHS cases
- keeping docs and tests aligned with the real boundary

## Non-Negotiable Constraints

1. Do not remove the Python backend.
2. Do not regress `matlabv1`.
3. Do not regress existing Python workflows.
4. Do not silently reintroduce Python into the default runtime path for runtime-native symbolic cases.
5. Every new native claim must have automated tests.
6. Every generated model must still simulate and validate against the MATLAB numerical reference path.
7. Do not overclaim direct-symbolic support for `sawtooth` / `triangle` unless MATLAB symbolic forms are actually reliable.
8. Keep `MATLAB Function` fallback only for genuinely unsupported symbolic expressions.

## Primary Objective

Close the remaining high-value MATLAB-symbolic explicit-ODE gaps in this order:

1. settle `sawtooth` / `triangle` honestly:
   - either harden direct symbolic recognition
   - or explicitly document them as expression/input-spec native only
2. promote and test `cosine` if it is truly native already
3. decide whether impulse approximation belongs in the native supported matrix now
4. keep cleaning RHS/source lowering so readable expressions stay readable

## Required Testing

At minimum:

- add committed tests for any newly claimed direct-symbolic family
- add tests that prove the direct-symbolic vs struct-spec-only boundary for `sawtooth` / `triangle`
- add tests that assert readable native block families instead of `MATLAB Function` where support exists
- keep the focused MATLAB-backed integration suite green for the touched surface

## Required Documentation

Update:

- [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)
- [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)

Document explicitly:

- which families are direct-symbolic-native
- which are struct-spec-only native
- which still delegate
- which still rely on `MATLAB Function` fallback

## Concrete First Step

Start by testing whether `cosine` is already one patch away from being a real claimed symbolic family and whether `sawtooth` / `triangle` can be recognized directly from the symbolic forms MATLAB actually preserves.

If not, do not force the claim. Tighten the boundary and move on.
