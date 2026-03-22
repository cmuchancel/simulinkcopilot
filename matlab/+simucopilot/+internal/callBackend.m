function out = callBackend(request, opts)
% callBackend Invoke the Python backend through the JSON bridge.

if ~isstruct(request)
    error("simucopilot:InvalidBackendRequest", ...
        "Backend request must be a struct.");
end

tempRoot = tempname;
mkdir(tempRoot);
cleanupObj = onCleanup(@() localCleanup(tempRoot, opts.KeepTempFiles));

requestPath = fullfile(tempRoot, "request.json");
responsePath = fullfile(tempRoot, "response.json");
simucopilot.internal.writeJson(requestPath, request);

command = localBuildCommand(opts, requestPath, responsePath);
[status, commandOutput] = system(command);
if opts.Verbose && ~isempty(commandOutput)
    fprintf("%s\n", commandOutput);
end

if ~isfile(responsePath)
    lowerOutput = lower(string(commandOutput));
    if contains(lowerOutput, "not found") || contains(lowerOutput, "is not recognized")
        error("simucopilot:PythonExecutableNotFound", ...
            "Python executable not found. Set 'PythonExecutable' explicitly or configure your environment.");
    end
    error("simucopilot:MissingBackendResponse", ...
        "Backend response file was not created; Python backend may have crashed before completion.");
end

rawResponse = simucopilot.internal.readJson(responsePath);
out = simucopilot.internal.parseBackendResponse(rawResponse);
out.Command = command;
out.CommandOutput = commandOutput;
if opts.KeepTempFiles
    out.TempDirectory = tempRoot;
else
    out.TempDirectory = "";
end

if opts.OpenModel && ~isempty(out.GeneratedModelPath)
    if ~isfile(out.GeneratedModelPath)
        error("simucopilot:MissingGeneratedModel", ...
            "Generated model path does not exist: %s", out.GeneratedModelPath);
    end
    open_system(out.GeneratedModelPath);
end

if status ~= 0 && opts.Verbose
    fprintf("%s\n", commandOutput);
end
clear cleanupObj
end

function command = localBuildCommand(opts, requestPath, responsePath)
quotedRepo = localQuote(opts.RepoRoot);
quotedPython = localQuote(opts.PythonExecutable);
quotedRequest = localQuote(requestPath);
quotedResponse = localQuote(responsePath);
backendEntryPoint = char(opts.BackendEntryPoint);

if ispc
    command = sprintf( ...
        'cd /d %s && %s -m %s --request %s --response %s', ...
        quotedRepo, quotedPython, backendEntryPoint, quotedRequest, quotedResponse);
else
    command = sprintf( ...
        'cd %s && %s -m %s --request %s --response %s', ...
        quotedRepo, quotedPython, backendEntryPoint, quotedRequest, quotedResponse);
end
end

function localCleanup(tempRoot, keepTempFiles)
if keepTempFiles
    return;
end
if isfolder(tempRoot)
    rmdir(tempRoot, "s");
end
end

function quoted = localQuote(value)
quoted = ['"' strrep(char(string(value)), '"', '\"') '"'];
end
