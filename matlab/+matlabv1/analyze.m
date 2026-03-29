function out = analyze(primaryInput, varargin)
% matlabv1.analyze Analyze support and inferred metadata without opening a model.
%
% Usage:
%   report = matlabv1.analyze(eqn, "State", "x")

[sourceType, opts] = matlabv1.internal.prepareInvocation( ...
    struct("Build", false, "OpenModel", false), ...
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
opts = simucopilot.internal.enrichProblemMetadata(sourceType, primaryInput, opts, callerWorkspace);
request = simucopilot.internal.makeRequestStruct(sourceType, primaryInput, opts);
out = simucopilot.internal.callBackend(request, opts);
out.Api = "matlabv1";
out.SourceType = sourceType;
out.PublicOptions = localPublicOptions(opts);
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
