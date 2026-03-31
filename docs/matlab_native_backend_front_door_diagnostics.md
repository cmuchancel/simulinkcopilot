# MATLAB-Symbolic Front Door Diagnostics

This document describes the current strict front-door contract for `matlabv2native` when the source type is `matlab_symbolic`.

## Contract

For `matlab_symbolic`, callers must provide `State` or `States`.

This is now intentional:

- the public front door does not silently infer state order anymore
- state order is user-owned
- invalid state declarations fail before native lowering

## Successful Result Surface

Current successful public-entrypoint results expose:

- `FrontDoorReadout`
- `FrontDoorDiagnosis`

`FrontDoorReadout` is the structured trace surface.

Current high-signal fields include:

- `FrontDoor`
- `SourceType`
- `RepresentationKind`
- `ScalarizedEquationCount`
- `DeclaredStates`
- `BoundStates`
- `Algebraics`
- `Inputs`
- `Parameters`
- `TimeVariable`
- `Route`
- `RouteStatus`
- `NativeEligible`
- `NativeEligibilityReason`
- `FallbackUsed`
- `Delegated`
- `SupportStatus`
- `DelegationReason`
- `NativeSourceBlockFamilies`
- `FailedStage`
- `UnderlyingErrorIdentifier`
- `UnderlyingErrorMessage`
- `Stages`

`Stages` currently tracks:

- `source_type_validation`
- `option_validation`
- `caller_capture`
- `symbolic_normalization`
- `state_binding`
- `route_classification`
- `native_eligibility`
- `lowering`
- `simulation`
- `matlab_reference`
- `parity`

`FrontDoorDiagnosis` is currently deterministic and rule-based.

This checkpoint does not ship an AI-assisted diagnosis layer yet.

## Wrapped Failure Surface

Current wrapped front-door failures expose, at minimum:

- stable error `Code`
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

## Current Diagnostic Classes

Current explicit front-door diagnostic codes include:

- `matlabv2native:FrontDoorMissingStateDeclaration`
- `matlabv2native:FrontDoorConflictingStateOptions`
- `matlabv2native:FrontDoorInvalidParityMode`
- `matlabv2native:FrontDoorInvalidOptions`
- `matlabv2native:FrontDoorDuplicateStateNames`
- `matlabv2native:FrontDoorStateAlgebraicOverlap`
- `matlabv2native:FrontDoorStateInputOverlap`
- `matlabv2native:FrontDoorStateParameterOverlap`
- `matlabv2native:FrontDoorStateBindingMismatch`
- `matlabv2native:FrontDoorSourceTypeValidationFailed`
- `matlabv2native:FrontDoorInternalError`

These codes are intended to remain stable enough for tests and downstream inspection.

## Current Boundary

This checkpoint hardens the entry contract and the error surface first.

It does not yet mean every MATLAB-symbolic construct is supported natively.

The current behavior is:

- supported native cases return structured readouts and deterministic diagnosis summaries
- delegated cases still return explicit route/readout information on successful delegated flows
- unsupported or invalid front-door calls fail early with wrapped diagnostics instead of opaque MATLAB exceptions
- internal bugs are wrapped as `FrontDoorInternalError` and preserve lower-level identifier/message details

## Future Work

The main remaining front-door hardening work is:

- widen the same structured diagnostic surface to more unsupported/delegated families
- add more fix-specific guidance for broader unsupported symbolic patterns
- decide whether to add an additive AI-assisted diagnosis layer on top of the deterministic payload
