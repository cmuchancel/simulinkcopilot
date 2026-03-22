function out = generateSimulinkFromODEFunction(functionSpec, varargin)
% generateSimulinkFromODEFunction Generate a Simulink model from a structured ODE specification.

if isa(functionSpec, "function_handle")
    error("simucopilot:OpaqueOdeFunction", ...
        "generateSimulinkFromODEFunction currently supports only structured exported RHS specifications, not opaque MATLAB function handles.");
end

opts = simucopilot.internal.validateOptions(struct("Build", true), varargin{:});
request = simucopilot.internal.makeRequestStruct("matlab_ode_function", functionSpec, opts);
out = simucopilot.internal.callBackend(request, opts);
end
