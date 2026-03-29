function out = generateSimulinkFromLatex(equations, varargin)
% generateSimulinkFromLatex Generate a Simulink model from LaTeX equations.

opts = simucopilot.internal.validateOptions(struct("Build", true), varargin{:});
callerNames = evalin("caller", "who");
callerWorkspace = struct();
for index = 1:numel(callerNames)
    name = callerNames{index};
    if isvarname(name)
        callerWorkspace.(name) = evalin("caller", name);
    end
end
opts = simucopilot.internal.enrichProblemMetadata("latex", equations, opts, callerWorkspace);
request = simucopilot.internal.makeRequestStruct("latex", equations, opts);
out = simucopilot.internal.callBackend(request, opts);
end
