function report = comparePreviewToProblem(preview, normalizedProblem)
% comparePreviewToProblem Compare phase-1 native preview metadata against the Python-normalized problem.

nativeStates = localCell(preview, "States");
nativeAlgebraics = localCell(preview, "Algebraics");
nativeInputs = localCell(preview, "Inputs");
nativeParameters = localCell(preview, "Parameters");
nativeTime = char(string(localScalar(preview, "TimeVariable", "")));

pythonStates = localCell(normalizedProblem, "states");
pythonAlgebraics = localCell(normalizedProblem, "algebraics");
pythonInputs = localCell(normalizedProblem, "inputs");
pythonParameters = localCell(normalizedProblem, "parameters");
pythonTime = char(string(localScalar(normalizedProblem, "time_variable", "")));

matches = struct( ...
    "states", isequal(nativeStates, pythonStates), ...
    "algebraics", isequal(nativeAlgebraics, pythonAlgebraics), ...
    "inputs", isequal(nativeInputs, pythonInputs), ...
    "parameters", isequal(nativeParameters, pythonParameters), ...
    "time_variable", strcmp(nativeTime, pythonTime) ...
);

report = struct();
report.Kind = "metadata_parity_phase1";
report.Matches = matches;
report.AllComparedFieldsMatch = all(struct2array(matches));
report.Native = struct( ...
    "states", {nativeStates}, ...
    "algebraics", {nativeAlgebraics}, ...
    "inputs", {nativeInputs}, ...
    "parameters", {nativeParameters}, ...
    "time_variable", nativeTime ...
);
report.Python = struct( ...
    "states", {pythonStates}, ...
    "algebraics", {pythonAlgebraics}, ...
    "inputs", {pythonInputs}, ...
    "parameters", {pythonParameters}, ...
    "time_variable", pythonTime ...
);
report.UncomparedFields = {"route", "generated_model", "validation"};
report.DelegatedFields = localCell(preview, "DelegatedFields");
end

function values = localCell(container, fieldName)
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

function value = localScalar(container, fieldName, fallback)
if isstruct(container) && isfield(container, fieldName)
    value = container.(fieldName);
else
    value = fallback;
end
end
