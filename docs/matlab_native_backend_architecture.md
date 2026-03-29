# Native MATLAB Backend Architecture

This document describes the additive native MATLAB backend effort that sits beside the existing Python backend.

## Current Status

`matlabv2native` currently exists as a **phase-2 explicit-ODE scaffold**:

- it provides a native MATLAB public API
- it performs MATLAB-side source-type, symbol-metadata, and explicit-ODE preview
- it delegates route analysis, build, simulation, and validation to the existing Python backend
- it returns a parity report comparing MATLAB-side preview data against the Python backend

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
- parity comparison against the Python backend for:
  - states
  - algebraics
  - inputs
  - parameters
  - time variable
  - route
  - first-order state order

### Still Delegated to Python

These behaviors still use the existing Python backend:

- authoritative route classification
- full normalization
- Simulink lowering
- model build
- simulation
- validation

This means `matlabv2native` is already MATLAB-first from the user API perspective, but it is not yet a fully native compiler path.

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
- [comparePreviewToProblem.m](../matlab/+matlabv2native/+internal/comparePreviewToProblem.m)

## Parity Strategy

During the native migration, the Python backend remains the reference oracle.

Current parity checks compare:

- states
- algebraics
- inputs
- parameters
- time variable
- route for native explicit-ODE previews
- first-order state order for native explicit-ODE previews

Fields not yet compared natively:

- source block families
- generated block structure
- simulation traces
- validation metrics
- first-order RHS semantics

Those will be added as the native backend matures beyond the scaffold.

## Immediate Next Steps

1. add native Simulink lowering for explicit ODEs
2. expand parity checks to input block families and simulation traces
3. compare native vs Python first-order RHS semantics
4. widen native coverage beyond symbolic explicit ODEs
5. keep the Python backend and `matlabv1` green throughout
