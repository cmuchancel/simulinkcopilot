function opts = resolveCallerRuntimeValues(opts, callerWorkspace)
% resolveCallerRuntimeValues Pull runtime values from the wrapper caller workspace.

if nargin < 1 || isempty(opts)
    error("simucopilot:MissingOptions", ...
        "resolveCallerRuntimeValues requires a normalized options struct.");
end
if nargin < 2 || isempty(callerWorkspace)
    callerWorkspace = struct();
end

if ~isfield(opts, "RuntimeOverride") || isempty(opts.RuntimeOverride)
    opts.RuntimeOverride = struct();
end
if ~isfield(opts.RuntimeOverride, "parameter_values") || isempty(opts.RuntimeOverride.parameter_values)
    opts.RuntimeOverride.parameter_values = struct();
end
if ~isfield(opts.RuntimeOverride, "input_values") || isempty(opts.RuntimeOverride.input_values)
    opts.RuntimeOverride.input_values = struct();
end
if ~isfield(opts.RuntimeOverride, "input_specs") || isempty(opts.RuntimeOverride.input_specs)
    opts.RuntimeOverride.input_specs = struct();
end

opts.RuntimeOverride.parameter_values = localNormalizeNumericStruct( ...
    opts.RuntimeOverride.parameter_values, ...
    "RuntimeOverride.parameter_values");
opts.RuntimeOverride.input_values = localNormalizeNumericStruct( ...
    opts.RuntimeOverride.input_values, ...
    "RuntimeOverride.input_values");
opts.RuntimeOverride.input_specs = localNormalizeInputSpecStruct( ...
    opts.RuntimeOverride.input_specs, ...
    "RuntimeOverride.input_specs", ...
    opts.TimeVariable);

for index = 1:numel(opts.Parameters)
    name = char(string(opts.Parameters{index}));
    if isfield(opts.RuntimeOverride.parameter_values, name)
        continue;
    end
    [exists, value] = localTryGetCallerValue(name, callerWorkspace);
    if ~exists
        continue;
    end
    if ~isnumeric(value) || ~isscalar(value)
        error("simucopilot:InvalidCallerParameterValue", ...
            "Declared parameter '%s' must resolve to a numeric scalar in the caller workspace.", ...
            name);
    end
    opts.RuntimeOverride.parameter_values.(name) = double(value);
end

if ~isempty(opts.Parameters) && (opts.Build || opts.RunSim)
    parameterFields = string(fieldnames(opts.RuntimeOverride.parameter_values));
    missingParameters = setdiff(string(opts.Parameters), parameterFields);
    if ~isempty(missingParameters)
        error("simucopilot:MissingParameterValues", ...
            "Declared Parameters require numeric values via ParameterValues or caller variables. Missing: %s", ...
            strjoin(cellstr(missingParameters), ", "));
    end
end

for index = 1:numel(opts.Inputs)
    name = char(string(opts.Inputs{index}));
    if isfield(opts.RuntimeOverride.input_values, name) || isfield(opts.RuntimeOverride.input_specs, name)
        continue;
    end
    [exists, value] = localTryGetCallerValue(name, callerWorkspace);
    if ~exists
        continue;
    end
    if isnumeric(value) && isscalar(value)
        opts.RuntimeOverride.input_values.(name) = double(value);
        continue;
    end
    opts.RuntimeOverride.input_specs.(name) = localNormalizeSingleInputSpec(value, name, opts.TimeVariable);
end
end

function normalized = localNormalizeNumericStruct(raw, optionName)
if isempty(raw)
    normalized = struct();
    return;
end
if ~isstruct(raw)
    error("simucopilot:InvalidNumericStruct", ...
        "%s must be a struct mapping names to numeric scalar values.", optionName);
end
normalized = struct();
fields = fieldnames(raw);
for index = 1:numel(fields)
    field = fields{index};
    value = raw.(field);
    if ~isnumeric(value) || ~isscalar(value)
        error("simucopilot:InvalidNumericStruct", ...
            "%s.%s must be a numeric scalar.", optionName, field);
    end
    normalized.(field) = double(value);
end
end

function normalized = localNormalizeInputSpecStruct(raw, optionName, timeVariable)
if isempty(raw)
    normalized = struct();
    return;
end
if ~isstruct(raw)
    error("simucopilot:InvalidInputSpecStruct", ...
        "%s must be a struct mapping input names to input spec structs or keywords.", optionName);
end
normalized = struct();
fields = fieldnames(raw);
for index = 1:numel(fields)
    field = fields{index};
    normalized.(field) = localNormalizeSingleInputSpec(raw.(field), field, timeVariable);
end
end

function normalized = localNormalizeSingleInputSpec(raw, inputName, timeVariable)
if ischar(raw) || (isstring(raw) && isscalar(raw))
    normalized = struct("kind", localNormalizeInputKind(raw, inputName));
    return;
end
if isa(raw, "symfun")
    normalized = localExpressionInputSpec(char(formula(raw)), timeVariable);
    return;
end
if isa(raw, "sym")
    if isempty(symvar(raw))
        numericValue = double(raw);
        normalized = struct("kind", "constant", "value", numericValue);
    else
        normalized = localExpressionInputSpec(char(raw), timeVariable);
    end
    return;
end
if ~isstruct(raw) || ~isscalar(raw)
    error("simucopilot:InvalidInputSpec", ...
        "Input '%s' must resolve to a numeric scalar, a waveform keyword, or a scalar struct spec.", ...
        inputName);
end

normalized = struct();
fields = fieldnames(raw);
for index = 1:numel(fields)
    field = fields{index};
    value = raw.(field);
    if ischar(value) || (isstring(value) && isscalar(value))
        normalized.(field) = char(string(value));
    elseif islogical(value) && isscalar(value)
        normalized.(field) = logical(value);
    elseif isnumeric(value) && isscalar(value)
        normalized.(field) = double(value);
    else
        error("simucopilot:InvalidInputSpec", ...
            "Input spec field '%s.%s' must be a scalar string, numeric scalar, or logical scalar.", ...
            inputName, field);
    end
end

if isfield(normalized, "type") && ~isfield(normalized, "kind")
    normalized.kind = normalized.type;
    normalized = rmfield(normalized, "type");
end
if ~isfield(normalized, "kind")
    error("simucopilot:MissingInputSpecKind", ...
        "Input spec for '%s' must include a 'kind' field.", inputName);
end
normalized.kind = localNormalizeInputKind(normalized.kind, inputName);
if strcmp(normalized.kind, "expression")
    if ~isfield(normalized, "expression")
        error("simucopilot:MissingInputSpecExpression", ...
            "Input spec for '%s' with kind 'expression' must include an 'expression' field.", ...
            inputName);
    end
    normalized = localExpressionInputSpec(normalized.expression, timeVariable);
end
end

function kind = localNormalizeInputKind(rawKind, inputName)
kind = lower(strtrim(char(string(rawKind))));
supportedKinds = [ ...
    "constant", "time", "step", "impulse", "pulse", "sine", "square", "sawtooth", "triangle", "ramp", ...
    "sum", "product", "power", "exp", "delay", "saturation", "dead_zone", "abs", "sign", "minmax", "relay", ...
    "piecewise", "random_number", "white_noise", "expression" ...
];
if ~any(strcmp(kind, supportedKinds))
    error("simucopilot:UnsupportedInputSpecKind", ...
        "Unsupported input spec kind '%s' for input '%s'. Supported kinds: %s.", ...
        kind, inputName, strjoin(cellstr(supportedKinds), ", "));
end
end

function [exists, value] = localTryGetCallerValue(name, callerWorkspace)
exists = isfield(callerWorkspace, name);
if exists
    value = callerWorkspace.(name);
else
    value = [];
end
end

function spec = localExpressionInputSpec(expressionText, timeVariable)
expressionText = char(string(expressionText));
recognized = simucopilot.internal.recognizeExpressionInputSpec(expressionText, timeVariable);
if ~isempty(recognized)
    spec = recognized;
    return;
end
spec = struct("kind", "expression", "expression", expressionText);
if ~isempty(strtrim(char(string(timeVariable))))
    spec.time_variable = char(string(timeVariable));
end
end
