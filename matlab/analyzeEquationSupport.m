function out = analyzeEquationSupport(varargin)
% analyzeEquationSupport Analyze backend support without requiring model build.

parser = inputParser;
parser.FunctionName = "analyzeEquationSupport";
parser.KeepUnmatched = true;
addParameter(parser, "SourceType", "", @(value) ischar(value) || isstring(value));
addParameter(parser, "Equations", [], @(value) true);
addParameter(parser, "FunctionSpec", [], @(value) true);
parse(parser, varargin{:});

sourceType = char(string(parser.Results.SourceType));
if isempty(strtrim(sourceType))
    error("simucopilot:MissingSourceType", ...
        "analyzeEquationSupport requires a 'SourceType' option.");
end

opts = simucopilot.internal.validateOptions( ...
    struct("Build", false, "OpenModel", false), ...
    localStructToNameValue(parser.Unmatched){:});

if strcmp(sourceType, "matlab_ode_function")
    primaryInput = parser.Results.FunctionSpec;
    if isempty(primaryInput)
        error("simucopilot:MissingFunctionSpec", ...
            "analyzeEquationSupport with SourceType='matlab_ode_function' requires 'FunctionSpec'.");
    end
else
    primaryInput = parser.Results.Equations;
    if isempty(primaryInput)
        error("simucopilot:MissingEquations", ...
            "analyzeEquationSupport requires 'Equations' for the selected SourceType.");
    end
end

request = simucopilot.internal.makeRequestStruct(sourceType, primaryInput, opts);
out = simucopilot.internal.callBackend(request, opts);
end

function nv = localStructToNameValue(values)
fields = fieldnames(values);
nv = cell(1, numel(fields) * 2);
for index = 1:numel(fields)
    nv{2 * index - 1} = fields{index};
    nv{2 * index} = values.(fields{index});
end
end
