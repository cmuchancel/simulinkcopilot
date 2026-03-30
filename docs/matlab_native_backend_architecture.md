# Native MATLAB Backend Architecture

This document describes the additive native MATLAB backend effort that sits beside the existing Python backend.

## Current Status

`matlabv2native` currently exists as a **phase-9 symbolic-nonlinear-runtime checkpoint**:

- it provides a native MATLAB public API
- it performs MATLAB-side source-type, symbol-metadata, and explicit-ODE preview
- it can build eligible MATLAB symbolic explicit ODEs natively in Simulink
- it simulates those native models in MATLAB
- it computes a MATLAB ODE reference solve for current native explicit-ODE anchor cases
- it validates current native explicit-ODE anchor cases against the MATLAB numerical reference in the default runtime path
- it keeps Python parity available explicitly for those same anchor cases
- it now covers the widened runtime-native waveform set through the native symbolic/input-spec path:
  - pulse
  - ramp
  - sine
  - square
- it now also covers runtime-native expression/input-spec waveform lowering for:
  - sawtooth
  - triangle
- it now recognizes direct MATLAB symbolic waveform expressions for:
  - pulse
  - ramp
  - sine
  - square
- it now recognizes and lowers direct MATLAB symbolic nonlinear input expressions for:
  - saturation
  - dead zone
- it now has committed native-runtime integration coverage for a coupled explicit system
- it now has committed parity-mode integration coverage for a coupled explicit system
- it reports additive timing fields for preview, build, simulation, reference solve, optional Python parity, and total wall time
- it still delegates non-eligible cases to the existing Python backend

This is intentional. The goal is to build the native path safely while keeping the Python backend as the oracle.

## Public API

Current public entrypoints:

- [matlabv2native_setup.m](../matlabv2native_setup.m)
- [setup.m](../matlab/+matlabv2native/setup.m)
- [analyze.m](../matlab/+matlabv2native/analyze.m)
- [generate.m](../matlab/+matlabv2native/generate.m)
- [validate.m](../matlab/+matlabv2native/validate.m)
- [compareWithPython.m](../matlab/+matlabv2native/compareWithPython.m)

Recommended bootstrap:

```matlab
info = matlabv2native_setup();
```

## Current Behavior

### Native in MATLAB

These behaviors are implemented on the MATLAB side today:

- source-type inference
- caller workspace capture
- equation-string extraction
- basic time-variable inference
- basic derivative/state inference
- basic input vs parameter inference from caller-workspace values
- explicit-ODE route preview for MATLAB symbolic equations when `odeToVectorField` succeeds
- native first-order state preview for those explicit ODEs
- native-lowering eligibility checks for MATLAB symbolic explicit ODEs
- native Simulink lowering for the current explicit-ODE anchor cases
- native simulation of those generated explicit-ODE models
- native MATLAB ODE reference solving for the current explicit-ODE anchor cases
- default runtime-mode generation and validation for those current anchor cases without requiring a Python build/sim
- explicit Python parity mode for those current anchor cases through `ParityMode="python"`
- committed integration coverage for a coupled explicit native-runtime case
- native input-source lowering for the currently supported native families:
  - constant
  - step / delayed step
  - pulse
  - ramp
  - sine
  - square
  - sawtooth via expression/input spec
  - triangle via expression/input spec
  - saturation
  - dead zone
  - sign
  - abs
  - min/max
  - unsupported symbolic input expression lowered to a MATLAB Function source block
- native affine RHS lowering for simple explicit-ODE expressions such as:
  - `-x + u`
  - `x - 2*y`
  - simple constant offsets combined with state/input/parameter signals
- direct symbolic-expression recognition for:
  - pulse
  - ramp
  - sine
  - square
  - saturation
  - dead zone
  - sign
  - abs
  - min/max
- runtime/performance timing capture for:
  - preview analysis
  - native model build
  - native Simulink simulation
  - MATLAB numerical reference solve
  - optional Python parity
  - total wall time
- parity comparison against the Python backend for:
  - states
  - algebraics
  - inputs
  - parameters
  - time variable
  - route
  - first-order state order
  - source block family
  - native vs MATLAB-reference simulation traces
  - Python vs MATLAB-reference simulation traces
  - native vs Python simulation traces
  - validation status with MATLAB reference as the primary oracle

The current family comparison is semantic rather than purely literal in one important case:

- native `SquareWave` lowering is treated as parity-equivalent to the Python backend's composed `Sum` implementation for the same symbolic square-wave input

### Still Delegated to Python

These behaviors still use the existing Python backend, either as the primary execution path or as the oracle:

- authoritative handling for non-symbolic front doors
- non-explicit or ambiguous systems
- broader normalization beyond the current explicit-ODE native preview boundary
- the Python oracle model used as an explicit secondary parity surface beside the MATLAB numerical reference
- Python parity for `sawtooth` / `triangle` expression-input paths, which is still pending because the current Python oracle model fails during model initialization for those cases
- Python parity for `saturation` / `dead_zone`, which is not yet claimed in this checkpoint even though the MATLAB-symbolic runtime path is native and MATLAB-reference validated
- input families not yet lowered natively in MATLAB beyond the current constant/step/pulse/ramp/sine/square/sawtooth/triangle/saturation/dead-zone/fallback set
- input families not yet evaluated natively in the MATLAB numerical oracle beyond that same set
- broader lowering/validation coverage beyond the current anchor matrix

This means `matlabv2native` is already MATLAB-first from the user API perspective, and it now has a real standalone native runtime path for the current explicit-ODE anchor cases plus the current widened waveform family set. It is still not a full native compiler with broad runtime coverage.

## Internal Module Boundaries

The scaffold is split into:

- MATLAB-facing package functions under `matlab/+matlabv2native/`
- native intake and preview helpers under `matlab/+matlabv2native/+internal/`
- existing bridge and shared Python backend under `matlab/+simucopilot/+internal/` and the Python repo modules

Important internal helpers:

- [prepareInvocation.m](../matlab/+matlabv2native/+internal/prepareInvocation.m)
- [inferSourceType.m](../matlab/+matlabv2native/+internal/inferSourceType.m)
- [captureCallerWorkspace.m](../matlab/+matlabv2native/+internal/captureCallerWorkspace.m)
- [equationTexts.m](../matlab/+matlabv2native/+internal/equationTexts.m)
- [nativeAnalyze.m](../matlab/+matlabv2native/+internal/nativeAnalyze.m)
- [applyNativePreview.m](../matlab/+matlabv2native/+internal/applyNativePreview.m)
- [isNativeExplicitOdeEligible.m](../matlab/+matlabv2native/+internal/isNativeExplicitOdeEligible.m)
- [generateNativeExplicitOde.m](../matlab/+matlabv2native/+internal/generateNativeExplicitOde.m)
- [comparePreviewToProblem.m](../matlab/+matlabv2native/+internal/comparePreviewToProblem.m)
- [recognizeExpressionInputSpec.m](../matlab/+simucopilot/+internal/recognizeExpressionInputSpec.m)

## Parity Strategy

During the native migration, the Python backend remains an important oracle, but current native anchor cases now also use a MATLAB numerical reference solve.

Current parity checks compare these preview-level fields for native and delegated cases:

- states
- algebraics
- inputs
- parameters
- time variable
- route for native explicit-ODE previews
- first-order state order for native explicit-ODE previews

For native-generated explicit-ODE models in explicit Python parity mode, the current generate path also compares:

- source block families
- native vs MATLAB-reference simulation traces
- Python vs MATLAB-reference simulation traces
- native vs Python simulation traces
- validation status

Fields not yet compared automatically across the full API surface:

- generated block structure beyond semantic source-family checks
- first-order RHS semantics
- the wider explicit-ODE input matrix listed in the campaign prompt
- non-explicit systems
- build/simulate parity through `compareWithPython(...)`, which is still preview-oriented

Those will be added as the native backend matures beyond the current runtime/parity split checkpoint.

## Immediate Next Steps

1. finish Python-parity support for runtime-native repeating-sequence families such as `sawtooth` and `triangle`
2. widen native explicit-ODE input lowering into nonlinear families such as `saturation`, `dead_zone`, `sign`, `abs`, and `min/max`
3. widen the MATLAB numerical oracle input evaluation to match that larger native input matrix
4. keep improving direct symbolic-expression recognition so fewer families rely on struct-style input specs
5. keep Python parity as an explicit comparison/debug flow rather than a default dependency
6. extend `compareWithPython(...)` or add a new comparison API for build/simulate/reference parity
7. compare native vs Python first-order RHS semantics
8. reduce MATLAB Function usage where native block compositions exist while keeping the Python backend and `matlabv1` green
