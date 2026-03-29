function out = generate(primaryInput, varargin)
% matlabv2native.generate Generate a Simulink model through the native MATLAB scaffold.
%
% Phase 1 behavior:
%   - performs native MATLAB preview and parity checking
%   - delegates actual model build, simulation, and validation to the existing backend

[sourceType, opts, invocation] = matlabv2native.internal.prepareInvocation( ...
    struct("Build", true, "OpenModel", false), ...
    primaryInput, ...
    varargin{:});

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
nativePreview = matlabv2native.internal.nativeAnalyze(sourceType, primaryInput, opts, callerWorkspace);
delegateOpts = matlabv2native.internal.applyNativePreview(opts, nativePreview);
delegateOpts = simucopilot.internal.enrichProblemMetadata(sourceType, primaryInput, delegateOpts, callerWorkspace);
request = simucopilot.internal.makeRequestStruct(sourceType, primaryInput, delegateOpts);
backendOut = simucopilot.internal.callBackend(request, delegateOpts);
parityReport = matlabv2native.internal.comparePreviewToProblem(nativePreview, backendOut.NormalizedProblem);

out = backendOut;
out.Api = "matlabv2native";
out.BackendKind = "python_delegate";
out.SourceType = sourceType;
out.Invocation = invocation;
out.NativePreview = nativePreview;
out.ParityReport = parityReport;
out.PublicOptions = localPublicOptions(delegateOpts);
end

function publicOptions = localPublicOptions(opts)
publicOptions = struct( ...
    "States", {opts.States}, ...
    "Algebraics", {opts.Algebraics}, ...
    "Inputs", {opts.Inputs}, ...
    "Parameters", {opts.Parameters}, ...
    "TimeVariable", opts.TimeVariable, ...
    "ModelName", opts.ModelName, ...
    "OpenModel", opts.OpenModel ...
);
end
