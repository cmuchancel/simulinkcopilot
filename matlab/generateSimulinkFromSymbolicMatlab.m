function out = generateSimulinkFromSymbolicMatlab(symbolicInput, varargin)
% generateSimulinkFromSymbolicMatlab Generate a Simulink model from symbolic-style MATLAB equations.

opts = simucopilot.internal.validateOptions(struct("Build", true, "TimeVariable", ""), varargin{:});
callerNames = evalin("caller", "who");
callerWorkspace = struct();
for index = 1:numel(callerNames)
    name = callerNames{index};
    if isvarname(name)
        callerWorkspace.(name) = evalin("caller", name);
    end
end
opts = simucopilot.internal.enrichProblemMetadata("matlab_symbolic", symbolicInput, opts, callerWorkspace);
request = simucopilot.internal.makeRequestStruct("matlab_symbolic", symbolicInput, opts);
out = simucopilot.internal.callBackend(request, opts);
end
