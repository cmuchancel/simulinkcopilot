function [result, notes] = nativeExplicitOdePreview(primaryInput, sourceType, states, inputs, parameters, timeVariable)
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

try
    [vectorField, stateBasis] = odeToVectorField(symbolicEquations);
catch exc
    notes{end + 1} = "Native explicit-ODE preview delegated: " + string(exc.message); %#ok<AGROW>
    return;
end

canonicalBasis = cell(numel(stateBasis), 1);
for index = 1:numel(stateBasis)
    [canonicalName, ok] = localCanonicalStateName(stateBasis(index));
    if ~ok
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

result.Route = "explicit_ode";
result.Status = "native_supported";
result.FirstOrderPreview = struct( ...
    "Available", true, ...
    "Method", "odeToVectorField", ...
    "States", {orderedStates}, ...
    "Inputs", {reshape(localUniqueCell(inputs), 1, [])}, ...
    "Parameters", {reshape(localUniqueCell(parameters), 1, [])}, ...
    "IndependentVariable", char(string(timeVariable)), ...
    "OriginalStateBasis", {cellstr(string(stateBasis(:)).')}, ...
    "StateEquations", stateEquations ...
);
notes{end + 1} = "Explicit-ODE route preview inferred natively with odeToVectorField."; %#ok<AGROW>
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
