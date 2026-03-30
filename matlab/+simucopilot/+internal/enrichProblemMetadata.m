function opts = enrichProblemMetadata(sourceType, primaryInput, opts, callerWorkspace)
% enrichProblemMetadata Infer missing symbol metadata before resolving workspace runtime values.

if nargin < 4 || isempty(callerWorkspace)
    callerWorkspace = struct();
end

opts = localSeedSymbolConfigFromCaller(sourceType, primaryInput, opts, callerWorkspace);

if localNeedsInference(opts)
    probeOpts = opts;
    probeOpts.Build = false;
    probeOpts.RunSim = false;
    probeOpts.OpenModel = false;

    probeRequest = simucopilot.internal.makeRequestStruct(sourceType, primaryInput, probeOpts);
    probeOut = simucopilot.internal.callBackend(probeRequest, probeOpts);
    problem = probeOut.NormalizedProblem;

    if isempty(opts.States) && isfield(problem, "states")
        opts.States = localToCellstr(problem.states);
    end
    if isempty(opts.Algebraics) && isfield(problem, "algebraics")
        opts.Algebraics = localToCellstr(problem.algebraics);
    end
    if isempty(opts.Inputs) && isfield(problem, "inputs")
        opts.Inputs = localToCellstr(problem.inputs);
    end
    if isempty(opts.Parameters) && isfield(problem, "parameters")
        opts.Parameters = localToCellstr(problem.parameters);
    end
    if isempty(strtrim(opts.TimeVariable)) && isfield(problem, "time_variable") && ~isempty(problem.time_variable)
        opts.TimeVariable = char(string(problem.time_variable));
    end
end

opts = simucopilot.internal.resolveCallerRuntimeValues(opts, callerWorkspace);
end

function tf = localNeedsInference(opts)
tf = isempty(opts.States) ...
    || isempty(opts.Algebraics) ...
    || isempty(opts.Inputs) ...
    || isempty(opts.Parameters) ...
    || isempty(strtrim(opts.TimeVariable));
end

function values = localToCellstr(raw)
if isempty(raw)
    values = {};
    return;
end
if ischar(raw)
    values = {char(raw)};
    return;
end
if isstring(raw)
    values = cellstr(raw(:).');
    return;
end
if iscell(raw)
    values = cellfun(@char, raw, "UniformOutput", false);
    return;
end
error("simucopilot:InvalidBackendMetadata", ...
    "Backend metadata must be a string, string array, char vector, or cell array of strings.");
end

function opts = localSeedSymbolConfigFromCaller(sourceType, primaryInput, opts, callerWorkspace)
if ~strcmp(sourceType, "matlab_symbolic")
    return;
end

equations = localEquationTexts(primaryInput);
if isempty(equations)
    return;
end

if isempty(opts.SymbolConfig)
    opts.SymbolConfig = struct();
end

if isempty(strtrim(opts.TimeVariable))
    inferredTime = localInferTimeVariable(equations);
    if ~isempty(inferredTime)
        opts.TimeVariable = char(string(inferredTime));
    end
end
if ~isempty(strtrim(opts.TimeVariable)) && ~isfield(opts.SymbolConfig, opts.TimeVariable)
    opts.SymbolConfig.(opts.TimeVariable) = 'independent_variable';
end

reserved = localCompactCellstr([ ...
    opts.States(:); ...
    opts.Algebraics(:); ...
    opts.Inputs(:); ...
    opts.Parameters(:); ...
    {opts.TimeVariable}; ...
    localKnownFunctionNames()' ...
]);

identifiers = localExtractIdentifiers(equations);
for index = 1:numel(identifiers)
    name = identifiers{index};
    if isempty(name) || any(strcmp(name, reserved)) || isfield(opts.SymbolConfig, name)
        continue;
    end
    [exists, value] = localTryGetCallerValue(name, callerWorkspace);
    if ~exists
        continue;
    end
    inferredRole = localRoleFromWorkspaceValue(value, opts.TimeVariable);
    if ~isempty(inferredRole)
        opts.SymbolConfig.(name) = char(inferredRole);
        if strcmp(inferredRole, 'parameter') && ~any(strcmp(name, opts.Parameters))
            opts.Parameters{end + 1} = name; %#ok<AGROW>
        end
        if strcmp(inferredRole, 'input') && ~any(strcmp(name, opts.Inputs))
            opts.Inputs{end + 1} = name; %#ok<AGROW>
        end
    end
end
end

function equations = localEquationTexts(primaryInput)
if isa(primaryInput, "symfun")
    primaryInput = formula(primaryInput);
end
if isa(primaryInput, "sym")
    equations = cellstr(string(primaryInput(:)));
    return;
end
if ischar(primaryInput)
    equations = {char(primaryInput)};
    return;
end
if isstring(primaryInput)
    equations = cellstr(primaryInput(:).');
    return;
end
if iscell(primaryInput)
    equations = cellfun(@char, primaryInput, "UniformOutput", false);
    return;
end
equations = {};
end

function timeVariable = localInferTimeVariable(equations)
timeVariable = '';
tokens = {};
for index = 1:numel(equations)
    equationText = equations{index};
    diffMatches = regexp(equationText, "diff\\([^,]+,\\s*(?<time>[A-Za-z][A-Za-z0-9_]*)", "names");
    for matchIndex = 1:numel(diffMatches)
        tokens{end + 1} = diffMatches(matchIndex).time; %#ok<AGROW>
    end
end
tokens = unique(tokens);
if numel(tokens) == 1
    timeVariable = char(tokens{1});
end
end

function identifiers = localExtractIdentifiers(equations)
identifiers = {};
for index = 1:numel(equations)
    matches = regexp(equations{index}, "[A-Za-z][A-Za-z0-9_]*", "match");
    identifiers = [identifiers, matches]; %#ok<AGROW>
end
identifiers = unique(identifiers);
end

function names = localKnownFunctionNames
names = { ...
    "diff", "abs", "sin", "cos", "tan", "sec", "csc", "cot", ...
    "asin", "acos", "atan", "sinh", "cosh", "tanh", "sech", "csch", "coth", ...
    "asinh", "acosh", "atanh", "exp", "log", "sqrt", "atan2", "min", "max", ...
    "sat", "sign", "sawtooth", "rand", "randn", ...
    "heaviside", "Heaviside", "dirac", "Dirac", "piecewise", "Piecewise", ...
    "Abs", "Min", "Max" ...
};
end

function values = localCompactCellstr(raw)
values = {};
for index = 1:numel(raw)
    item = raw{index};
    if isempty(item)
        continue;
    end
    values{end + 1} = char(string(item)); %#ok<AGROW>
end
	values = unique(values, "stable");
end

function role = localRoleFromWorkspaceValue(value, timeVariable)
role = '';
if (isnumeric(value) || islogical(value)) && isscalar(value)
    role = 'parameter';
    return;
end
if ischar(value) || (isstring(value) && isscalar(value)) || (isstruct(value) && isscalar(value)) || isa(value, "symfun")
    role = 'input';
    return;
end
if isa(value, "sym")
    symbols = string(arrayfun(@char, symvar(value), "UniformOutput", false));
    if isempty(symbols)
        role = 'parameter';
        return;
    end
    if ~isempty(strtrim(timeVariable)) && any(symbols == string(timeVariable))
        role = 'input';
    end
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
