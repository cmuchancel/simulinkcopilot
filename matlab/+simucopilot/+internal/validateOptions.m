function opts = validateOptions(defaultOverrides, varargin)
% validateOptions Parse and normalize shared MATLAB bridge options.

if nargin < 1 || isempty(defaultOverrides)
    defaultOverrides = struct();
end

defaults = simucopilot.internal.backendDefaults();
overrideFields = fieldnames(defaultOverrides);
for index = 1:numel(overrideFields)
    defaults.(overrideFields{index}) = defaultOverrides.(overrideFields{index});
end

parser = inputParser;
parser.FunctionName = "simucopilot.internal.validateOptions";

addParameter(parser, "States", {}, @(value) localIsTextList(value));
addParameter(parser, "Algebraics", {}, @(value) localIsTextList(value));
addParameter(parser, "Inputs", {}, @(value) localIsTextList(value));
addParameter(parser, "Parameters", {}, @(value) localIsTextList(value));
addParameter(parser, "TimeVariable", defaults.TimeVariable, @(value) ischar(value) || isstring(value));
addParameter(parser, "Build", defaults.Build, @(value) islogical(value) || isnumeric(value));
addParameter(parser, "RunSim", defaults.RunSim, @(value) islogical(value) || isnumeric(value));
addParameter(parser, "OpenModel", defaults.OpenModel, @(value) islogical(value) || isnumeric(value));
addParameter(parser, "ModelName", defaults.ModelName, @(value) ischar(value) || isstring(value));
addParameter(parser, "PythonExecutable", defaults.PythonExecutable, @(value) ischar(value) || isstring(value));
addParameter(parser, "BackendEntryPoint", defaults.BackendEntryPoint, @(value) ischar(value) || isstring(value));
addParameter(parser, "KeepTempFiles", defaults.KeepTempFiles, @(value) islogical(value) || isnumeric(value));
addParameter(parser, "Verbose", defaults.Verbose, @(value) islogical(value) || isnumeric(value));
addParameter(parser, "ClassificationMode", defaults.ClassificationMode, @(value) ischar(value) || isstring(value));
addParameter(parser, "SymbolConfig", defaults.SymbolConfig, @(value) isstruct(value) || isempty(value));
addParameter(parser, "RuntimeOverride", defaults.RuntimeOverride, @(value) isstruct(value) || isempty(value));
addParameter(parser, "SimulinkOutputDir", defaults.SimulinkOutputDir, @(value) ischar(value) || isstring(value));
addParameter(parser, "Assumptions", defaults.Assumptions, @(value) isstruct(value) || isempty(value));
addParameter(parser, "DerivativeMap", defaults.DerivativeMap, @(value) isstruct(value) || isempty(value));
addParameter(parser, "Tolerance", defaults.Tolerance, @(value) isempty(value) || (isnumeric(value) && isscalar(value)));

parse(parser, varargin{:});
opts = parser.Results;

opts.States = localToCellstr(opts.States);
opts.Algebraics = localToCellstr(opts.Algebraics);
opts.Inputs = localToCellstr(opts.Inputs);
opts.Parameters = localToCellstr(opts.Parameters);
opts.TimeVariable = char(string(opts.TimeVariable));
opts.Build = logical(opts.Build);
opts.RunSim = logical(opts.RunSim);
opts.OpenModel = logical(opts.OpenModel);
opts.ModelName = char(string(opts.ModelName));
opts.PythonExecutable = char(string(opts.PythonExecutable));
opts.BackendEntryPoint = char(string(opts.BackendEntryPoint));
opts.KeepTempFiles = logical(opts.KeepTempFiles);
opts.Verbose = logical(opts.Verbose);
opts.ClassificationMode = char(string(opts.ClassificationMode));
opts.SimulinkOutputDir = char(string(opts.SimulinkOutputDir));

if isempty(opts.SymbolConfig)
    opts.SymbolConfig = struct();
end
if isempty(opts.RuntimeOverride)
    opts.RuntimeOverride = struct();
end
if isempty(opts.Assumptions)
    opts.Assumptions = struct();
end
if isempty(opts.DerivativeMap)
    opts.DerivativeMap = struct();
end

if ~isempty(opts.ClassificationMode) && ~any(strcmp(opts.ClassificationMode, {"strict", "configured"}))
    error("simucopilot:InvalidClassificationMode", ...
        "ClassificationMode must be 'strict', 'configured', or empty.");
end

if ~opts.Build && opts.OpenModel
    error("simucopilot:InvalidOpenModelOption", ...
        "OpenModel requires Build=true.");
end

if ~isempty(opts.Tolerance) && opts.Tolerance <= 0
    error("simucopilot:InvalidTolerance", ...
        "Tolerance must be positive when provided.");
end
end

function tf = localIsTextList(value)
tf = isempty(value) || ischar(value) || isstring(value) || iscellstr(value);
if tf && iscell(value)
    tf = all(cellfun(@(item) ischar(item) || isstring(item), value));
end
end

function values = localToCellstr(raw)
if isempty(raw)
    values = {};
    return;
end
if ischar(raw)
    values = {char(raw)};
    return;
end
if isstring(raw)
    values = cellstr(raw(:).');
    return;
end
if iscell(raw)
    values = cellfun(@char, raw, "UniformOutput", false);
    return;
end
error("simucopilot:InvalidTextList", "Expected a string, string array, char vector, or cell array of strings.");
end
