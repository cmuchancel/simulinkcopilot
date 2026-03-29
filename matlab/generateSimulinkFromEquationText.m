function out = generateSimulinkFromEquationText(equations, varargin)
% generateSimulinkFromEquationText Generate a Simulink model from MATLAB-style equation text.

opts = simucopilot.internal.validateOptions(struct("Build", true), varargin{:});
callerNames = evalin("caller", "who");
callerWorkspace = struct();
for index = 1:numel(callerNames)
    name = callerNames{index};
    if isvarname(name)
        callerWorkspace.(name) = evalin("caller", name);
    end
end
opts = simucopilot.internal.enrichProblemMetadata("matlab_equation_text", equations, opts, callerWorkspace);
request = simucopilot.internal.makeRequestStruct("matlab_equation_text", equations, opts);
out = simucopilot.internal.callBackend(request, opts);
end
