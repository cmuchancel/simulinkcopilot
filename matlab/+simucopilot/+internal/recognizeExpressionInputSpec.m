function spec = recognizeExpressionInputSpec(expressionText, timeVariable)
% recognizeExpressionInputSpec Recognize common symbolic input expressions as native specs.

spec = [];
expr = regexprep(char(string(expressionText)), "\s+", "");
timeValue = char(string(timeVariable));
if isempty(strtrim(timeValue))
    return;
end

timeToken = regexptranslate("escape", timeValue);
numberToken = localNumberPattern();

if ~isempty(regexp(expr, ['^heaviside\(' timeToken '\)$'], "once"))
    spec = struct("kind", "step", "step_time", 0, "bias", 0, "amplitude", 1);
    return;
end

match = regexp(expr, ['^heaviside\(' timeToken '\-(?<delay>' numberToken ')\)$'], "names");
if ~isempty(match)
    spec = struct("kind", "step", "step_time", localNumericTokenToDouble(match.delay), "bias", 0, "amplitude", 1);
    return;
end

match = regexp(expr, ['^heaviside\(' timeToken '\+(?<delay>' numberToken ')\)$'], "names");
if ~isempty(match)
    spec = struct("kind", "step", "step_time", -localNumericTokenToDouble(match.delay), "bias", 0, "amplitude", 1);
    return;
end

match = regexp(expr, ...
    ['^(?<amp>' numberToken ')\*heaviside\(' timeToken '\-(?<start>' numberToken ')\)(?<second>[+-])(?<amp2>' numberToken ')\*heaviside\(' timeToken '\-(?<stop>' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    "names");
if ~isempty(match)
    amp1 = localNumericTokenToDouble(match.amp);
    amp2 = localNumericTokenToDouble(match.amp2);
    startTime = localNumericTokenToDouble(match.start);
    stopTime = localNumericTokenToDouble(match.stop);
    if match.second == '-' && abs(amp1 - amp2) <= 1e-9 && stopTime > startTime
        bias = 0.0;
        if isfield(match, "bias") && ~isempty(match.bias)
            bias = localNumericTokenToDouble(match.bias);
        end
        spec = struct( ...
            "kind", "pulse", ...
            "amplitude", amp1, ...
            "start_time", startTime, ...
            "width", stopTime - startTime, ...
            "bias", bias);
        return;
    end
end

spec = localRecognizeRamp(expr, timeToken, numberToken);
if ~isempty(spec)
    return;
end

spec = localRecognizeSineLike(expr, timeToken, numberToken);
if ~isempty(spec)
    return;
end

spec = localRecognizeSquare(expr, timeToken, numberToken);
if ~isempty(spec)
    return;
end

spec = localRecognizeRepeatingSequence(expr, timeToken, numberToken);
end

function spec = localRecognizeRamp(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\((?<slope>' numberToken ')\*' timeToken '(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\(' timeToken '\*(?<slope>' numberToken ')(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\(\((?<num>' numberToken ')\*' timeToken '\)/(?<den>' numberToken ')(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\(\(' timeToken '\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'] ...
};

match = [];
for index = 1:numel(patterns)
    current = regexp(expr, patterns{index}, "names");
    if isempty(current)
        continue;
    end
    if isfield(current, "num") && isfield(current, "den")
        current.slope = num2str(localNumericTokenToDouble(current.num) / localNumericTokenToDouble(current.den), 17);
    end
    match = current;
    break;
end

if isempty(match)
    return;
end

startTime = localNumericTokenToDouble(match.start);
slope = localNumericTokenToDouble(match.slope);
offset = localNumericTokenToDouble(match.offset);
if abs(offset - (-slope * startTime)) > 1e-9
    return;
end

bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end

spec = struct("kind", "ramp", "slope", slope, "start_time", startTime, "initial_output", bias);
end

function spec = localRecognizeSineLike(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^(?:(?<amp>' numberToken ')\*)?(?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*(?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'] ...
};

match = [];
for index = 1:numel(patterns)
    current = regexp(expr, patterns{index}, "names");
    if isempty(current)
        continue;
    end
    if isfield(current, "num") && isfield(current, "den")
        current.amp = num2str(localNumericTokenToDouble(current.num) / localNumericTokenToDouble(current.den), 17);
    end
    match = current;
    break;
end

if isempty(match)
    return;
end

amplitude = 1.0;
if isfield(match, "amp") && ~isempty(match.amp)
    amplitude = localNumericTokenToDouble(match.amp);
end
phase = 0.0;
if isfield(match, "phase") && ~isempty(match.phase)
    phase = localNumericTokenToDouble(match.phase);
end
if strcmp(match.fn, "cos")
    phase = phase + pi / 2.0;
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end

spec = struct( ...
    "kind", "sine", ...
    "amplitude", amplitude, ...
    "frequency", localNumericTokenToDouble(match.freq), ...
    "phase", phase, ...
    "bias", bias);
end

function spec = localRecognizeSquare(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^(?:(?<amp>' numberToken ')\*)?sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\(sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'] ...
};

match = [];
for index = 1:numel(patterns)
    current = regexp(expr, patterns{index}, "names");
    if isempty(current)
        continue;
    end
    if isfield(current, "num") && isfield(current, "den")
        current.amp = num2str(localNumericTokenToDouble(current.num) / localNumericTokenToDouble(current.den), 17);
    end
    match = current;
    break;
end

if isempty(match)
    return;
end

amplitude = 1.0;
if isfield(match, "amp") && ~isempty(match.amp)
    amplitude = localNumericTokenToDouble(match.amp);
end
phase = 0.0;
if isfield(match, "phase") && ~isempty(match.phase)
    phase = localNumericTokenToDouble(match.phase);
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end

spec = struct( ...
    "kind", "square", ...
    "amplitude", amplitude, ...
    "frequency", localNumericTokenToDouble(match.freq), ...
    "phase", phase, ...
    "bias", bias);
end

function spec = localRecognizeRepeatingSequence(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^(?<amp>' numberToken ')\*sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\(sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<amp>' numberToken ')\*sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\(sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'] ...
};

match = [];
for index = 1:numel(patterns)
    current = regexp(expr, patterns{index}, "names");
    if isempty(current)
        continue;
    end
    if isfield(current, "num") && isfield(current, "den")
        current.amp = num2str(localNumericTokenToDouble(current.num) / localNumericTokenToDouble(current.den), 17);
    end
    match = current;
    break;
end

if isempty(match)
    return;
end

amplitude = 1.0;
if isfield(match, "amp") && ~isempty(match.amp)
    amplitude = localNumericTokenToDouble(match.amp);
end
phase = 0.0;
if isfield(match, "phase") && ~isempty(match.phase)
    phase = localNumericTokenToDouble(match.phase);
end
width = 1.0;
if isfield(match, "width") && ~isempty(match.width)
    width = localNumericTokenToDouble(match.width);
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end

kind = "sawtooth";
if abs(width - 0.5) <= 1e-12
    kind = "triangle";
end

spec = struct( ...
    "kind", kind, ...
    "amplitude", amplitude, ...
    "frequency", localNumericTokenToDouble(match.freq), ...
    "phase", phase, ...
    "bias", bias, ...
    "width", width);
end

function pattern = localNumberPattern()
pattern = '[-+]?(?:[0-9]*\.?[0-9]+|[0-9]+/[0-9]+)';
end

function value = localNumericTokenToDouble(token)
value = double(vpa(str2sym(char(string(token)))));
end
