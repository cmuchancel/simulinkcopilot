function [sourceType, opts] = prepareInvocation(defaultOverrides, primaryInput, varargin)
% prepareInvocation Parse matlabv1 public options and infer the backend source type.

parser = inputParser;
parser.FunctionName = "matlabv1.internal.prepareInvocation";
parser.KeepUnmatched = true;
addParameter(parser, "SourceType", "auto", @(value) ischar(value) || isstring(value));
addParameter(parser, "State", {}, @(value) localIsTextList(value));
parse(parser, varargin{:});

sourceType = matlabv1.internal.inferSourceType(primaryInput, parser.Results.SourceType);

unmatched = parser.Unmatched;
if ~isempty(parser.Results.State)
    if isfield(unmatched, "States") && ~isempty(unmatched.States)
        error("matlabv1:ConflictingStateOptions", ...
            "Use either 'State' or 'States', not both.");
    end
    unmatched.States = parser.Results.State;
end

nameValueArgs = localStructToNameValue(unmatched);
opts = simucopilot.internal.validateOptions(defaultOverrides, nameValueArgs{:});
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
