function payload = readJson(path)
% readJson Read a JSON file into a MATLAB struct.

if ~isfile(path)
    error("simucopilot:JsonReadFailed", ...
        "JSON file does not exist: %s", path);
end
payload = jsondecode(fileread(path));
end
