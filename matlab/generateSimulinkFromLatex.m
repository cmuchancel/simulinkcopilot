function out = generateSimulinkFromLatex(equations, varargin)
% generateSimulinkFromLatex Generate a Simulink model from LaTeX equations.

opts = simucopilot.internal.validateOptions(struct("Build", true), varargin{:});
request = simucopilot.internal.makeRequestStruct("latex", equations, opts);
out = simucopilot.internal.callBackend(request, opts);
end
