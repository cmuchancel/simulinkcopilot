function report = comparePreviewToProblem(preview, backendOut)
% comparePreviewToProblem Compare native MATLAB preview data against the Python backend oracle.

normalizedProblem = localStruct(backendOut, "NormalizedProblem");
nativeStates = localCell(preview, "States");
nativeAlgebraics = localCell(preview, "Algebraics");
nativeInputs = localCell(preview, "Inputs");
nativeParameters = localCell(preview, "Parameters");
nativeTime = char(string(localScalar(preview, "TimeVariable", "")));
nativeRoute = char(string(localScalar(preview, "Route", "")));
nativeFirstOrder = localStruct(preview, "FirstOrderPreview");
nativeFirstOrderStates = localOrderedCell(nativeFirstOrder, "States");
nativeFirstOrderEquationStates = localStateEquationStates(nativeFirstOrder);

pythonStates = localCell(normalizedProblem, "states");
pythonAlgebraics = localCell(normalizedProblem, "algebraics");
pythonInputs = localCell(normalizedProblem, "inputs");
pythonParameters = localCell(normalizedProblem, "parameters");
pythonTime = char(string(localScalar(normalizedProblem, "time_variable", "")));
pythonRoute = char(string(localScalar(backendOut, "Route", "")));
pythonFirstOrder = localStruct(backendOut, "FirstOrder");
pythonFirstOrderStates = localOrderedCell(pythonFirstOrder, "states");
pythonFirstOrderEquationStates = localStateEquationStates(pythonFirstOrder);

matches = struct( ...
    "states", isequal(nativeStates, pythonStates), ...
    "algebraics", isequal(nativeAlgebraics, pythonAlgebraics), ...
    "inputs", isequal(nativeInputs, pythonInputs), ...
    "parameters", isequal(nativeParameters, pythonParameters), ...
    "time_variable", strcmp(nativeTime, pythonTime) ...
);

comparedFields = {"states", "algebraics", "inputs", "parameters", "time_variable"};
uncomparedFields = {"generated_model", "validation", "input_block_family", "simulation_traces"};

if ~isempty(nativeRoute)
    matches.route = strcmp(nativeRoute, pythonRoute);
    comparedFields{end + 1} = "route"; %#ok<AGROW>
else
    uncomparedFields{end + 1} = "route"; %#ok<AGROW>
end

if localLogical(nativeFirstOrder, "Available", false) && ~isempty(pythonFirstOrderStates)
    matches.first_order_states = isequal(nativeFirstOrderStates, pythonFirstOrderStates);
    matches.first_order_equation_state_order = isequal(nativeFirstOrderEquationStates, pythonFirstOrderEquationStates);
    comparedFields{end + 1} = "first_order_states"; %#ok<AGROW>
    comparedFields{end + 1} = "first_order_equation_state_order"; %#ok<AGROW>
    uncomparedFields{end + 1} = "first_order_rhs"; %#ok<AGROW>
else
    uncomparedFields{end + 1} = "first_order_states"; %#ok<AGROW>
    uncomparedFields{end + 1} = "first_order_equation_state_order"; %#ok<AGROW>
    uncomparedFields{end + 1} = "first_order_rhs"; %#ok<AGROW>
end

report = struct();
report.Kind = "parity_phase2_preview";
report.Matches = matches;
report.ComparedFields = comparedFields;
report.AllComparedFieldsMatch = all(cellfun(@(name) logical(matches.(name)), comparedFields));
report.Native = struct( ...
    "states", {nativeStates}, ...
    "algebraics", {nativeAlgebraics}, ...
    "inputs", {nativeInputs}, ...
    "parameters", {nativeParameters}, ...
    "time_variable", nativeTime, ...
    "route", nativeRoute, ...
    "first_order", nativeFirstOrder ...
);
report.Python = struct( ...
    "states", {pythonStates}, ...
    "algebraics", {pythonAlgebraics}, ...
    "inputs", {pythonInputs}, ...
    "parameters", {pythonParameters}, ...
    "time_variable", pythonTime, ...
    "route", pythonRoute, ...
    "first_order", pythonFirstOrder ...
);
report.UncomparedFields = reshape(unique(cellfun(@(item) char(string(item)), uncomparedFields, "UniformOutput", false)), 1, []);
report.DelegatedFields = localCell(preview, "DelegatedFields");
end

function values = localOrderedCell(container, fieldName)
if isstruct(container) && isfield(container, fieldName)
    raw = container.(fieldName);
else
    raw = {};
end

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
    values = reshape(cellfun(@(item) char(string(item)), raw, "UniformOutput", false), 1, []);
    return;
end
values = {char(string(raw))};
end

function values = localCell(container, fieldName)
if nargin == 2 && isstruct(container) && isfield(container, fieldName)
    raw = container.(fieldName);
else
    raw = container;
end

if isempty(raw)
    values = {};
    return;
end
if ischar(raw)
    values = {char(raw)};
    values = reshape(unique(values), 1, []);
    return;
end
if isstring(raw)
    values = reshape(unique(cellstr(raw(:).')), 1, []);
    return;
end
if iscell(raw)
    values = reshape(unique(cellfun(@(item) char(string(item)), raw, "UniformOutput", false)), 1, []);
    return;
end
values = {char(string(raw))};
values = reshape(values, 1, []);
end

function values = localStateEquationStates(container)
if isstruct(container) && isfield(container, "state_equations")
    raw = container.state_equations;
elseif isstruct(container) && isfield(container, "StateEquations")
    raw = container.StateEquations;
else
    raw = struct("state", {}, "rhs", {});
end

values = {};
for index = 1:numel(raw)
    if isfield(raw(index), "state")
        values{end + 1} = char(string(raw(index).state)); %#ok<AGROW>
    end
end
values = reshape(values, 1, []);
end

function value = localScalar(container, fieldName, fallback)
if isstruct(container) && isfield(container, fieldName)
    value = container.(fieldName);
else
    value = fallback;
end
end

function value = localLogical(container, fieldName, fallback)
value = localScalar(container, fieldName, fallback);
value = logical(value);
end

function value = localStruct(container, fieldName)
if isstruct(container) && isfield(container, fieldName) && isstruct(container.(fieldName))
    value = container.(fieldName);
else
    value = struct();
end
end
