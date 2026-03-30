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

spec = localRecognizeTime(expr, timeValue);
if ~isempty(spec)
    return;
end

spec = localRecognizeNumericConstant(expr, numberToken);
if ~isempty(spec)
    return;
end

spec = localRecognizeAffineStep(expr, timeToken, numberToken);
if ~isempty(spec)
    return;
end

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
if ~isempty(spec)
    return;
end

spec = localRecognizeUnaryNative(expr, timeValue, "sign", "sign");
if ~isempty(spec)
    return;
end

spec = localRecognizeUnaryNative(expr, timeValue, "abs", "abs");
if ~isempty(spec)
    return;
end

spec = localRecognizeUnaryNative(expr, timeValue, "atan", "atan");
if ~isempty(spec)
    return;
end

spec = localRecognizeUnaryNative(expr, timeValue, "exp", "exp");
if ~isempty(spec)
    return;
end

spec = localRecognizeUnaryNative(expr, timeValue, "log", "log");
if ~isempty(spec)
    return;
end

spec = localRecognizeUnaryNative(expr, timeValue, "sqrt", "sqrt");
if ~isempty(spec)
    return;
end

spec = localRecognizeSqrtPower(expr, timeValue);
if ~isempty(spec)
    return;
end

spec = localRecognizeSaturation(expr, timeValue, numberToken);
if ~isempty(spec)
    return;
end

spec = localRecognizeDeadZone(expr, timeValue, numberToken);
if ~isempty(spec)
    return;
end

spec = localRecognizeMinMax(expr, timeValue);
if ~isempty(spec)
    return;
end

spec = localRecognizeAtan2(expr, timeValue);
end

function spec = localRecognizeTime(expr, timeValue)
spec = [];
if strcmp(localStripOuterParens(expr), timeValue)
    spec = struct("kind", "time");
end
end

function spec = localRecognizeNumericConstant(expr, numberToken)
spec = [];
if ~isempty(regexp(expr, ['^' numberToken '$'], "once"))
    spec = struct("kind", "constant", "value", localNumericTokenToDouble(expr));
end
end

function spec = localRecognizeAffineStep(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^(?<amp>' numberToken ')\*heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<num>' numberToken ')\*heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<leading_bias>' numberToken ')(?<join>[+-])(?:(?<amp>' numberToken ')\*)?heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)$'], ...
    ['^(?<leading_bias>' numberToken ')(?<join>[+-])heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')$'], ...
    ['^(?<leading_bias>' numberToken ')(?<join>[+-])(?<num>' numberToken ')\*heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')$'] ...
};

match = [];
for index = 1:numel(patterns)
    current = regexp(expr, patterns{index}, "names");
    if isempty(current)
        continue;
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
elseif isfield(match, "num") && ~isempty(match.num) && isfield(match, "den") && ~isempty(match.den)
    amplitude = localNumericTokenToDouble(match.num) / localNumericTokenToDouble(match.den);
elseif isfield(match, "den") && ~isempty(match.den)
    amplitude = 1.0 / localNumericTokenToDouble(match.den);
end
if isfield(match, "join") && ~isempty(match.join) && match.join == '-'
    amplitude = -amplitude;
end

stepTime = 0.0;
if isfield(match, "offset") && ~isempty(match.offset)
    offset = localNumericTokenToDouble(match.offset);
    stepTime = -offset;
end

bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
elseif isfield(match, "leading_bias") && ~isempty(match.leading_bias)
    bias = localNumericTokenToDouble(match.leading_bias);
end

spec = struct("kind", "step", "step_time", stepTime, "bias", bias, "amplitude", amplitude);
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
    ['^(?:(?<amp>' numberToken ')\*)?(?<fn>sin|cos)\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<fn>sin|cos)\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*(?<fn>sin|cos)\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<fn>sin|cos)\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'] ...
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
frequency = 1.0;
if isfield(match, "freq") && ~isempty(match.freq)
    frequency = localNumericTokenToDouble(match.freq);
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
    "frequency", frequency, ...
    "phase", phase, ...
    "bias", bias);
end

function spec = localRecognizeSquare(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^(?:(?<amp>' numberToken ')\*)?sign\(sin\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sign\(sin\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*sign\(sin\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\(sign\(sin\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'] ...
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
frequency = 1.0;
if isfield(match, "freq") && ~isempty(match.freq)
    frequency = localNumericTokenToDouble(match.freq);
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end

spec = struct( ...
    "kind", "square", ...
    "amplitude", amplitude, ...
    "frequency", frequency, ...
    "phase", phase, ...
    "bias", bias);
end

function spec = localRecognizeRepeatingSequence(expr, timeToken, numberToken)
spec = [];
patterns = { ...
    ['^(?<amp>' numberToken ')\*sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\(sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<amp>' numberToken ')\*sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\((?<num>' numberToken ')\*sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^\(sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?,(?<width>' numberToken ')\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^sawtooth\((?:(?<freq>' numberToken ')\*)?' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'] ...
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
frequency = 1.0;
if isfield(match, "freq") && ~isempty(match.freq)
    frequency = localNumericTokenToDouble(match.freq);
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
    "frequency", frequency, ...
    "phase", phase, ...
    "bias", bias, ...
    "width", width);
end

function spec = localRecognizeSaturation(expr, timeValue, numberToken)
spec = [];

[innerExpr, lowerToken, upperToken] = localRecognizeSaturationTokens(expr, numberToken);
if isempty(innerExpr)
    return;
end
innerExpr = localStripOuterParens(innerExpr);
if strcmp(innerExpr, localStripOuterParens(expr))
    return;
end

innerSpec = simucopilot.internal.recognizeExpressionInputSpec(innerExpr, timeValue);
if isempty(innerSpec)
    return;
end

spec = struct( ...
    "kind", "saturation", ...
    "input", innerSpec, ...
    "lower_limit", localNumericTokenToDouble(lowerToken), ...
    "upper_limit", localNumericTokenToDouble(upperToken));
end

function [innerExpr, lowerToken, upperToken] = localRecognizeSaturationTokens(expr, numberToken)
innerExpr = "";
lowerToken = "";
upperToken = "";

cleanPatterns = { ...
    ['^min\(max\((?<inner>.+),(?<lower>' numberToken ')\),(?<upper>' numberToken ')\)$'], ...
    ['^min\((?<upper>' numberToken '),max\((?<inner>.+),(?<lower>' numberToken ')\)\)$'], ...
    ['^max\(min\((?<inner>.+),(?<upper>' numberToken ')\),(?<lower>' numberToken ')\)$'], ...
    ['^max\((?<lower>' numberToken '),min\((?<inner>.+),(?<upper>' numberToken ')\)\)$'] ...
};

for index = 1:numel(cleanPatterns)
    match = regexp(expr, cleanPatterns{index}, "names");
    if isempty(match)
        continue;
    end
    innerExpr = localStripOuterParens(match.inner);
    lowerToken = string(match.lower);
    upperToken = string(match.upper);
    return;
end

outerArgs = localParseFunctionArgs(expr, "min");
if isempty(outerArgs)
    return;
end
outerVector = strtrim(outerArgs{1});
if strlength(string(outerVector)) < 2 || outerVector(1) ~= '[' || outerVector(end) ~= ']'
    return;
end
outerItems = localSplitTopLevel(outerVector(2:end-1));
if numel(outerItems) ~= 2
    return;
end
upperCandidate = outerItems{1};
innerMaxExpr = outerItems{2};
if isempty(regexp(upperCandidate, ['^' numberToken '$'], "once"))
    return;
end

innerArgs = localParseFunctionArgs(innerMaxExpr, "max");
if isempty(innerArgs)
    return;
end
innerVector = strtrim(innerArgs{1});
if strlength(string(innerVector)) < 2 || innerVector(1) ~= '[' || innerVector(end) ~= ']'
    return;
end
innerItems = localSplitTopLevel(innerVector(2:end-1));
if numel(innerItems) ~= 2
    return;
end
lowerCandidate = innerItems{1};
if isempty(regexp(lowerCandidate, ['^' numberToken '$'], "once"))
    return;
end

innerExpr = localStripOuterParens(innerItems{2});
lowerToken = string(lowerCandidate);
upperToken = string(upperCandidate);
end

function spec = localRecognizeDeadZone(expr, timeValue, numberToken)
spec = [];

[innerExpr, lowerValue, upperValue] = localRecognizeDeadZoneTokens(expr, numberToken);
if isempty(innerExpr)
    return;
end
innerExpr = localStripOuterParens(innerExpr);
if strcmp(innerExpr, localStripOuterParens(expr))
    return;
end

innerSpec = simucopilot.internal.recognizeExpressionInputSpec(innerExpr, timeValue);
if isempty(innerSpec)
    return;
end

spec = struct( ...
    "kind", "dead_zone", ...
    "input", innerSpec, ...
    "lower_limit", lowerValue, ...
    "upper_limit", upperValue);
end

function spec = localRecognizeUnaryNative(expr, timeValue, functionName, kindName)
spec = [];
args = localParseFunctionArgs(expr, functionName);
if isempty(args) || numel(args) ~= 1
    return;
end
innerSpec = simucopilot.internal.recognizeExpressionInputSpec(args{1}, timeValue);
if isempty(innerSpec)
    innerSpec = localRecognizeAffineTime(args{1}, timeValue);
end
if isempty(innerSpec)
    return;
end
spec = struct("kind", kindName, "input", innerSpec);
end

function spec = localRecognizeMinMax(expr, timeValue)
spec = [];
functionNames = {"min", "max"};
for index = 1:numel(functionNames)
    functionName = functionNames{index};
    args = localParseFunctionArgs(expr, functionName);
    if isempty(args)
        continue;
    end
    if numel(args) == 1 || localLooksLikeSymbolicVectorMinMax(args)
        vectorExpr = strtrim(args{1});
        if strlength(string(vectorExpr)) >= 2 && vectorExpr(1) == '[' && vectorExpr(end) == ']'
            args = localSplitTopLevel(vectorExpr(2:end-1));
        end
    end
    if numel(args) ~= 2
        continue;
    end
    inputASpec = simucopilot.internal.recognizeExpressionInputSpec(args{1}, timeValue);
    inputBSpec = simucopilot.internal.recognizeExpressionInputSpec(args{2}, timeValue);
    if isempty(inputASpec) || isempty(inputBSpec)
        continue;
    end
    spec = struct( ...
        "kind", "minmax", ...
        "function", functionName, ...
        "input_a", inputASpec, ...
        "input_b", inputBSpec);
    return;
end
end

function spec = localRecognizeAtan2(expr, timeValue)
spec = [];
args = localParseFunctionArgs(expr, "atan2");
if ~isempty(args) && numel(args) == 2
    inputASpec = simucopilot.internal.recognizeExpressionInputSpec(args{1}, timeValue);
    inputBSpec = simucopilot.internal.recognizeExpressionInputSpec(args{2}, timeValue);
    if isempty(inputASpec)
        inputASpec = localRecognizeAffineTime(args{1}, timeValue);
    end
    if isempty(inputBSpec)
        inputBSpec = localRecognizeAffineTime(args{2}, timeValue);
    end
    if ~isempty(inputASpec) && ~isempty(inputBSpec)
        spec = struct( ...
            "kind", "atan2", ...
            "input_a", inputASpec, ...
            "input_b", inputBSpec);
        return;
    end
end

spec = localRecognizeAngleAtan2(expr, timeValue);
end

function spec = localRecognizeAffineTime(expr, timeValue)
spec = [];
timeExpr = localStripOuterParens(timeValue);
expr = localStripOuterParens(expr);
if isempty(timeExpr) || strcmp(expr, timeExpr)
    return;
end
try
    tSym = sym(timeExpr);
    exprSym = str2sym(expr);
    if any(~strcmp(string(symvar(exprSym)), string(tSym)))
        return;
    end
    gainExpr = simplify(diff(exprSym, tSym));
    if ~isempty(symvar(gainExpr))
        return;
    end
    gainValue = double(gainExpr);
    biasExpr = simplify(subs(exprSym, tSym, 0));
    if ~isempty(symvar(biasExpr))
        return;
    end
    biasValue = double(biasExpr);
    residual = simplify(exprSym - (sym(gainValue) * tSym + sym(biasValue)));
    if ~isempty(symvar(residual)) || abs(double(residual)) > 1e-12
        return;
    end
catch
    return;
end

if abs(gainValue - 1.0) <= 1e-12 && abs(biasValue) <= 1e-12
    return;
end

spec = struct( ...
    "kind", "affine", ...
    "input", struct("kind", "time"), ...
    "gain", gainValue, ...
    "bias", biasValue);
end

function spec = localRecognizeSqrtPower(expr, timeValue)
spec = [];

match = regexp(localStripOuterParens(expr), '^(?<inner>.+)\^\((?<exp>1/2|0\.5)\)$', "names");
if isempty(match)
    return;
end

innerSpec = simucopilot.internal.recognizeExpressionInputSpec(match.inner, timeValue);
if isempty(innerSpec)
    innerSpec = localRecognizeAffineTime(match.inner, timeValue);
end
if isempty(innerSpec)
    return;
end

spec = struct("kind", "sqrt", "input", innerSpec);
end

function spec = localRecognizeAngleAtan2(expr, timeValue)
spec = [];
args = localParseFunctionArgs(expr, "angle");
if isempty(args) || numel(args) ~= 1
    return;
end

try
    assumedRealTime = sym(timeValue, "real");
    rawTime = sym(timeValue);
    complexSym = subs(str2sym(args{1}), rawTime, assumedRealTime);
    realExpr = char(formula(simplify(real(complexSym))));
    imagExpr = char(formula(simplify(imag(complexSym))));
catch
    return;
end

if isempty(strtrim(realExpr)) || isempty(strtrim(imagExpr))
    return;
end

inputASpec = simucopilot.internal.recognizeExpressionInputSpec(imagExpr, timeValue);
inputBSpec = simucopilot.internal.recognizeExpressionInputSpec(realExpr, timeValue);
if isempty(inputASpec)
    inputASpec = localRecognizeAffineTime(imagExpr, timeValue);
end
if isempty(inputBSpec)
    inputBSpec = localRecognizeAffineTime(realExpr, timeValue);
end
if isempty(inputASpec) || isempty(inputBSpec)
    return;
end

spec = struct( ...
    "kind", "atan2", ...
    "input_a", inputASpec, ...
    "input_b", inputBSpec);
end

function tf = localLooksLikeSymbolicVectorMinMax(args)
tf = false;
if numel(args) < 3
    return;
end
vectorExpr = strtrim(args{1});
secondArg = localStripOuterParens(args{2});
thirdArg = localStripOuterParens(args{3});
if ~(strlength(string(vectorExpr)) >= 2 && vectorExpr(1) == '[' && vectorExpr(end) == ']')
    return;
end
if ~(strcmp(secondArg, "[]") || isempty(secondArg))
    return;
end
tf = strcmp(thirdArg, "2");
end

function [innerExpr, lowerValue, upperValue] = localRecognizeDeadZoneTokens(expr, numberToken)
innerExpr = "";
lowerValue = [];
upperValue = [];

args = localParseFunctionArgs(expr, "piecewise");
if isempty(args)
    return;
end

if numel(args) == 3
    [cond1, value1, ok1] = localParsePiecewiseTuple(args{1});
    [cond2, value2, ok2] = localParsePiecewiseTuple(args{2});
    [cond3, value3, ok3] = localParsePiecewiseTuple(args{3});
    if ~(ok1 && ok2 && ok3)
        return;
    end
    [innerExpr, lowerValue, upperValue] = localMatchDeadZoneBranches(cond1, value1, cond2, value2, cond3, value3, numberToken);
    return;
end

if numel(args) == 5
    [innerExpr, lowerValue, upperValue] = localMatchDeadZoneBranches(args{1}, args{2}, args{3}, args{4}, "symtrue", args{5}, numberToken);
    return;
end

if numel(args) == 6
    [innerExpr, lowerValue, upperValue] = localMatchDeadZoneBranches(args{1}, args{2}, args{3}, args{4}, args{5}, args{6}, numberToken);
end
end

function [condText, valueText, ok] = localParsePiecewiseTuple(tupleExpr)
ok = false;
condText = "";
valueText = "";
inner = localStripOuterParens(tupleExpr);
parts = localSplitTopLevel(inner);
if numel(parts) ~= 2
    return;
end
valueText = parts{1};
condText = parts{2};
ok = true;
end

function [innerExpr, lowerValue, upperValue] = localMatchDeadZoneBranches(cond1, value1, cond2, value2, cond3, value3, numberToken)
innerExpr = "";
lowerValue = [];
upperValue = [];

zeroValue = str2double(value1);
if ~(~isnan(zeroValue) && abs(zeroValue) <= 1e-12)
    return;
end

[innerFromAbs, widthToken] = localMatchAbsLess(cond1, numberToken);
if isempty(innerFromAbs)
    return;
end

[innerFromUpper, upperToken] = localMatchGreaterThan(cond2, numberToken);
if isempty(innerFromUpper) || ~strcmp(innerFromUpper, innerFromAbs)
    return;
end

[innerFromPositive, positiveToken] = localMatchSubtractConstant(value2, numberToken);
if isempty(innerFromPositive) || ~strcmp(innerFromPositive, innerFromAbs)
    return;
end

if ~strcmpi(cond3, "symtrue") && ~strcmpi(cond3, "true")
    return;
end

[innerFromNegative, negativeToken] = localMatchAddConstant(value3, numberToken);
if isempty(innerFromNegative) || ~strcmp(innerFromNegative, innerFromAbs)
    return;
end

widthValue = localNumericTokenToDouble(widthToken);
upperValueCandidate = localNumericTokenToDouble(upperToken);
positiveValue = localNumericTokenToDouble(positiveToken);
negativeValue = localNumericTokenToDouble(negativeToken);

if abs(widthValue - upperValueCandidate) > 1e-12 || ...
        abs(widthValue - positiveValue) > 1e-12 || ...
        abs(widthValue - negativeValue) > 1e-12
    return;
end

innerExpr = localStripOuterParens(innerFromAbs);
lowerValue = -widthValue;
upperValue = widthValue;
end

function [innerExpr, limitToken] = localMatchAbsLess(condExpr, numberToken)
innerExpr = "";
limitToken = "";
patterns = { ...
    ['^abs\((?<inner>.+)\)<(?<limit>' numberToken ')$'], ...
    ['^(?<limit>' numberToken ')>abs\((?<inner>.+)\)$'] ...
};
for index = 1:numel(patterns)
    match = regexp(condExpr, patterns{index}, "names");
    if isempty(match)
        continue;
    end
    innerExpr = localStripOuterParens(match.inner);
    limitToken = string(match.limit);
    return;
end
end

function [innerExpr, limitToken] = localMatchGreaterThan(expr, numberToken)
innerExpr = "";
limitToken = "";
patterns = { ...
    ['^(?<inner>.+)>(?<limit>' numberToken ')$'], ...
    ['^(?<limit>' numberToken ')<(?<inner>.+)$'] ...
};
for index = 1:numel(patterns)
    match = regexp(expr, patterns{index}, "names");
    if isempty(match)
        continue;
    end
    innerExpr = localStripOuterParens(match.inner);
    limitToken = string(match.limit);
    return;
end
end

function [innerExpr, limitToken] = localMatchSubtractConstant(expr, numberToken)
innerExpr = "";
limitToken = "";
match = regexp(expr, ['^(?<inner>.+)-(?<limit>' numberToken ')$'], "names");
if isempty(match)
    return;
end
innerExpr = localStripOuterParens(match.inner);
limitToken = string(match.limit);
end

function [innerExpr, limitToken] = localMatchAddConstant(expr, numberToken)
innerExpr = "";
limitToken = "";
match = regexp(expr, ['^(?<inner>.+)\+(?<limit>' numberToken ')$'], "names");
if isempty(match)
    return;
end
innerExpr = localStripOuterParens(match.inner);
limitToken = string(match.limit);
end

function args = localParseFunctionArgs(expr, functionName)
args = {};
prefix = functionName + "(";
if ~startsWith(string(expr), prefix) || ~endsWith(string(expr), ")")
    return;
end
inner = extractBetween(string(expr), strlength(prefix) + 1, strlength(string(expr)) - 1);
if isempty(inner)
    return;
end
args = localSplitTopLevel(char(inner));
end

function parts = localSplitTopLevel(expr)
parts = {};
depthParen = 0;
depthBracket = 0;
tokenStart = 1;
expr = char(string(expr));
for index = 1:strlength(string(expr))
    ch = expr(index);
    switch ch
        case '('
            depthParen = depthParen + 1;
        case ')'
            depthParen = depthParen - 1;
        case '['
            depthBracket = depthBracket + 1;
        case ']'
            depthBracket = depthBracket - 1;
        case ','
            if depthParen == 0 && depthBracket == 0
                parts{end + 1} = expr(tokenStart:index-1); %#ok<AGROW>
                tokenStart = index + 1;
            end
    end
end
parts{end + 1} = expr(tokenStart:end);
parts = cellfun(@(item) localStripOuterParens(strtrim(item)), parts, "UniformOutput", false);
end

function value = localStripOuterParens(expr)
value = strtrim(char(string(expr)));
while strlength(string(value)) >= 2 && value(1) == '(' && value(end) == ')'
    depth = 0;
    balanced = true;
    for index = 1:numel(value)
        if value(index) == '('
            depth = depth + 1;
        elseif value(index) == ')'
            depth = depth - 1;
            if depth == 0 && index < numel(value)
                balanced = false;
                break;
            end
        end
    end
    if ~balanced || depth ~= 0
        break;
    end
    value = strtrim(value(2:end-1));
end
end

function pattern = localNumberPattern()
pattern = '[-+]?(?:[0-9]*\.?[0-9]+|[0-9]+/[0-9]+)';
end

function value = localNumericTokenToDouble(token)
value = double(vpa(str2sym(char(string(token)))));
end
