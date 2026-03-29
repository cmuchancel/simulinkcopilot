function [tf, reason] = isNativeExplicitOdeEligible(sourceType, preview)
% isNativeExplicitOdeEligible Determine whether matlabv2native can lower the problem natively.

if ~strcmp(sourceType, "matlab_symbolic")
    tf = false;
    reason = "native lowering currently requires matlab_symbolic source input";
    return;
end

if ~isstruct(preview) || ~isfield(preview, "Route") || ~strcmp(char(string(preview.Route)), "explicit_ode")
    tf = false;
    reason = "native lowering currently requires an explicit_ode native preview";
    return;
end

if ~isfield(preview, "FirstOrderPreview") || ~isstruct(preview.FirstOrderPreview)
    tf = false;
    reason = "native lowering currently requires a first-order preview";
    return;
end

if ~isfield(preview.FirstOrderPreview, "Available") || ~logical(preview.FirstOrderPreview.Available)
    tf = false;
    reason = "native lowering currently requires an available first-order preview";
    return;
end

tf = true;
reason = "";
end
