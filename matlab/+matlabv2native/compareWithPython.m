function report = compareWithPython(primaryInput, varargin)
% matlabv2native.compareWithPython Compare MATLAB-side native preview data against the Python oracle.

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

    report = struct( ...
        "Api", "matlabv2native", ...
        "BackendKind", "python_delegate", ...
        "SourceType", sourceType, ...
        "Invocation", invocation, ...
        "NativePreview", nativePreview, ...
        "PythonRoute", backendOut.Route, ...
        "PythonFirstOrder", backendOut.FirstOrder, ...
        "PythonNormalizedProblem", backendOut.NormalizedProblem, ...
        "ParityReport", parityReport ...
    );
    readout = matlabv2native.internal.frontDoorSupport("attach_outcome", readout, report, canNativeLower, nativeEligibilityReason);
    report.FrontDoorReadout = readout;
    report.FrontDoorDiagnosis = matlabv2native.internal.frontDoorSupport("diagnose", readout);
catch exc
    if matlabv2native.internal.frontDoorSupport("is_diagnostic_identifier", exc.identifier)
        rethrow(exc);
    end
    readout = localMarkFailedStage(readout, currentStage, exc);
    matlabv2native.internal.frontDoorSupport("raise_unexpected", currentStage, exc, readout);
end
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
