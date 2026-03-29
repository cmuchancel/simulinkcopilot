function out = generate(primaryInput, varargin)
% matlabv2native.generate Generate a Simulink model through the native MATLAB scaffold.
%
% Phase 5 behavior:
%   - performs native MATLAB preview, explicit-ODE preview, and parity checking
%   - runs native-eligible explicit ODE anchor cases in MATLAB-only runtime mode by default
%   - supports optional Python parity mode for those native-eligible cases
%   - otherwise delegates build, simulation, and validation to the existing backend

totalTimer = tic;
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

previewTimer = tic;
nativePreview = matlabv2native.internal.nativeAnalyze(sourceType, primaryInput, opts, callerWorkspace);
[canNativeLower, ~] = matlabv2native.internal.isNativeExplicitOdeEligible(sourceType, nativePreview);
previewTimeSec = toc(previewTimer);
if canNativeLower
    nativeOpts = localApplyNativePreview(opts, nativePreview, callerWorkspace);
    out = matlabv2native.internal.generateNativeExplicitOde( ...
        primaryInput, ...
        sourceType, ...
        nativeOpts, ...
        invocation, ...
        callerWorkspace, ...
        nativePreview);
    out.Timing.preview_analysis_sec = previewTimeSec;
    out.Timing.total_wall_time_sec = toc(totalTimer);
    return;
end

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
out.Timing = struct( ...
    "preview_analysis_sec", previewTimeSec, ...
    "python_delegate_sec", toc(totalTimer) - previewTimeSec, ...
    "total_wall_time_sec", toc(totalTimer) ...
);
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

function opts = localApplyNativePreview(opts, preview, callerWorkspace)
if isempty(opts.States) && isfield(preview, "States")
    opts.States = localToCellstr(preview.States);
end
if isempty(opts.Algebraics) && isfield(preview, "Algebraics")
    opts.Algebraics = localToCellstr(preview.Algebraics);
end
if isempty(opts.Inputs) && isfield(preview, "Inputs")
    opts.Inputs = localToCellstr(preview.Inputs);
end
if isempty(opts.Parameters) && isfield(preview, "Parameters")
    opts.Parameters = localToCellstr(preview.Parameters);
end
if isempty(strtrim(opts.TimeVariable)) && isfield(preview, "TimeVariable") && ~isempty(preview.TimeVariable)
    opts.TimeVariable = char(string(preview.TimeVariable));
end
opts = simucopilot.internal.resolveCallerRuntimeValues(opts, callerWorkspace);
end

function values = localToCellstr(raw)
if isempty(raw)
    values = {};
    return;
end
if ischar(raw)
    values = {char(raw)};
    return;
end
if isstring(raw)
    values = cellstr(raw(:).');
    return;
end
if iscell(raw)
    values = cellfun(@char, raw, "UniformOutput", false);
    return;
end
values = {char(string(raw))};
end
