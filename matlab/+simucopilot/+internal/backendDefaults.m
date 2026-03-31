function defaults = backendDefaults()
% backendDefaults Return deterministic defaults for the MATLAB bridge.

internalRoot = fileparts(mfilename("fullpath"));
packageRoot = fileparts(internalRoot);
matlabRoot = fileparts(packageRoot);
repoRoot = fileparts(matlabRoot);

pythonExecutable = getenv("SIMULINKCOPILOT_PYTHON");
if isempty(pythonExecutable)
    pythonExecutable = localSelectPythonExecutable(repoRoot);
end

defaults = struct( ...
    "RepoRoot", repoRoot, ...
    "PythonExecutable", char(pythonExecutable), ...
    "BackendEntryPoint", "pipeline.run_pipeline", ...
    "KeepTempFiles", false, ...
    "Verbose", false, ...
    "Build", false, ...
    "RunSim", true, ...
    "OpenModel", false, ...
    "ModelName", "", ...
    "TimeVariable", "t", ...
    "ParameterValues", struct(), ...
    "SimulinkOutputDir", "", ...
    "ClassificationMode", "", ...
    "SymbolConfig", struct(), ...
    "RuntimeOverride", struct(), ...
    "NativeRhsStyle", "subsystem_native", ...
    "Assumptions", struct(), ...
    "DerivativeMap", struct(), ...
    "Tolerance", [] ...
);
end

function pythonExecutable = localSelectPythonExecutable(repoRoot)
if ispc
    repoPython = fullfile(repoRoot, ".venv", "Scripts", "python.exe");
else
    repoPython = fullfile(repoRoot, ".venv", "bin", "python");
end

candidates = {};
if exist(repoPython, "file") == 2
    candidates{end + 1} = repoPython; %#ok<AGROW>
    canonicalRepoPython = localCanonicalPath(repoPython);
    if ~strcmp(canonicalRepoPython, repoPython)
        candidates{end + 1} = canonicalRepoPython; %#ok<AGROW>
    end
end
candidates{end + 1} = "python3";

for idx = 1:numel(candidates)
    candidate = candidates{idx};
    if localPythonSupportsBackend(candidate)
        pythonExecutable = candidate;
        return;
    end
end

pythonExecutable = "python3";
end

function tf = localPythonSupportsBackend(candidate)
probe = sprintf('%s -c "import numpy, sympy, scipy"', localQuote(candidate));
[status, ~] = system(probe);
tf = status == 0;
end

function resolved = localCanonicalPath(pathValue)
resolved = char(java.io.File(pathValue).getCanonicalPath());
end

function quoted = localQuote(value)
quoted = ['"' strrep(char(string(value)), '"', '\"') '"'];
end
