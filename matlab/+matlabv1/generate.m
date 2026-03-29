function out = generate(primaryInput, varargin)
% matlabv1.generate Build, simulate, and validate a Simulink model from MATLAB-side equations.
%
% Usage:
%   out = matlabv1.generate(eqn, "State", "x")
%   out = matlabv1.generate(eqn, "States", ["x" "v"], "OpenModel", true)
%   out = matlabv1.generate("\dot{x} = -x + u", "SourceType", "latex", "State", "x")

[sourceType, opts] = matlabv1.internal.prepareInvocation( ...
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
    "ModelName", opts.ModelName, ...
    "OpenModel", opts.OpenModel ...
);
end
