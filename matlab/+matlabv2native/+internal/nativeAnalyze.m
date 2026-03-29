function preview = nativeAnalyze(sourceType, primaryInput, opts, callerWorkspace)
% nativeAnalyze Phase-1 MATLAB-native metadata inference before delegation.

equations = matlabv2native.internal.equationTexts(primaryInput);
preview = struct();
preview.SourceType = sourceType;
preview.EquationTexts = equations;
preview.States = opts.States;
preview.Algebraics = opts.Algebraics;
preview.Inputs = opts.Inputs;
preview.Parameters = opts.Parameters;
preview.TimeVariable = opts.TimeVariable;
preview.InferenceStatus = "phase1_native_preview";
preview.Notes = {};
preview.DelegatedFields = {};

if isempty(strtrim(preview.TimeVariable))
    preview.TimeVariable = localInferTimeVariable(equations);
    if isempty(strtrim(preview.TimeVariable))
        preview.DelegatedFields{end + 1} = "time_variable"; %#ok<AGROW>
    else
        preview.Notes{end + 1} = "Time variable inferred natively."; %#ok<AGROW>
    end
end

if isempty(preview.States)
    inferredStates = localInferStates(equations, preview.TimeVariable);
    if isempty(inferredStates)
        preview.DelegatedFields{end + 1} = "states"; %#ok<AGROW>
    else
        preview.States = inferredStates;
        preview.Notes{end + 1} = "States inferred natively from derivative patterns."; %#ok<AGROW>
    end
end

if isempty(preview.Inputs) || isempty(preview.Parameters)
    [inferredInputs, inferredParameters] = localInferRoles( ...
        equations, ...
        callerWorkspace, ...
        preview.TimeVariable, ...
        preview.States, ...
        preview.Algebraics, ...
        preview.Inputs, ...
        preview.Parameters);
    if isempty(preview.Inputs)
        preview.Inputs = inferredInputs;
        if isempty(inferredInputs)
            preview.DelegatedFields{end + 1} = "inputs"; %#ok<AGROW>
        end
    end
    if isempty(preview.Parameters)
        preview.Parameters = inferredParameters;
        if isempty(inferredParameters)
            preview.DelegatedFields{end + 1} = "parameters"; %#ok<AGROW>
        end
    end
end

preview.States = localUniqueCell(preview.States);
preview.Algebraics = localUniqueCell(preview.Algebraics);
preview.Inputs = localUniqueCell(preview.Inputs);
preview.Parameters = localUniqueCell(preview.Parameters);
preview.DelegatedFields = localUniqueCell(preview.DelegatedFields);
preview.Notes = localUniqueCell(preview.Notes);
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
    functionMatches = regexp(equationText, "(?<name>[A-Za-z][A-Za-z0-9_]*)\\((?<arg>[A-Za-z][A-Za-z0-9_]*)\\)", "names");
    for matchIndex = 1:numel(functionMatches)
        if any(strcmp(functionMatches(matchIndex).name, localKnownFunctionNames()))
            continue;
        end
        tokens{end + 1} = functionMatches(matchIndex).arg; %#ok<AGROW>
    end
end
tokens = unique(tokens);
if numel(tokens) == 1
    timeVariable = char(tokens{1});
end
end

function states = localInferStates(equations, timeVariable)
states = {};
for index = 1:numel(equations)
    equationText = equations{index};
    diffMatches = regexp(equationText, "diff\\((?<state>[A-Za-z][A-Za-z0-9_]*)\\s*,\\s*(?<time>[A-Za-z][A-Za-z0-9_]*)", "names");
    for matchIndex = 1:numel(diffMatches)
        if isempty(timeVariable) || strcmp(diffMatches(matchIndex).time, timeVariable)
            states{end + 1} = diffMatches(matchIndex).state; %#ok<AGROW>
        end
    end
end
states = localUniqueCell(states);
end

function [inputs, parameters] = localInferRoles(equations, callerWorkspace, timeVariable, states, algebraics, existingInputs, existingParameters)
inputs = existingInputs;
parameters = existingParameters;
reserved = localUniqueCell([states(:); algebraics(:); existingInputs(:); existingParameters(:); {timeVariable}; localKnownFunctionNames()']);
identifiers = localExtractIdentifiers(equations);
for index = 1:numel(identifiers)
    name = identifiers{index};
    if isempty(name) || any(strcmp(name, reserved))
        continue;
    end
    if isfield(callerWorkspace, name)
        role = localRoleFromWorkspaceValue(callerWorkspace.(name), timeVariable);
        if strcmp(role, 'parameter')
            parameters{end + 1} = name; %#ok<AGROW>
            continue;
        end
        if strcmp(role, 'input')
            inputs{end + 1} = name; %#ok<AGROW>
            continue;
        end
    end
    if localAppearsAsTimeFunction(name, equations, timeVariable)
        inputs{end + 1} = name; %#ok<AGROW>
    end
end
inputs = localUniqueCell(inputs);
parameters = localUniqueCell(parameters);
end

function tf = localAppearsAsTimeFunction(name, equations, timeVariable)
tf = false;
if isempty(strtrim(char(string(timeVariable))))
    return;
end
pattern = sprintf("%s\\(\\s*%s\\s*\\)", regexptranslate('escape', name), regexptranslate('escape', char(string(timeVariable))));
for index = 1:numel(equations)
    if ~isempty(regexp(equations{index}, pattern, "once"))
        tf = true;
        return;
    end
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
    if ~isempty(strtrim(char(string(timeVariable)))) && any(symbols == string(timeVariable))
        role = 'input';
    end
end
end

function names = localKnownFunctionNames
names = { ...
    "diff", "abs", "sin", "cos", "tan", "sec", "csc", "cot", ...
    "asin", "acos", "atan", "sinh", "cosh", "tanh", "sech", "csch", "coth", ...
    "asinh", "acosh", "atanh", "exp", "log", "sqrt", "atan2", "min", "max", ...
    "sat", "sign", "sawtooth", "rand", "randn", ...
    "heaviside", "Heaviside", "dirac", "Dirac", "piecewise", "Piecewise", ...
    "Abs", "Min", "Max", "True", "False" ...
};
end

function values = localUniqueCell(raw)
values = {};
for index = 1:numel(raw)
    item = raw{index};
    if isempty(item)
        continue;
    end
    values{end + 1} = char(string(item)); %#ok<AGROW>
end
values = unique(values);
end
