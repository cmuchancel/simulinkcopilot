# Native MATLAB Backend Architecture

This document describes the additive native MATLAB backend effort that sits beside the existing Python backend.

## Current Status

`matlabv2native` currently exists as a **phase-3 explicit-ODE backend checkpoint**:

- it provides a native MATLAB public API
- it performs MATLAB-side source-type, symbol-metadata, and explicit-ODE preview
- it can build eligible MATLAB symbolic explicit ODEs natively in Simulink
- it simulates those native models in MATLAB
- it compares them against a Python-backed oracle build and validation result
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
- native input-source lowering for the currently supported native families:
  - constant
  - step / delayed step
  - unsupported symbolic input expression lowered to a MATLAB Function source block
- parity comparison against the Python backend for:
  - states
  - algebraics
  - inputs
  - parameters
  - time variable
  - route
  - first-order state order
  - source block family
  - simulation traces
  - validation status

### Still Delegated to Python

These behaviors still use the existing Python backend, either as the primary execution path or as the oracle:

- authoritative handling for non-symbolic front doors
- non-explicit or ambiguous systems
- broader normalization beyond the current explicit-ODE native preview boundary
- the Python oracle model used for native-vs-oracle parity and validation
- input families not yet lowered natively in MATLAB
- broader lowering/validation coverage beyond the current anchor matrix

This means `matlabv2native` is already MATLAB-first from the user API perspective, and it now has a real native explicit-ODE lowering path, but it is not yet a full native compiler with broad parity coverage.

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

## Parity Strategy

During the native migration, the Python backend remains the reference oracle.

Current parity checks compare these preview-level fields for native and delegated cases:

- states
- algebraics
- inputs
- parameters
- time variable
- route for native explicit-ODE previews
- first-order state order for native explicit-ODE previews

For native-generated explicit-ODE models, the current generate path also compares:

- source block families
- simulation traces
- validation status

Fields not yet compared automatically across the full API surface:

- generated block structure beyond semantic source-family checks
- first-order RHS semantics
- the wider explicit-ODE input matrix listed in the campaign prompt
- non-explicit systems

Those will be added as the native backend matures beyond the current anchor-level native lowering checkpoint.

## Immediate Next Steps

1. widen native explicit-ODE input lowering beyond constant/step/fallback anchor coverage
2. extend `compareWithPython(...)` so it can report block-family and simulation parity for native-eligible cases
3. compare native vs Python first-order RHS semantics
4. reduce MATLAB Function usage where native block compositions exist
5. widen native coverage beyond symbolic explicit ODEs while keeping the Python backend and `matlabv1` green
