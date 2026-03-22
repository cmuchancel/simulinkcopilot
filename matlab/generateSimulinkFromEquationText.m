function out = generateSimulinkFromEquationText(equations, varargin)
% generateSimulinkFromEquationText Generate a Simulink model from MATLAB-style equation text.

opts = simucopilot.internal.validateOptions(struct("Build", true), varargin{:});
request = simucopilot.internal.makeRequestStruct("matlab_equation_text", equations, opts);
out = simucopilot.internal.callBackend(request, opts);
end
