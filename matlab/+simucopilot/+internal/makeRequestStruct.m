function request = makeRequestStruct(sourceType, primaryInput, opts)
% makeRequestStruct Build a deterministic backend request for the MATLAB bridge.

sourceType = char(string(sourceType));

request = struct();
request.source_type = sourceType;
if ~isempty(strtrim(opts.ModelName))
    request.name = opts.ModelName;
    request.model_name = opts.ModelName;
end
if ~isempty(opts.States)
    request.states = opts.States;
end
if ~isempty(opts.Algebraics)
    request.algebraics = opts.Algebraics;
end
if ~isempty(opts.Inputs)
    request.inputs = opts.Inputs;
end
if ~isempty(opts.Parameters)
    request.parameters = opts.Parameters;
end
if ~isempty(strtrim(opts.TimeVariable)) && ~strcmp(sourceType, "latex")
    request.time_variable = opts.TimeVariable;
end
if ~isempty(fieldnames(opts.Assumptions))
    request.assumptions = opts.Assumptions;
end

switch sourceType
    case {"latex", "matlab_symbolic", "matlab_equation_text"}
        request.equations = localSerializeEquations(primaryInput);
    case "matlab_ode_function"
        if isa(primaryInput, "function_handle")
            error("simucopilot:OpaqueOdeFunction", ...
                "generateSimulinkFromODEFunction currently supports only structured exported RHS specifications, not opaque MATLAB function handles.");
        end
        if ~isstruct(primaryInput)
            error("simucopilot:InvalidOdeFunctionSpec", ...
                "matlab_ode_function currently requires a structured exported specification.");
        end
        request.function_spec = primaryInput;
    otherwise
        error("simucopilot:UnsupportedSourceType", ...
            "Unsupported SourceType '%s'.", sourceType);
end

if strcmp(sourceType, "matlab_equation_text") && ~isempty(fieldnames(opts.DerivativeMap))
    request.derivative_map = opts.DerivativeMap;
end

request.options = localBridgeOptions(opts);
end

function equations = localSerializeEquations(raw)
if isa(raw, "sym")
    equations = arrayfun(@char, raw(:), "UniformOutput", false);
    return;
end
if ischar(raw)
    equations = {char(raw)};
    return;
end
if isstring(raw)
    equations = cellstr(raw(:).');
    return;
end
if iscell(raw)
    equations = cellfun(@localCharString, raw, "UniformOutput", false);
    return;
end
error("simucopilot:InvalidEquationInput", ...
    "Equations must be a char vector, string array, cell array of strings, or symbolic equation array.");
end

function value = localCharString(item)
if isa(item, "sym")
    value = char(item);
    return;
end
value = char(string(item));
end

function options = localBridgeOptions(opts)
options = struct( ...
    "build", opts.Build, ...
    "run_sim", opts.RunSim, ...
    "validate_graph", true ...
);
if ~isempty(opts.ClassificationMode)
    options.classification_mode = opts.ClassificationMode;
end
if ~isempty(fieldnames(opts.SymbolConfig))
    options.symbol_config = opts.SymbolConfig;
end
if ~isempty(fieldnames(opts.RuntimeOverride))
    options.runtime_override = opts.RuntimeOverride;
end
if ~isempty(opts.SimulinkOutputDir)
    options.simulink_output_dir = opts.SimulinkOutputDir;
end
if ~isempty(opts.Tolerance)
    options.tolerance = opts.Tolerance;
end
end
