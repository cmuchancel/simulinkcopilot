function out = generateSimulinkFromSymbolicMatlab(symbolicInput, varargin)
% generateSimulinkFromSymbolicMatlab Generate a Simulink model from symbolic-style MATLAB equations.

opts = simucopilot.internal.validateOptions(struct("Build", true), varargin{:});
request = simucopilot.internal.makeRequestStruct("matlab_symbolic", symbolicInput, opts);
out = simucopilot.internal.callBackend(request, opts);
end
