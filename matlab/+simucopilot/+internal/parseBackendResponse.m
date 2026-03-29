function out = parseBackendResponse(rawResponse)
% parseBackendResponse Convert backend JSON into a MATLAB-friendly struct.

status = string(localField(rawResponse, "status", ""));
if strlength(status) == 0
    error("simucopilot:InvalidBackendResponse", ...
        "Backend response is missing a status field.");
end

if status == "error"
    errorCode = string(localField(rawResponse, "error_code", "backend_error"));
    message = char(string(localField(rawResponse, "message", "Backend request failed.")));
    error(char("simucopilot:" + errorCode), "%s", message);
end

out = struct();
out.Status = char(status);
out.Route = localField(rawResponse, "route", []);
out.Message = localField(rawResponse, "message", "");
out.Diagnostics = localField(rawResponse, "diagnostics", {});
out.Validation = localField(rawResponse, "validation", struct());
out.NormalizedProblem = localField(rawResponse, "normalized_problem", struct());
out.FirstOrder = localField(rawResponse, "first_order", struct());
out.GeneratedModelPath = localField(rawResponse, "generated_model_path", "");
out.ModelName = localField(rawResponse, "model_name", "");
out.Artifacts = localField(rawResponse, "artifacts", struct());
out.RawBackendResponse = rawResponse;
end

function value = localField(rawResponse, name, fallback)
if isstruct(rawResponse) && isfield(rawResponse, name)
    value = rawResponse.(name);
else
    value = fallback;
end
end
