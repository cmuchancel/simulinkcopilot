function writeJson(path, payload)
% writeJson Write a MATLAB struct to JSON.

jsonText = jsonencode(payload);
fileId = fopen(path, "w");
if fileId == -1
    error("simucopilot:JsonWriteFailed", ...
        "Unable to open JSON path for writing: %s", path);
end
cleanupObj = onCleanup(@() fclose(fileId));
fprintf(fileId, "%s", jsonText);
clear cleanupObj
end
