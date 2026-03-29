function [sourceType, opts, invocation] = prepareInvocation(defaultOverrides, primaryInput, varargin)
% prepareInvocation Parse matlabv2native public options and infer the backend source type.

parser = inputParser;
parser.FunctionName = "matlabv2native.internal.prepareInvocation";
parser.KeepUnmatched = true;
addParameter(parser, "SourceType", "auto", @(value) ischar(value) || isstring(value));
addParameter(parser, "State", {}, @(value) localIsTextList(value));
addParameter(parser, "ParityMode", "runtime", @(value) ischar(value) || isstring(value));
parse(parser, varargin{:});

sourceType = matlabv2native.internal.inferSourceType(primaryInput, parser.Results.SourceType);
unmatched = parser.Unmatched;
if ~isempty(parser.Results.State)
    if isfield(unmatched, "States") && ~isempty(unmatched.States)
        error("matlabv2native:ConflictingStateOptions", ...
            "Use either 'State' or 'States', not both.");
    end
    unmatched.States = parser.Results.State;
end

parityMode = localNormalizeParityMode(parser.Results.ParityMode);

nameValueArgs = localStructToNameValue(unmatched);
opts = simucopilot.internal.validateOptions(defaultOverrides, nameValueArgs{:});
invocation = struct( ...
    "RequestedSourceType", char(string(parser.Results.SourceType)), ...
    "ResolvedSourceType", sourceType, ...
    "ParityMode", parityMode ...
);
end

function tf = localIsTextList(value)
tf = isempty(value) || ischar(value) || isstring(value) || iscellstr(value);
if tf && iscell(value)
    tf = all(cellfun(@(item) ischar(item) || isstring(item), value));
end
end

function nv = localStructToNameValue(values)
fields = fieldnames(values);
nv = cell(1, numel(fields) * 2);
for index = 1:numel(fields)
    nv{2 * index - 1} = fields{index};
    nv{2 * index} = values.(fields{index});
end
end

function mode = localNormalizeParityMode(raw)
mode = lower(strtrim(char(string(raw))));
switch mode
    case {"runtime", "native", "off"}
        mode = "runtime";
    case {"python", "parity", "compare", "on"}
        mode = "python";
    otherwise
        error("matlabv2native:InvalidParityMode", ...
            "ParityMode must be 'runtime' or 'python'.");
end
end
