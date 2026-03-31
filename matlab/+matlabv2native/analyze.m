function out = analyze(primaryInput, varargin)
% matlabv2native.analyze Analyze equations through the native MATLAB scaffold and compare with Python.
%
% Phase 2 behavior:
%   - performs native MATLAB intake, symbol preview, and explicit-ODE preview
%   - delegates route analysis to the existing Python backend
%   - returns a parity report between native preview data and the Python oracle

currentStage = "prepare_invocation";
readout = struct();
try
    [sourceType, opts, invocation, readout] = matlabv2native.internal.prepareInvocation( ...
        struct("Build", false, "OpenModel", false), ...
        primaryInput, ...
        varargin{:});

    currentStage = "caller_capture";
    callerNames = evalin("caller", "who");
    callerWorkspace = struct();
    for index = 1:numel(callerNames)
        name = callerNames{index};
        if ~isvarname(name)
            continue;
        end
        try
            callerWorkspace.(name) = evalin("caller", name);
        catch
            % Ignore values that cannot be materialized deterministically.
        end
    end
    readout.Stages.caller_capture = "passed";

    currentStage = "route_classification";
    nativePreview = matlabv2native.internal.nativeAnalyze(sourceType, primaryInput, opts, callerWorkspace);
    readout = matlabv2native.internal.frontDoorSupport("attach_preview", readout, primaryInput, nativePreview);
    readout = matlabv2native.internal.frontDoorSupport("validate_state_binding", sourceType, primaryInput, opts, nativePreview, readout);
    [canNativeLower, nativeEligibilityReason] = matlabv2native.internal.isNativeExplicitOdeEligible(sourceType, nativePreview);

    currentStage = "python_delegate";
    delegateOpts = matlabv2native.internal.applyNativePreview(opts, nativePreview);
    delegateOpts = simucopilot.internal.enrichProblemMetadata(sourceType, primaryInput, delegateOpts, callerWorkspace);
    request = simucopilot.internal.makeRequestStruct(sourceType, primaryInput, delegateOpts);
    backendOut = simucopilot.internal.callBackend(request, delegateOpts);
    parityReport = matlabv2native.internal.comparePreviewToProblem(nativePreview, backendOut);

    out = backendOut;
    out.Api = "matlabv2native";
    out.BackendKind = "python_delegate";
    out.SourceType = sourceType;
    out.Invocation = invocation;
    out.NativePreview = nativePreview;
    out.ParityReport = parityReport;
    out.PublicOptions = localPublicOptions(delegateOpts);
    readout = matlabv2native.internal.frontDoorSupport("attach_outcome", readout, out, canNativeLower, nativeEligibilityReason);
    out.FrontDoorReadout = readout;
    out.FrontDoorDiagnosis = matlabv2native.internal.frontDoorSupport("diagnose", readout);
catch exc
    if matlabv2native.internal.frontDoorSupport("is_diagnostic_identifier", exc.identifier)
        rethrow(exc);
    end
    readout = localMarkFailedStage(readout, currentStage, exc);
    matlabv2native.internal.frontDoorSupport("raise_unexpected", currentStage, exc, readout);
end
end

function publicOptions = localPublicOptions(opts)
publicOptions = struct( ...
    "States", {opts.States}, ...
    "Algebraics", {opts.Algebraics}, ...
    "Inputs", {opts.Inputs}, ...
    "Parameters", {opts.Parameters}, ...
    "TimeVariable", opts.TimeVariable, ...
    "ModelName", opts.ModelName ...
);
end

function readout = localMarkFailedStage(readout, stage, exc)
if isempty(readout)
    readout = struct();
end
readout.FailedStage = char(string(stage));
readout.UnderlyingErrorIdentifier = char(string(exc.identifier));
readout.UnderlyingErrorMessage = char(string(exc.message));
if isfield(readout, "Stages") && isstruct(readout.Stages)
    fieldName = char(string(stage));
    if isfield(readout.Stages, fieldName)
        readout.Stages.(fieldName) = "failed";
    end
end
end
