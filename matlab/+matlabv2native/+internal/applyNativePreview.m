function opts = applyNativePreview(opts, preview)
% applyNativePreview Seed shared bridge options from native preview results.

if isempty(opts.States) && isfield(preview, "States")
    opts.States = preview.States;
end
if isempty(opts.Algebraics) && isfield(preview, "Algebraics")
    opts.Algebraics = preview.Algebraics;
end
if isempty(opts.Inputs) && isfield(preview, "Inputs")
    opts.Inputs = preview.Inputs;
end
if isempty(opts.Parameters) && isfield(preview, "Parameters")
    opts.Parameters = preview.Parameters;
end
if isempty(strtrim(opts.TimeVariable)) && isfield(preview, "TimeVariable")
    opts.TimeVariable = char(string(preview.TimeVariable));
end
end
