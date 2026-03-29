function sourceType = inferSourceType(primaryInput, requestedSourceType)
% inferSourceType Determine which shared backend front door should handle the MATLAB input.

requested = lower(strtrim(char(string(requestedSourceType))));
if isempty(requested) || strcmp(requested, "auto")
    sourceType = localInfer(primaryInput);
    return;
end

supported = {"latex", "matlab_symbolic", "matlab_equation_text", "matlab_ode_function"};
if ~any(strcmp(requested, supported))
    error("matlabv1:InvalidSourceType", ...
        "SourceType must be 'auto', 'latex', 'matlab_symbolic', 'matlab_equation_text', or 'matlab_ode_function'.");
end
sourceType = requested;
end

function sourceType = localInfer(primaryInput)
if isa(primaryInput, "function_handle")
    error("matlabv1:OpaqueOdeFunction", ...
        "Opaque MATLAB function handles are not supported. Export a structured RHS spec or use equations directly.");
end

if isa(primaryInput, "sym") || isa(primaryInput, "symfun") || localCellContainsSymbolic(primaryInput)
    sourceType = "matlab_symbolic";
    return;
end

if isstruct(primaryInput)
    sourceType = "matlab_ode_function";
    return;
end

texts = localExtractTexts(primaryInput);
if isempty(texts)
    error("matlabv1:UnsupportedInputType", ...
        "matlabv1.generate/analyze supports symbolic equations, text equations, LaTeX equations, or structured ODE specs.");
end

lowered = lower(string(texts));
if any(contains(lowered, "\")) || any(contains(lowered, ["\\dot", "\\ddot", "\\frac", "\\left", "\\right"]))
    sourceType = "latex";
    return;
end

symbolicMarkers = [ ...
    "diff(", "==", "heaviside(", "dirac(", "piecewise(", ...
    "sawtooth(", "atan2(", "sat(", "rand(", "randn(" ...
];
if any(contains(lowered, symbolicMarkers))
    sourceType = "matlab_symbolic";
    return;
end

sourceType = "matlab_equation_text";
end

function tf = localCellContainsSymbolic(value)
tf = false;
if ~iscell(value)
    return;
end
for index = 1:numel(value)
    item = value{index};
    if isa(item, "sym") || isa(item, "symfun")
        tf = true;
        return;
    end
end
end

function texts = localExtractTexts(primaryInput)
if ischar(primaryInput)
    texts = {char(primaryInput)};
    return;
end
if isstring(primaryInput)
    texts = cellstr(primaryInput(:).');
    return;
end
if iscell(primaryInput)
    try
        texts = cellfun(@(item) char(string(item)), primaryInput, "UniformOutput", false);
    catch
        texts = {};
    end
    return;
end
texts = {};
end
