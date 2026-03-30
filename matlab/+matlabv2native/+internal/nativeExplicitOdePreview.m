function [result, notes] = nativeExplicitOdePreview(primaryInput, sourceType, states, algebraics, inputs, parameters, timeVariable, callerWorkspace)
% nativeExplicitOdePreview Build a native explicit-ODE preview when MATLAB symbolic tools can support it.

notes = {};
result = struct( ...
    "Route", "", ...
    "Status", "delegated", ...
    "FirstOrderPreview", localEmptyFirstOrderPreview() ...
);

if ~strcmp(sourceType, "matlab_symbolic")
    notes{end + 1} = "Route classification still delegates to Python for non-symbolic source types."; %#ok<AGROW>
    return;
end

[symbolicEquations, available] = localSymbolicEquations(primaryInput);
if ~available
    notes{end + 1} = "Route classification still delegates to Python when symbolic equations are not available as MATLAB symbolic objects."; %#ok<AGROW>
    return;
end

if isempty(strtrim(char(string(timeVariable))))
    notes{end + 1} = "Route classification still delegates to Python when the time variable is not inferred natively."; %#ok<AGROW>
    return;
end

[explicitPreview, explicitNotes, explicitOk] = localBuildVectorFieldPreview( ...
    symbolicEquations, ...
    states, ...
    inputs, ...
    parameters, ...
    timeVariable, ...
    "explicit_ode", ...
    "odeToVectorField");
notes = [notes, explicitNotes];
if explicitOk
    result = explicitPreview;
    return;
end

if ~localHasAlgebraicShape(symbolicEquations)
    return;
end

[daePreview, daeNotes, daeOk] = localAttemptReducibleDaePreview( ...
    symbolicEquations, ...
    states, ...
    algebraics, ...
    inputs, ...
    parameters, ...
    timeVariable, ...
    callerWorkspace);
notes = [notes, daeNotes];
result = daePreview;
if daeOk
    return;
end
end

function [equations, available] = localSymbolicEquations(primaryInput)
available = true;
if isa(primaryInput, "symfun")
    equations = formula(primaryInput);
    return;
end
if isa(primaryInput, "sym")
    equations = primaryInput(:);
    return;
end
if iscell(primaryInput)
    equations = sym.empty(0, 1);
    for index = 1:numel(primaryInput)
        item = primaryInput{index};
        if isa(item, "symfun")
            equations(end + 1, 1) = formula(item); %#ok<AGROW>
            continue;
        end
        if isa(item, "sym")
            equations(end + 1, 1) = item; %#ok<AGROW>
            continue;
        end
        available = false;
        equations = sym.empty(0, 1);
        return;
    end
    return;
end
available = false;
equations = sym.empty(0, 1);
end

function [result, notes, ok] = localBuildVectorFieldPreview(symbolicEquations, states, inputs, parameters, timeVariable, routeName, methodName)
notes = {};
result = struct( ...
    "Route", "", ...
    "Status", "delegated", ...
    "FirstOrderPreview", localEmptyFirstOrderPreview() ...
);
ok = false;

try
    [vectorField, stateBasis] = odeToVectorField(symbolicEquations);
catch exc
    notes{end + 1} = "Native explicit-ODE preview delegated: " + string(exc.message); %#ok<AGROW>
    return;
end

canonicalBasis = cell(numel(stateBasis), 1);
for index = 1:numel(stateBasis)
    [canonicalName, basisOk] = localCanonicalStateName(stateBasis(index));
    if ~basisOk
        notes{end + 1} = "Native explicit-ODE preview delegated: unable to canonicalize state basis " + string(stateBasis(index)) + "."; %#ok<AGROW>
        return;
    end
    canonicalBasis{index} = canonicalName;
end

orderedStates = localCanonicalStateOrder(canonicalBasis, states);
equationStates = cell(1, numel(canonicalBasis));
equationRhs = cell(1, numel(canonicalBasis));
for index = 1:numel(canonicalBasis)
    equationStates{index} = canonicalBasis{index};
    equationRhs{index} = localCanonicalizeRhs(char(vectorField(index)), canonicalBasis, inputs, timeVariable);
end

stateEquations = struct("state", cell(1, numel(orderedStates)), "rhs", cell(1, numel(orderedStates)));
for index = 1:numel(orderedStates)
    stateName = orderedStates{index};
    rhsIndex = find(strcmp(equationStates, stateName), 1);
    if isempty(rhsIndex)
        notes{end + 1} = "Native explicit-ODE preview delegated: canonical state ordering did not align with MATLAB vector-field output."; %#ok<AGROW>
        return;
    end
    stateEquations(index).state = stateName;
    stateEquations(index).rhs = equationRhs{rhsIndex};
end

result.Route = routeName;
result.Status = "native_supported";
result.FirstOrderPreview = struct( ...
    "Available", true, ...
    "Method", methodName, ...
    "States", {orderedStates}, ...
    "Inputs", {reshape(localUniqueCell(inputs), 1, [])}, ...
    "Parameters", {reshape(localUniqueCell(parameters), 1, [])}, ...
    "IndependentVariable", char(string(timeVariable)), ...
    "OriginalStateBasis", {cellstr(string(stateBasis(:)).')}, ...
    "StateEquations", stateEquations ...
);
notes{end + 1} = string(routeName) + " route preview inferred natively with " + string(methodName) + "."; %#ok<AGROW>
ok = true;
end

function tf = localHasAlgebraicShape(symbolicEquations)
tf = false;
hasDifferential = false;
hasNonDifferential = false;
for index = 1:numel(symbolicEquations)
    equationText = char(symbolicEquations(index));
    if contains(equationText, "diff(")
        hasDifferential = true;
    else
        hasNonDifferential = true;
    end
end
tf = hasDifferential && hasNonDifferential;
end

function [result, notes, ok] = localAttemptReducibleDaePreview(symbolicEquations, states, algebraics, inputs, parameters, timeVariable, callerWorkspace)
notes = {};
result = struct( ...
    "Route", "dae_algebraic", ...
    "Status", "delegated", ...
    "FirstOrderPreview", localEmptyFirstOrderPreview() ...
);
ok = false;

[differentialEquations, algebraicEquations] = localPartitionDifferentialAndAlgebraicEquations(symbolicEquations);
if isempty(differentialEquations) || isempty(algebraicEquations)
    notes{end + 1} = "DAE/algebraic route delegated: mixed differential and algebraic equations were not detected cleanly."; %#ok<AGROW>
    return;
end

algebraicNames = localResolveAlgebraicNames(algebraics, algebraicEquations, states, inputs, parameters, timeVariable, callerWorkspace);
if numel(algebraicNames) ~= 1 || numel(algebraicEquations) ~= 1
    notes{end + 1} = "DAE/algebraic route delegated: native reduction currently supports one algebraic variable solved from one algebraic equation."; %#ok<AGROW>
    return;
end

target = localResolveCallerSymbol(callerWorkspace, algebraicNames{1});
if isempty(target)
    notes{end + 1} = "DAE/algebraic route delegated: unable to materialize algebraic variable '" + string(algebraicNames{1}) + "' from the caller workspace."; %#ok<AGROW>
    return;
end

try
    solution = solve(algebraicEquations(1), target);
catch exc
    notes{end + 1} = "DAE/algebraic route delegated: symbolic solve failed for algebraic variable '" + string(algebraicNames{1}) + "' with message: " + string(exc.message); %#ok<AGROW>
    return;
end

if isempty(solution) || numel(solution) ~= 1
    notes{end + 1} = "DAE/algebraic route delegated: algebraic solve did not return a unique reduction for '" + string(algebraicNames{1}) + "'."; %#ok<AGROW>
    return;
end

reducedEquations = subs(differentialEquations, target, solution);
equationTexts = arrayfun(@char, reducedEquations(:), "UniformOutput", false);
if any(contains(equationTexts, char(string(target))))
    notes{end + 1} = "DAE/algebraic route delegated: algebraic variable '" + string(algebraicNames{1}) + "' remained after attempted substitution."; %#ok<AGROW>
    return;
end

[reducedPreview, reducedNotes, reducedOk] = localBuildVectorFieldPreview( ...
    reducedEquations, ...
    states, ...
    inputs, ...
    parameters, ...
    timeVariable, ...
    "dae_reduced_to_explicit_ode", ...
    "algebraic_elimination+odeToVectorField");
notes = [notes, reducedNotes];
result = reducedPreview;
if reducedOk
    notes{end + 1} = "Reducible DAE preview inferred natively by solving algebraic variable '" + string(algebraicNames{1}) + "' before explicit-ODE lowering."; %#ok<AGROW>
    ok = true;
    return;
end

result.Route = "dae_algebraic";
result.Status = "delegated";
end

function [differentialEquations, algebraicEquations] = localPartitionDifferentialAndAlgebraicEquations(symbolicEquations)
differentialEquations = sym.empty(0, 1);
algebraicEquations = sym.empty(0, 1);
for index = 1:numel(symbolicEquations)
    equation = symbolicEquations(index);
    if contains(char(equation), "diff(")
        differentialEquations(end + 1, 1) = equation; %#ok<AGROW>
    else
        algebraicEquations(end + 1, 1) = equation; %#ok<AGROW>
    end
end
end

function names = localResolveAlgebraicNames(algebraics, algebraicEquations, states, inputs, parameters, timeVariable, callerWorkspace)
names = reshape(localUniqueCell(algebraics), 1, []);
if ~isempty(names)
    return;
end

reserved = localUniqueCell([states(:); inputs(:); parameters(:); {timeVariable}; localKnownFunctionNames()']);
rawNames = {};
for index = 1:numel(algebraicEquations)
    tokens = regexp(char(algebraicEquations(index)), "[A-Za-z][A-Za-z0-9_]*", "match");
    for tokenIndex = 1:numel(tokens)
        token = tokens{tokenIndex};
        if any(strcmp(token, reserved))
            continue;
        end
        if isfield(callerWorkspace, token)
            value = callerWorkspace.(token);
            if isa(value, "symfun") || isa(value, "sym")
                rawNames{end + 1} = token; %#ok<AGROW>
            end
        end
    end
end
names = reshape(localUniqueCell(rawNames), 1, []);
end

function target = localResolveCallerSymbol(callerWorkspace, name)
target = sym.empty(0, 1);
if ~isfield(callerWorkspace, name)
    return;
end
value = callerWorkspace.(name);
if isa(value, "symfun") || isa(value, "sym")
    target = value;
end
end

function orderedStates = localCanonicalStateOrder(canonicalBasis, preferredBases)
entries = repmat(struct("name", "", "base", "", "order", 0), 1, numel(canonicalBasis));
for index = 1:numel(canonicalBasis)
    [base, order] = localSplitCanonicalStateName(canonicalBasis{index});
    entries(index).name = canonicalBasis{index};
    entries(index).base = base;
    entries(index).order = order;
end

preferredBases = reshape(localUniqueCell(preferredBases), 1, []);
baseOrder = containers.Map("KeyType", "char", "ValueType", "double");
for index = 1:numel(preferredBases)
    baseOrder(preferredBases{index}) = index;
end

fallbackBases = unique({entries.base});
fallbackBases = sort(fallbackBases);
fallbackOrder = containers.Map("KeyType", "char", "ValueType", "double");
for index = 1:numel(fallbackBases)
    fallbackOrder(fallbackBases{index}) = index;
end

[~, order] = sortrows( ...
    [arrayfun(@(entry) localBaseRank(baseOrder, fallbackOrder, entry.base), entries).', arrayfun(@(entry) entry.order, entries).'], ...
    [1, 2]);
orderedStates = {entries(order).name};
end

function rank = localBaseRank(baseOrder, fallbackOrder, base)
if isKey(baseOrder, base)
    rank = baseOrder(base);
    return;
end
rank = 1000 + fallbackOrder(base);
end

function rhs = localCanonicalizeRhs(rhs, canonicalBasis, inputs, timeVariable)
for index = 1:numel(canonicalBasis)
    pattern = sprintf("Y\\[%d\\]", index);
    rhs = regexprep(rhs, pattern, canonicalBasis{index});
end

for index = 1:numel(inputs)
    name = char(string(inputs{index}));
    if isempty(name)
        continue;
    end
    pattern = sprintf("%s\\(\\s*%s\\s*\\)", regexptranslate('escape', name), regexptranslate('escape', char(string(timeVariable))));
    rhs = regexprep(rhs, pattern, name);
end
rhs = strtrim(rhs);
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

function [canonicalName, ok] = localCanonicalStateName(rawBasis)
token = char(string(rawBasis));
token = token(:).';
token = regexprep(token, "\s+", "");
match = regexp(token, "^D(?<order>[0-9]+)(?<base>[A-Za-z][A-Za-z0-9_]*)$", "names");
if ~isempty(match)
    canonicalName = localBuildCanonicalStateName(match.base, str2double(match.order));
    ok = true;
    return;
end

match = regexp(token, "^D(?<base>[A-Za-z][A-Za-z0-9_]*)$", "names");
if ~isempty(match)
    canonicalName = localBuildCanonicalStateName(match.base, 1);
    ok = true;
    return;
end

match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)$", "names");
if ~isempty(match)
    canonicalName = localBuildCanonicalStateName(match.base, 0);
    ok = true;
    return;
end

canonicalName = "";
ok = false;
end

function [base, order] = localSplitCanonicalStateName(name)
token = char(string(name));
token = token(:).';
match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)_ddot$", "names");
if ~isempty(match)
    base = match.base;
    order = 2;
    return;
end

match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)_dot$", "names");
if ~isempty(match)
    base = match.base;
    order = 1;
    return;
end

match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)_d(?<order>[0-9]+)$", "names");
if ~isempty(match)
    base = match.base;
    order = str2double(match.order);
    return;
end

base = token;
order = 0;
end

function stateName = localBuildCanonicalStateName(base, order)
switch order
    case 0
        stateName = char(base);
    case 1
        stateName = [char(base) '_dot'];
    case 2
        stateName = [char(base) '_ddot'];
    otherwise
        stateName = sprintf("%s_d%d", char(base), order);
end
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
	values = unique(values, "stable");
end

function preview = localEmptyFirstOrderPreview
preview = struct( ...
    "Available", false, ...
    "Method", "", ...
    "States", {{}}, ...
    "Inputs", {{}}, ...
    "Parameters", {{}}, ...
    "IndependentVariable", "", ...
    "OriginalStateBasis", {{}}, ...
    "StateEquations", struct("state", {}, "rhs", {}) ...
);
end
