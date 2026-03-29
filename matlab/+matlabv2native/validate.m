function out = validate(primaryInput, varargin)
% matlabv2native.validate Build, simulate, and require validation to pass.

out = matlabv2native.generate(primaryInput, varargin{:});
if ~localValidationPasses(out.Validation)
    error("matlabv2native:ValidationFailed", ...
        "Generated model failed validation for route '%s'.", char(string(out.Route)));
end
out.Validated = true;
end

function tf = localValidationPasses(validation)
tf = false;
if ~isstruct(validation) || ~isfield(validation, "passes")
    return;
end
passes = validation.passes;
if islogical(passes)
    tf = isscalar(passes) && passes;
elseif isnumeric(passes)
    tf = isscalar(passes) && logical(passes);
end
end
