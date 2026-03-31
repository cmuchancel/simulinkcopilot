function out = generateNativeExplicitOde(primaryInput, sourceType, opts, invocation, callerWorkspace, nativePreview)
% generateNativeExplicitOde Build a native MATLAB/Simulink explicit-ODE model and compare it to MATLAB and Python oracles.

nativeModelName = localResolvedModelName(opts.ModelName);
parityMode = localInvocationParityMode(invocation);
timing = struct( ...
    "native_build_sec", 0.0, ...
    "native_simulation_sec", 0.0, ...
    "matlab_reference_sec", 0.0, ...
    "python_parity_sec", 0.0 ...
);
outputDir = localResolvedOutputDir(opts);
stateNames = localOrderedCell(nativePreview.FirstOrderPreview, "States");
modelConfig = localDefaultModelConfig(opts);
oracleOut = struct();
oracleSourceFamilies = struct();
oracleSimulation = struct();

if strcmp(parityMode, "python")
    parityTimer = tic;
    oracleOpts = opts;
    oracleOpts.OpenModel = false;
    oracleOpts.ModelName = [nativeModelName '_python_oracle'];

    oracleRequest = simucopilot.internal.makeRequestStruct(sourceType, primaryInput, oracleOpts);
    oracleOut = simucopilot.internal.callBackend(oracleRequest, oracleOpts);

    stateNames = localOrderedCell(oracleOut.FirstOrder, "states");
    if isempty(stateNames)
        stateNames = localOrderedCell(nativePreview.FirstOrderPreview, "States");
    end

    modelConfig = localReadModelConfig(oracleOut.GeneratedModelPath, oracleOut.ModelName);
    oracleSourceFamilies = localSourceBlockFamiliesForModel(oracleOut.GeneratedModelPath, oracleOut.ModelName, localOrderedCell(nativePreview, "Inputs"));
    oracleSimulation = localSimulateModel(oracleOut.GeneratedModelPath, oracleOut.ModelName, stateNames);
    timing.python_parity_sec = toc(parityTimer);
end

buildTimer = tic;
nativeBuild = localBuildNativeModel( ...
    nativeModelName, ...
    outputDir, ...
    nativePreview, ...
    opts, ...
    callerWorkspace, ...
    stateNames, ...
    modelConfig);
timing.native_build_sec = toc(buildTimer);

simulationTimer = tic;
nativeSimulation = localSimulateModel(nativeBuild.GeneratedModelPath, nativeBuild.ModelName, stateNames);
timing.native_simulation_sec = toc(simulationTimer);

referenceTimer = tic;
matlabReference = localBuildMatlabReferenceSimulation( ...
    nativePreview, ...
    opts, ...
    stateNames, ...
    modelConfig);
timing.matlab_reference_sec = toc(referenceTimer);

tolerance = localResolvedTolerance(opts);
nativeVsMatlab = localCompareSimulations(matlabReference, nativeSimulation, tolerance);
if strcmp(parityMode, "python")
    pythonVsMatlab = localCompareSimulations(matlabReference, oracleSimulation, tolerance);
    nativeVsPython = localCompareSimulations(oracleSimulation, nativeSimulation, tolerance);
    oracleValidationPasses = localOracleValidationPasses(oracleOut.Validation);
    nativeValidation = struct( ...
        "passes", logical(nativeVsMatlab.passes) && logical(pythonVsMatlab.passes) && logical(nativeVsPython.passes), ...
        "reference_kind", "matlab_ode", ...
        "reference_solver", matlabReference.reference_solver, ...
        "native_vs_matlab_reference", nativeVsMatlab, ...
        "python_vs_matlab_reference", pythonVsMatlab, ...
        "native_vs_python_delegate", nativeVsPython, ...
        "vs_python_delegate", nativeVsPython, ...
        "surface_passes", struct( ...
            "native_vs_matlab_reference", logical(nativeVsMatlab.passes), ...
            "python_vs_matlab_reference", logical(pythonVsMatlab.passes), ...
            "native_vs_python_delegate", logical(nativeVsPython.passes)), ...
        "oracle_validation_passes", oracleValidationPasses ...
    );

    parityReport = matlabv2native.internal.comparePreviewToProblem(nativePreview, oracleOut);
    parityReport = localAugmentParityReport( ...
        parityReport, ...
        nativeBuild.SourceBlockFamilies, ...
        oracleSourceFamilies, ...
        matlabReference, ...
        nativeVsMatlab, ...
        pythonVsMatlab, ...
        nativeVsPython, ...
        nativeValidation, ...
        oracleOut.Validation);
    backendKind = "native_with_python_parity";
    normalizedProblem = oracleOut.NormalizedProblem;
    firstOrder = oracleOut.FirstOrder;
else
    nativeValidation = struct( ...
        "passes", logical(nativeVsMatlab.passes), ...
        "reference_kind", "matlab_ode", ...
        "reference_solver", matlabReference.reference_solver, ...
        "native_vs_matlab_reference", nativeVsMatlab, ...
        "surface_passes", struct( ...
            "native_vs_matlab_reference", logical(nativeVsMatlab.passes)), ...
        "python_parity_available", false ...
    );
    parityReport = localRuntimeOnlyParityReport(nativePreview, nativeBuild.SourceBlockFamilies, matlabReference, nativeValidation);
    backendKind = "native_runtime_only";
    normalizedProblem = localNormalizedProblemFromPreview(nativePreview);
    firstOrder = localFirstOrderFromPreview(nativePreview);
end

out = struct();
out.Api = "matlabv2native";
out.BackendKind = backendKind;
out.SourceType = sourceType;
out.Invocation = invocation;
out.NativePreview = nativePreview;
out.PublicOptions = localPublicOptions(opts);
out.Route = char(string(localScalar(nativePreview, "Route", "explicit_ode")));
out.GeneratedModelPath = nativeBuild.GeneratedModelPath;
out.ModelName = nativeBuild.ModelName;
out.Validation = nativeValidation;
out.ParityReport = parityReport;
out.NormalizedProblem = normalizedProblem;
out.FirstOrder = firstOrder;
out.NativeSimulation = nativeSimulation;
out.PythonOracleSimulation = oracleSimulation;
out.MatlabReferenceSimulation = matlabReference;
out.PythonOracle = oracleOut;
out.SourceBlockFamilies = nativeBuild.SourceBlockFamilies;
out.OracleSourceBlockFamilies = oracleSourceFamilies;
out.Timing = timing;

if opts.OpenModel
    open_system(out.GeneratedModelPath);
end
end

function build = localBuildNativeModel(modelName, outputDir, preview, opts, callerWorkspace, stateNames, oracleConfig)
load_system("simulink");
if bdIsLoaded(modelName)
    close_system(modelName, 0);
end
new_system(modelName);
cleanupModel = onCleanup(@() localBestEffortClose(modelName));

localApplyModelConfig(modelName, oracleConfig);

stateNames = reshape(stateNames, 1, []);
inputNames = localOrderedCell(preview, "Inputs");
parameterNames = localOrderedCell(preview, "Parameters");
timeVariable = char(string(localScalar(preview, "TimeVariable", "t")));
initialConditions = localStruct(opts.RuntimeOverride, "initial_conditions");
parameterValues = localStruct(opts.RuntimeOverride, "parameter_values");
inputValues = localStruct(opts.RuntimeOverride, "input_values");
inputSpecs = localStruct(opts.RuntimeOverride, "input_specs");
nativeRhsStyle = localResolvedNativeRhsStyle(opts);

positions = localLayoutPlan(numel(inputNames), numel(parameterNames), numel(stateNames));
signalSources = struct();

for index = 1:numel(stateNames)
    stateName = stateNames{index};
    blockName = ['int_' localSanitize(stateName)];
    blockPath = [modelName '/' blockName];
    add_block("simulink/Continuous/Integrator", blockPath, ...
        "Position", positions.integrators(index, :), ...
        "InitialCondition", localNumericString(localScalar(initialConditions, stateName, 0)));
    signalSources.(stateName) = [blockName '/1'];
end

for index = 1:numel(parameterNames)
    parameterName = parameterNames{index};
    blockPath = [modelName '/' parameterName];
    add_block("simulink/Sources/Constant", blockPath, ...
        "Value", localNumericString(localScalar(parameterValues, parameterName, 0)), ...
        "Position", positions.parameters(index, :));
    signalSources.(parameterName) = [parameterName '/1'];
end

clockBlockName = '';
clockSignal = '';
inputFamilies = struct();
for index = 1:numel(inputNames)
    inputName = inputNames{index};
    inputPlacement = positions.inputs(index, :);
    [signalPort, family, clockBlockName, clockSignal] = localAddInputSource( ...
        modelName, ...
        inputName, ...
        inputPlacement, ...
        inputValues, ...
        inputSpecs, ...
        signalSources, ...
        parameterNames, ...
        stateNames, ...
        timeVariable, ...
        oracleConfig, ...
        clockBlockName, ...
        clockSignal);
    signalSources.(inputName) = signalPort;
    inputFamilies.(inputName) = family;
end

stateEquations = preview.FirstOrderPreview.StateEquations;
deferredBlocks = struct("state", {}, "block_name", {}, "dependencies", {});
for index = 1:numel(stateEquations)
    stateName = char(string(stateEquations(index).state));
    rhsText = strtrim(char(string(stateEquations(index).rhs)));
    targetPort = ['int_' localSanitize(stateName) '/1'];
    directPort = localDirectSignalPort(rhsText, signalSources);
    if ~isempty(directPort)
        add_line(modelName, directPort, targetPort, "autorouting", "on");
        continue;
    end
    numericValue = str2double(rhsText);
    if ~isnan(numericValue)
        constName = ['rhs_const_' localSanitize(stateName)];
        add_block("simulink/Sources/Constant", [modelName '/' constName], ...
            "Value", localNumericString(numericValue), ...
            "Position", positions.rhs(index, :));
        add_line(modelName, [constName '/1'], targetPort, "autorouting", "on");
        continue;
    end
    [nativeRhsPort, clockBlockName, clockSignal] = localNativeSignalPlusTimeRhsPort( ...
        modelName, ...
        stateName, ...
        rhsText, ...
        positions.rhs(index, :), ...
        signalSources, ...
        stateNames, ...
        inputNames, ...
        parameterNames, ...
        timeVariable, ...
        oracleConfig, ...
        clockBlockName, ...
        clockSignal);
    if ~isempty(nativeRhsPort)
        add_line(modelName, nativeRhsPort, targetPort, "autorouting", "on");
        continue;
    end

    nativeRhsPort = localNativeAffineRhsPort( ...
        modelName, ...
        stateName, ...
        rhsText, ...
        positions.rhs(index, :), ...
        signalSources, ...
        stateNames, ...
        inputNames, ...
        parameterNames);
    if ~isempty(nativeRhsPort)
        add_line(modelName, nativeRhsPort, targetPort, "autorouting", "on");
        continue;
    end

    [nativeRhsPort, ~, clockBlockName, clockSignal] = localNativeTimeExpressionRhsPort( ...
        modelName, ...
        stateName, ...
        rhsText, ...
        positions.rhs(index, :), ...
        timeVariable, ...
        oracleConfig, ...
        clockBlockName, ...
        clockSignal);
    if ~isempty(nativeRhsPort)
        add_line(modelName, nativeRhsPort, targetPort, "autorouting", "on");
        continue;
    end

    [nativeRhsPort, clockBlockName, clockSignal] = localNativeRecursiveRhsPort( ...
        modelName, ...
        stateName, ...
        rhsText, ...
        positions.rhs(index, :), ...
        signalSources, ...
        localExpressionDependencies(rhsText, stateNames, inputNames, parameterNames, timeVariable), ...
        nativeRhsStyle, ...
        timeVariable, ...
        oracleConfig, ...
        clockBlockName, ...
        clockSignal);
    if ~isempty(nativeRhsPort)
        add_line(modelName, nativeRhsPort, targetPort, "autorouting", "on");
        continue;
    end

    blockName = ['rhs_' localSanitize(stateName)];
    blockPath = [modelName '/' blockName];
    add_block("simulink/User-Defined Functions/MATLAB Function", blockPath, ...
        "Position", positions.rhs(index, :));
    dependencies = localExpressionDependencies(rhsText, stateNames, inputNames, parameterNames, timeVariable);
    localSetMatlabFunctionScript(blockPath, blockName, dependencies, rhsText, "rhs");
    deferredBlocks(end + 1) = struct("state", stateName, "block_name", blockName, "dependencies", {dependencies}); %#ok<AGROW>
end

set_param(modelName, "SimulationCommand", "Update");

if isempty(clockSignal) && localDeferredBlocksNeedClock(deferredBlocks, timeVariable)
    [clockBlockName, clockSignal] = localEnsureClock(modelName, clockBlockName, clockSignal); %#ok<NASGU>
end

for index = 1:numel(deferredBlocks)
    blockName = deferredBlocks(index).block_name;
    dependencies = deferredBlocks(index).dependencies;
    for portIndex = 1:numel(dependencies)
        dependency = dependencies{portIndex};
        dependencyPort = localSignalPortForDependency(dependency, signalSources, clockSignal, timeVariable);
        add_line(modelName, dependencyPort, [blockName '/' num2str(portIndex)], "autorouting", "on");
    end
    add_line(modelName, [blockName '/1'], ['int_' localSanitize(deferredBlocks(index).state) '/1'], "autorouting", "on");
end

for index = 1:numel(stateNames)
    stateName = stateNames{index};
    outName = ['out_' localSanitize(stateName)];
    add_block("simulink/Sinks/Out1", [modelName '/' outName], ...
        "Position", positions.outputs(index, :), ...
        "Port", num2str(index));
    add_line(modelName, ['int_' localSanitize(stateName) '/1'], [outName '/1'], "autorouting", "on");
end

if ~isfolder(outputDir)
    mkdir(outputDir);
end
generatedModelPath = fullfile(outputDir, [modelName '.slx']);
save_system(modelName, generatedModelPath);
clear cleanupModel
close_system(modelName, 0);

build = struct( ...
    "ModelName", modelName, ...
    "GeneratedModelPath", generatedModelPath, ...
    "SourceBlockFamilies", inputFamilies ...
);
end

function [signalPort, family, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, inputName, position, inputValues, inputSpecs, signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal)

if isfield(inputValues, inputName)
    add_block("simulink/Sources/Constant", [modelName '/' inputName], ...
        "Value", localNumericString(localScalar(inputValues, inputName, 0)), ...
        "Position", position);
    signalPort = [inputName '/1'];
    family = "Constant";
    return;
end

spec = [];
if isfield(inputSpecs, inputName)
    spec = inputSpecs.(inputName);
end
[nativeKind, payload] = localClassifyInputSpec(spec, inputName, timeVariable, modelConfig);

switch nativeKind
    case "Constant"
        add_block("simulink/Sources/Constant", [modelName '/' inputName], ...
            "Value", localNumericString(payload.value), ...
            "Position", position);
        signalPort = [inputName '/1'];
        family = "Constant";
    case "Clock"
        [clockBlockName, clockSignal] = localEnsureClock(modelName, clockBlockName, clockSignal);
        signalPort = clockSignal;
        family = "Clock";
    case "Step"
        add_block("simulink/Sources/Step", [modelName '/' inputName], ...
            "Time", localNumericString(payload.step_time), ...
            "Before", localNumericString(payload.before), ...
            "After", localNumericString(payload.after), ...
            "Position", position);
        signalPort = [inputName '/1'];
        family = "Step";
    case "PulseGenerator"
        add_block("simulink/Sources/Pulse Generator", [modelName '/' inputName], ...
            "PulseType", "Time based", ...
            "Amplitude", localNumericString(payload.amplitude), ...
            "Period", localNumericString(payload.period), ...
            "PulseWidth", localNumericString((payload.width / payload.period) * 100.0), ...
            "PhaseDelay", localNumericString(payload.start_time), ...
            "Position", position);
        signalPort = [inputName '/1'];
        family = "PulseGenerator";
    case "Ramp"
        add_block("simulink/Sources/Ramp", [modelName '/' inputName], ...
            "slope", localNumericString(payload.slope), ...
            "start", localNumericString(payload.start_time), ...
            "InitialOutput", localNumericString(payload.initial_output), ...
            "Position", position);
        signalPort = [inputName '/1'];
        family = "Ramp";
    case "SineWave"
        add_block("simulink/Sources/Sine Wave", [modelName '/' inputName], ...
            "Amplitude", localNumericString(payload.amplitude), ...
            "Frequency", localNumericString(payload.frequency), ...
            "Phase", localNumericString(payload.phase), ...
            "Bias", localNumericString(payload.bias), ...
            "SampleTime", "0", ...
            "Position", position);
        signalPort = [inputName '/1'];
        family = "SineWave";
    case "SquareWave"
        [signalPort, family] = localAddSquareWaveSource(modelName, inputName, position, payload);
    case "RepeatingSequence"
        [signalPort, family] = localAddRepeatingSequenceSource(modelName, inputName, position, payload);
    case "Saturation"
        [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Discontinuities/Saturation", "Saturation", ...
            struct( ...
                "LowerLimit", localNumericString(payload.lower_limit), ...
                "UpperLimit", localNumericString(payload.upper_limit)), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "DeadZone"
        [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Discontinuities/Dead Zone", "DeadZone", ...
            struct( ...
                "LowerValue", localNumericString(payload.lower_limit), ...
                "UpperValue", localNumericString(payload.upper_limit)), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "Sign"
        [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Math Operations/Sign", "Sign", ...
            struct(), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "Abs"
        [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Math Operations/Abs", "Abs", ...
            struct(), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "MinMax"
        [signalPort, family, clockBlockName, clockSignal] = localAddBinaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Math Operations/MinMax", "MinMax", ...
            struct("Function", lower(char(string(payload.function))), "Inputs", "2"), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "Affine"
        [signalPort, family, clockBlockName, clockSignal] = localAddAffineInputSource( ...
            modelName, inputName, position, payload, ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "Atan"
        [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Math Operations/Trigonometric Function", "TrigonometricFunction", ...
            struct("Operator", "atan"), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "Atan2"
        [signalPort, family, clockBlockName, clockSignal] = localAddBinaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Math Operations/Trigonometric Function", "TrigonometricFunction", ...
            struct("Operator", "atan2"), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    case "MathFunction"
        [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
            modelName, inputName, position, payload, ...
            "simulink/Math Operations/Math Function", "MathFunction", ...
            struct("Operator", char(string(payload.operator))), ...
            signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
    otherwise
        [clockBlockName, clockSignal] = localEnsureClock(modelName, clockBlockName, clockSignal);
        add_block("simulink/User-Defined Functions/MATLAB Function", [modelName '/' inputName], ...
            "Position", position);
        dependencies = localExpressionDependencies(payload.expression, stateNames, {inputName}, parameterNames, timeVariable);
        dependencies = setdiff(dependencies, {inputName}, "stable");
        localSetMatlabFunctionScript([modelName '/' inputName], inputName, dependencies, payload.expression, "y");
        set_param(modelName, "SimulationCommand", "Update");
        for portIndex = 1:numel(dependencies)
            dependencyPort = localSignalPortForDependency(dependencies{portIndex}, signalSources, clockSignal, timeVariable);
            add_line(modelName, dependencyPort, [inputName '/' num2str(portIndex)], "autorouting", "on");
        end
        signalPort = [inputName '/1'];
        family = "MATLAB Function";
end
end

function [kind, payload] = localClassifyInputSpec(spec, inputName, timeVariable, modelConfig)
if isempty(spec)
    kind = "Constant";
    payload = struct("value", 0);
    return;
end

specKind = char(string(localScalar(spec, "kind", "expression")));
switch lower(specKind)
    case "constant"
        kind = "Constant";
        payload = struct("value", double(localScalar(spec, "value", 0)));
        return;
    case "time"
        kind = "Clock";
        payload = struct();
        return;
    case "step"
        bias = double(localScalar(spec, "bias", localScalar(spec, "initial_value", 0)));
        amplitude = double(localScalar(spec, "amplitude", localScalar(spec, "final_value", 1) - bias));
        kind = "Step";
        payload = struct( ...
            "step_time", double(localScalar(spec, "step_time", localScalar(spec, "start_time", 0))), ...
            "before", bias, ...
            "after", bias + amplitude ...
        );
        return;
    case "pulse"
        kind = "PulseGenerator";
        payload = struct( ...
            "amplitude", double(localScalar(spec, "amplitude", localScalar(spec, "value", 1))), ...
            "start_time", double(localScalar(spec, "start_time", 0)), ...
            "width", double(localScalar(spec, "width", 0.1)), ...
            "period", double(localScalar(spec, "period", localDefaultPulsePeriodFromSpan( ...
                double(localScalar(spec, "start_time", 0)), ...
                double(localScalar(spec, "width", 0.1)), ...
                localModelConfigSpan(modelConfig)))) ...
        );
        return;
    case "ramp"
        kind = "Ramp";
        payload = struct( ...
            "slope", double(localScalar(spec, "slope", 1)), ...
            "start_time", double(localScalar(spec, "start_time", 0)), ...
            "initial_output", double(localScalar(spec, "initial_output", 0)) ...
        );
        return;
    case "sine"
        kind = "SineWave";
        payload = struct( ...
            "amplitude", double(localScalar(spec, "amplitude", 1)), ...
            "frequency", double(localScalar(spec, "frequency", localScalar(spec, "omega", 1))), ...
            "phase", double(localScalar(spec, "phase", 0)), ...
            "bias", double(localScalar(spec, "bias", 0)) ...
        );
        return;
    case "square"
        kind = "SquareWave";
        payload = struct( ...
            "amplitude", double(localScalar(spec, "amplitude", 1)), ...
            "frequency", double(localScalar(spec, "frequency", localScalar(spec, "omega", 1))), ...
            "phase", double(localScalar(spec, "phase", 0)), ...
            "bias", double(localScalar(spec, "bias", 0)) ...
        );
        return;
    case {"sawtooth", "triangle"}
        widthDefault = 1.0;
        if strcmp(specKind, "triangle")
            widthDefault = 0.5;
        end
        kind = "RepeatingSequence";
        payload = struct( ...
            "waveform_kind", specKind, ...
            "amplitude", double(localScalar(spec, "amplitude", 1)), ...
            "frequency", double(localScalar(spec, "frequency", localScalar(spec, "omega", 1))), ...
            "phase", double(localScalar(spec, "phase", 0)), ...
            "bias", double(localScalar(spec, "bias", 0)), ...
            "width", double(localScalar(spec, "width", widthDefault)) ...
        );
        return;
    case "saturation"
        kind = "Saturation";
        payload = struct( ...
            "input_spec", localScalar(spec, "input", struct("kind", "time")), ...
            "lower_limit", double(localScalar(spec, "lower_limit", -1)), ...
            "upper_limit", double(localScalar(spec, "upper_limit", 1)) ...
        );
        return;
    case "dead_zone"
        kind = "DeadZone";
        payload = struct( ...
            "input_spec", localScalar(spec, "input", struct("kind", "time")), ...
            "lower_limit", double(localScalar(spec, "lower_limit", -1)), ...
            "upper_limit", double(localScalar(spec, "upper_limit", 1)) ...
        );
        return;
    case "sign"
        kind = "Sign";
        payload = struct("input_spec", localScalar(spec, "input", struct("kind", "time")));
        return;
    case "abs"
        kind = "Abs";
        payload = struct("input_spec", localScalar(spec, "input", struct("kind", "time")));
        return;
    case "minmax"
        kind = "MinMax";
        payload = struct( ...
            "function", char(string(localScalar(spec, "function", "max"))), ...
            "input_a", localScalar(spec, "input_a", struct("kind", "constant", "value", 0)), ...
            "input_b", localScalar(spec, "input_b", struct("kind", "constant", "value", 0)) ...
        );
        return;
    case "affine"
        kind = "Affine";
        payload = struct( ...
            "input_spec", localScalar(spec, "input", struct("kind", "time")), ...
            "gain", double(localScalar(spec, "gain", 1)), ...
            "bias", double(localScalar(spec, "bias", 0)) ...
        );
        return;
    case "atan"
        kind = "Atan";
        payload = struct("input_spec", localScalar(spec, "input", struct("kind", "time")));
        return;
    case "atan2"
        kind = "Atan2";
        payload = struct( ...
            "input_a", localScalar(spec, "input_a", struct("kind", "constant", "value", 0)), ...
            "input_b", localScalar(spec, "input_b", struct("kind", "constant", "value", 0)) ...
        );
        return;
    case {"exp", "log", "sqrt"}
        kind = "MathFunction";
        payload = struct( ...
            "operator", lower(specKind), ...
            "input_spec", localScalar(spec, "input", struct("kind", "time")) ...
        );
        return;
    case "expression"
        expression = char(string(localScalar(spec, "expression", "")));
        recognizedSpec = simucopilot.internal.recognizeExpressionInputSpec(expression, timeVariable);
        if ~isempty(recognizedSpec)
            [kind, payload] = localClassifyInputSpec(recognizedSpec, inputName, timeVariable, modelConfig);
            return;
        end
        [isStep, stepPayload] = localExpressionIsStep(expression, timeVariable);
        if isStep
            kind = "Step";
            payload = stepPayload;
            return;
        end
        [isPulse, pulsePayload] = localExpressionIsPulse(expression, timeVariable, localModelConfigSpan(modelConfig));
        if isPulse
            kind = "PulseGenerator";
            payload = pulsePayload;
            return;
        end
        [isRamp, rampPayload] = localExpressionIsRamp(expression, timeVariable);
        if isRamp
            kind = "Ramp";
            payload = rampPayload;
            return;
        end
        [isSine, sinePayload] = localExpressionIsSineWave(expression, timeVariable);
        if isSine
            kind = "SineWave";
            payload = sinePayload;
            return;
        end
        [isSquare, squarePayload] = localExpressionIsSquareWave(expression, timeVariable);
        if isSquare
            kind = "SquareWave";
            payload = squarePayload;
            return;
        end
        [isRepeating, repeatingPayload] = localExpressionIsRepeatingSequenceWave(expression, timeVariable);
        if isRepeating
            kind = "RepeatingSequence";
            payload = repeatingPayload;
            return;
        end
        numericValue = str2double(strtrim(expression));
        if ~isnan(numericValue)
            kind = "Constant";
            payload = struct("value", numericValue);
            return;
        end
        kind = "MATLAB Function";
        payload = struct("expression", expression, "input_name", inputName);
        return;
    otherwise
        kind = "MATLAB Function";
        payload = struct("expression", char(string(localScalar(spec, "expression", specKind))), "input_name", inputName);
end
end

function [signalPort, family] = localAddSquareWaveSource(modelName, inputName, position, payload)
sourceName = [inputName '_src'];
signName = [inputName '_sign'];

add_block("simulink/Sources/Sine Wave", [modelName '/' sourceName], ...
    "Amplitude", "1", ...
    "Frequency", localNumericString(payload.frequency), ...
    "Phase", localNumericString(payload.phase), ...
    "Bias", "0", ...
    "SampleTime", "0", ...
    "Position", position);
add_block("simulink/Math Operations/Sign", [modelName '/' signName], ...
    "Position", position + [130 0 130 0]);
add_line(modelName, [sourceName '/1'], [signName '/1'], "autorouting", "on");

currentPort = [signName '/1'];
if abs(payload.amplitude - 1.0) > 1e-12
    gainName = [inputName '_gain'];
    add_block("simulink/Math Operations/Gain", [modelName '/' gainName], ...
        "Gain", localNumericString(payload.amplitude), ...
        "Position", position + [260 0 260 0]);
    add_line(modelName, currentPort, [gainName '/1'], "autorouting", "on");
    currentPort = [gainName '/1'];
end

if abs(payload.bias) > 1e-12
    constName = [inputName '_bias'];
    sumName = inputName;
    add_block("simulink/Sources/Constant", [modelName '/' constName], ...
        "Value", localNumericString(payload.bias), ...
        "Position", position + [260 80 260 80]);
    add_block("simulink/Math Operations/Sum", [modelName '/' sumName], ...
        "Inputs", "++", ...
        "Position", position + [390 0 390 0]);
    add_line(modelName, currentPort, [sumName '/1'], "autorouting", "on");
    add_line(modelName, [constName '/1'], [sumName '/2'], "autorouting", "on");
    signalPort = [sumName '/1'];
else
    signalPort = currentPort;
end
family = "SquareWave";
end

function [signalPort, family] = localAddRepeatingSequenceSource(modelName, inputName, position, payload)
period = localPeriodicSourcePeriod(payload.frequency);
[times, values] = localRepeatingSequencePoints(period, payload.amplitude, payload.bias, payload.width);
sourceName = inputName;
if abs(payload.phase) > 1e-12
    sourceName = [inputName '_src'];
end

add_block("simulink/Sources/Repeating Sequence", [modelName '/' sourceName], ...
    "rep_seq_t", ['[' strjoin(cellfun(@localNumericString, num2cell(times), "UniformOutput", false), ' ') ']'], ...
    "rep_seq_y", ['[' strjoin(cellfun(@localNumericString, num2cell(values), "UniformOutput", false), ' ') ']'], ...
    "Position", position);

if abs(payload.phase) <= 1e-12
    signalPort = [sourceName '/1'];
    family = "RepeatingSequence";
    return;
end

delayName = inputName;
add_block("simulink/Continuous/Transport Delay", [modelName '/' delayName], ...
    "DelayTime", localNumericString(localPeriodicPhaseDelay(payload.frequency, payload.phase)), ...
    "InitialOutput", localNumericString(values(1)), ...
    "Position", position + [150 0 150 0]);
add_line(modelName, [sourceName '/1'], [delayName '/1'], "autorouting", "on");
signalPort = [delayName '/1'];
family = "RepeatingSequence";
end

function [signalPort, family, clockBlockName, clockSignal] = localAddUnaryNativeInputSource( ...
    modelName, inputName, position, payload, blockPath, familyName, params, ...
    signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal)

innerInputName = [inputName '_src'];
innerSpecs = struct();
innerSpecs.(innerInputName) = payload.input_spec;
innerPosition = position + [-140 0 -140 0];
[innerPort, ~, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, innerInputName, innerPosition, struct(), innerSpecs, signalSources, ...
    parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);

paramPairs = localStructNameValuePairs(params);
add_block(blockPath, [modelName '/' inputName], ...
    paramPairs{:}, ...
    "Position", position);
add_line(modelName, innerPort, [inputName '/1'], "autorouting", "on");
signalPort = [inputName '/1'];
family = familyName;
end

function [signalPort, family, clockBlockName, clockSignal] = localAddBinaryNativeInputSource( ...
    modelName, inputName, position, payload, blockPath, familyName, params, ...
    signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal)

inputAName = [inputName '_src1'];
inputBName = [inputName '_src2'];
inputSpecs = struct();
inputSpecs.(inputAName) = payload.input_a;
inputSpecs.(inputBName) = payload.input_b;

positionA = position + [-160 -40 -160 -40];
positionB = position + [-160 40 -160 40];
[inputAPort, ~, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, inputAName, positionA, struct(), inputSpecs, signalSources, ...
    parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);
[inputBPort, ~, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, inputBName, positionB, struct(), inputSpecs, signalSources, ...
    parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);

paramPairs = localStructNameValuePairs(params);
add_block(blockPath, [modelName '/' inputName], ...
    paramPairs{:}, ...
    "Position", position);
add_line(modelName, inputAPort, [inputName '/1'], "autorouting", "on");
add_line(modelName, inputBPort, [inputName '/2'], "autorouting", "on");
signalPort = [inputName '/1'];
family = familyName;
end

function [signalPort, family, clockBlockName, clockSignal] = localAddAffineInputSource( ...
    modelName, inputName, position, payload, ...
    signalSources, parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal)

innerInputName = [inputName '_src'];
innerSpecs = struct();
innerSpecs.(innerInputName) = payload.input_spec;
innerPosition = position + [-160 0 -160 0];
[currentPort, ~, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, innerInputName, innerPosition, struct(), innerSpecs, signalSources, ...
    parameterNames, stateNames, timeVariable, modelConfig, clockBlockName, clockSignal);

gainValue = double(payload.gain);
biasValue = double(payload.bias);

if abs(gainValue - 1.0) > 1e-12
    gainName = [inputName '_gain'];
    add_block("simulink/Math Operations/Gain", [modelName '/' gainName], ...
        "Gain", localNumericString(gainValue), ...
        "Position", position + [-20 0 -20 0]);
    add_line(modelName, currentPort, [gainName '/1'], "autorouting", "on");
    currentPort = [gainName '/1'];
end

if abs(biasValue) > 1e-12
    constName = [inputName '_bias'];
    add_block("simulink/Sources/Constant", [modelName '/' constName], ...
        "Value", localNumericString(biasValue), ...
        "Position", position + [-20 80 -20 80]);
    add_block("simulink/Math Operations/Sum", [modelName '/' inputName], ...
        "Inputs", "++", ...
        "Position", position);
    add_line(modelName, currentPort, [inputName '/1'], "autorouting", "on");
    add_line(modelName, [constName '/1'], [inputName '/2'], "autorouting", "on");
    signalPort = [inputName '/1'];
    family = "Affine";
    return;
end

if abs(gainValue - 1.0) > 1e-12
    signalPort = currentPort;
    family = "Affine";
    return;
end

signalPort = currentPort;
family = "Affine";
end

function [isStep, payload] = localExpressionIsStep(expression, timeVariable)
expr = regexprep(char(string(expression)), "\s+", "");
timeToken = regexptranslate("escape", char(string(timeVariable)));
numberToken = localNumberPattern();

patterns = { ...
    ['^(?<amp>' numberToken ')\*heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'], ...
    ['^heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<num>' numberToken ')\*heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'], ...
    ['^(?<leading_bias>' numberToken ')(?<join>[+-])(?:(?<amp>' numberToken ')\*)?heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)$'], ...
    ['^(?<leading_bias>' numberToken ')(?<join>[+-])heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')$'], ...
    ['^(?<leading_bias>' numberToken ')(?<join>[+-])(?<num>' numberToken ')\*heaviside\(' timeToken '(?<offset>[+-]' numberToken ')?\)/(?<den>' numberToken ')$'] ...
};

for index = 1:numel(patterns)
    match = regexp(expr, patterns{index}, "names");
    if isempty(match)
        continue;
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
        stepTime = -localNumericTokenToDouble(match.offset);
    end
    bias = 0.0;
    if isfield(match, "bias") && ~isempty(match.bias)
        bias = localNumericTokenToDouble(match.bias);
    elseif isfield(match, "leading_bias") && ~isempty(match.leading_bias)
        bias = localNumericTokenToDouble(match.leading_bias);
    end
    isStep = true;
    payload = struct("step_time", stepTime, "before", bias, "after", bias + amplitude);
    return;
end

isStep = false;
payload = struct("step_time", 0, "before", 0, "after", 0);
end

function [isPulse, payload] = localExpressionIsPulse(expression, timeVariable, tSpan)
expr = regexprep(char(string(expression)), "\s+", "");
timeToken = regexptranslate("escape", char(string(timeVariable)));
numberToken = localNumberPattern();
pattern = ['^(?<amp>' numberToken ')\*heaviside\(' timeToken '\-(?<start>' numberToken ')\)(?<second>[+-])(?<amp2>' numberToken ')\*heaviside\(' timeToken '\-(?<stop>' numberToken ')\)(?<bias>[+-]' numberToken ')?$'];
match = regexp(expr, pattern, "names");
if isempty(match)
    isPulse = false;
    payload = struct("amplitude", 0, "start_time", 0, "width", 0, "period", 1);
    return;
end
amp1 = localNumericTokenToDouble(match.amp);
amp2 = localNumericTokenToDouble(match.amp2);
startTime = localNumericTokenToDouble(match.start);
stopTime = localNumericTokenToDouble(match.stop);
if match.second ~= '-' || abs(amp1 - amp2) > 1e-9 || stopTime <= startTime
    isPulse = false;
    payload = struct("amplitude", 0, "start_time", 0, "width", 0, "period", 1);
    return;
end
width = stopTime - startTime;
period = localDefaultPulsePeriodFromSpan(startTime, width, tSpan);
isPulse = true;
payload = struct( ...
    "amplitude", amp1, ...
    "start_time", startTime, ...
    "width", width, ...
    "period", period ...
);
end

function [isRamp, payload] = localExpressionIsRamp(expression, timeVariable)
expr = regexprep(char(string(expression)), "\s+", "");
timeToken = regexptranslate("escape", char(string(timeVariable)));
numberToken = localNumberPattern();
pattern = ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\((?<slope>' numberToken ')\*' timeToken '(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'];
match = regexp(expr, pattern, "names");
if isempty(match)
    swappedPattern = ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\(' timeToken '\*(?<slope>' numberToken ')(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'];
    swappedMatch = regexp(expr, swappedPattern, "names");
    if ~isempty(swappedMatch)
        match = swappedMatch;
    end
end
if isempty(match)
    fractionalPattern = ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\(\((?<num>' numberToken ')\*' timeToken '\)/(?<den>' numberToken ')(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'];
    fractionalMatch = regexp(expr, fractionalPattern, "names");
    if ~isempty(fractionalMatch)
        match = fractionalMatch;
        match.slope = num2str(localNumericTokenToDouble(fractionalMatch.num) / localNumericTokenToDouble(fractionalMatch.den), 17);
    end
end
if isempty(match)
    fractionalSwappedPattern = ['^heaviside\(' timeToken '\-(?<start>' numberToken ')\)\*\(\(' timeToken '\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<offset>[+-]' numberToken ')\)(?<bias>[+-]' numberToken ')?$'];
    fractionalSwappedMatch = regexp(expr, fractionalSwappedPattern, "names");
    if ~isempty(fractionalSwappedMatch)
        match = fractionalSwappedMatch;
        match.slope = num2str(localNumericTokenToDouble(fractionalSwappedMatch.num) / localNumericTokenToDouble(fractionalSwappedMatch.den), 17);
    end
end
if isempty(match)
    isRamp = false;
    payload = struct("slope", 0, "start_time", 0, "initial_output", 0);
    return;
end
startTime = localNumericTokenToDouble(match.start);
slope = localNumericTokenToDouble(match.slope);
offset = localNumericTokenToDouble(match.offset);
expectedOffset = -slope * startTime;
if abs(offset - expectedOffset) > 1e-9
    isRamp = false;
    payload = struct("slope", 0, "start_time", 0, "initial_output", 0);
    return;
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end
isRamp = true;
payload = struct( ...
    "slope", slope, ...
    "start_time", startTime, ...
    "initial_output", bias ...
);
end

function [isSine, payload] = localExpressionIsSineWave(expression, timeVariable)
expr = regexprep(char(string(expression)), "\s+", "");
timeToken = regexptranslate("escape", char(string(timeVariable)));
numberToken = localNumberPattern();
pattern = ['^(?:(?<amp>' numberToken ')\*)?(?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)(?<bias>[+-]' numberToken ')?$'];
match = regexp(expr, pattern, "names");
if isempty(match)
    trailingPattern = ['^(?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'];
    trailingMatch = regexp(expr, trailingPattern, "names");
    if ~isempty(trailingMatch)
        match = trailingMatch;
    end
end
if isempty(match)
    fractionalPattern = ['^\((?<num>' numberToken ')\*(?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'];
    fractionalMatch = regexp(expr, fractionalPattern, "names");
    if ~isempty(fractionalMatch)
        match = fractionalMatch;
        match.amp = num2str(localNumericTokenToDouble(fractionalMatch.num) / localNumericTokenToDouble(fractionalMatch.den), 17);
    end
end
if isempty(match)
    fractionalTrailingPattern = ['^\((?<fn>sin|cos)\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'];
    fractionalTrailingMatch = regexp(expr, fractionalTrailingPattern, "names");
    if ~isempty(fractionalTrailingMatch)
        match = fractionalTrailingMatch;
        match.amp = num2str(localNumericTokenToDouble(fractionalTrailingMatch.num) / localNumericTokenToDouble(fractionalTrailingMatch.den), 17);
    end
end
if isempty(match)
    isSine = false;
    payload = struct("amplitude", 0, "frequency", 0, "phase", 0, "bias", 0);
    return;
end
amplitude = 1.0;
if isfield(match, "amp") && ~isempty(match.amp)
    amplitude = localNumericTokenToDouble(match.amp);
end
frequency = localNumericTokenToDouble(match.freq);
phase = 0.0;
if isfield(match, "phase") && ~isempty(match.phase)
    phase = localNumericTokenToDouble(match.phase);
end
if strcmp(match.fn, 'cos')
    phase = phase + pi / 2.0;
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end
isSine = true;
payload = struct( ...
    "amplitude", amplitude, ...
    "frequency", frequency, ...
    "phase", phase, ...
    "bias", bias ...
);
end

function [isSquare, payload] = localExpressionIsSquareWave(expression, timeVariable)
expr = regexprep(char(string(expression)), "\s+", "");
timeToken = regexptranslate("escape", char(string(timeVariable)));
numberToken = localNumberPattern();
pattern = ['^(?:(?<amp>' numberToken ')\*)?sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)(?<bias>[+-]' numberToken ')?$'];
match = regexp(expr, pattern, "names");
if isempty(match)
    trailingPattern = ['^sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)\*(?<amp>' numberToken ')(?<bias>[+-]' numberToken ')?$'];
    trailingMatch = regexp(expr, trailingPattern, "names");
    if ~isempty(trailingMatch)
        match = trailingMatch;
    end
end
if isempty(match)
    fractionalPattern = ['^\((?<num>' numberToken ')\*sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'];
    fractionalMatch = regexp(expr, fractionalPattern, "names");
    if ~isempty(fractionalMatch)
        match = fractionalMatch;
        match.amp = num2str(localNumericTokenToDouble(fractionalMatch.num) / localNumericTokenToDouble(fractionalMatch.den), 17);
    end
end
if isempty(match)
    fractionalTrailingPattern = ['^\(sign\(sin\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?\)\)\*(?<num>' numberToken ')\)/(?<den>' numberToken ')(?<bias>[+-]' numberToken ')?$'];
    fractionalTrailingMatch = regexp(expr, fractionalTrailingPattern, "names");
    if ~isempty(fractionalTrailingMatch)
        match = fractionalTrailingMatch;
        match.amp = num2str(localNumericTokenToDouble(fractionalTrailingMatch.num) / localNumericTokenToDouble(fractionalTrailingMatch.den), 17);
    end
end
if isempty(match)
    isSquare = false;
    payload = struct("amplitude", 0, "frequency", 0, "phase", 0, "bias", 0);
    return;
end

amplitude = 1.0;
if isfield(match, "amp") && ~isempty(match.amp)
    amplitude = localNumericTokenToDouble(match.amp);
end
frequency = localNumericTokenToDouble(match.freq);
phase = 0.0;
if isfield(match, "phase") && ~isempty(match.phase)
    phase = localNumericTokenToDouble(match.phase);
end
bias = 0.0;
if isfield(match, "bias") && ~isempty(match.bias)
    bias = localNumericTokenToDouble(match.bias);
end
isSquare = true;
payload = struct( ...
    "amplitude", amplitude, ...
    "frequency", frequency, ...
    "phase", phase, ...
    "bias", bias ...
);
end

function [isRepeating, payload] = localExpressionIsRepeatingSequenceWave(expression, timeVariable)
expr = regexprep(char(string(expression)), "\s+", "");
timeToken = regexptranslate("escape", char(string(timeVariable)));
numberToken = localNumberPattern();
pattern = ['^(?:(?<amp>' numberToken ')\*)?sawtooth\((?<freq>' numberToken ')\*' timeToken '(?<phase>[+-]' numberToken ')?(?:,(?<width>' numberToken '))?\)(?<bias>[+-]' numberToken ')?$'];
match = regexp(expr, pattern, "names");
if isempty(match)
    isRepeating = false;
    payload = struct("waveform_kind", "", "amplitude", 0, "frequency", 0, "phase", 0, "bias", 0, "width", 1);
    return;
end

amplitude = 1.0;
if isfield(match, "amp") && ~isempty(match.amp)
    amplitude = localNumericTokenToDouble(match.amp);
end
frequency = localNumericTokenToDouble(match.freq);
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

waveformKind = "sawtooth";
if abs(width - 0.5) <= 1e-12
    waveformKind = "triangle";
end
isRepeating = true;
payload = struct( ...
    "waveform_kind", waveformKind, ...
    "amplitude", amplitude, ...
    "frequency", frequency, ...
    "phase", phase, ...
    "bias", bias, ...
    "width", width ...
);
end

function [clockBlockName, clockSignal] = localEnsureClock(modelName, clockBlockName, clockSignal)
if strlength(string(clockBlockName)) ~= 0
    return;
end
clockBlockName = 'clock_t';
add_block("simulink/Sources/Clock", [modelName '/' clockBlockName], ...
    "Position", [40 240 70 260]);
clockSignal = [clockBlockName '/1'];
end

function localSetMatlabFunctionScript(blockPath, blockName, dependencies, expression, outputName)
rt = sfroot;
chart = rt.find('-isa', 'Stateflow.EMChart', 'Path', blockPath);
if isempty(chart)
    error("matlabv2native:MissingMatlabFunctionChart", ...
        "Could not resolve MATLAB Function chart for block '%s'.", blockPath);
end
functionName = matlab.lang.makeValidName(blockName);
signatureArgs = strjoin(dependencies, ", ");
if isempty(signatureArgs)
    header = sprintf("function %s = %s()", outputName, functionName);
else
    header = sprintf("function %s = %s(%s)", outputName, functionName, signatureArgs);
end
chart.Script = sprintf("%s\n%s = %s;\n", header, outputName, expression);
end

function dependencies = localExpressionDependencies(expression, stateNames, inputNames, parameterNames, timeVariable)
matches = regexp(char(string(expression)), "[A-Za-z][A-Za-z0-9_]*", "match");
orderedPool = [reshape(stateNames, 1, []), reshape(inputNames, 1, []), reshape(parameterNames, 1, []), {char(string(timeVariable))}];
dependencies = {};
for index = 1:numel(orderedPool)
    candidate = orderedPool{index};
    if isempty(candidate)
        continue;
    end
    if any(strcmp(matches, candidate))
        dependencies{end + 1} = candidate; %#ok<AGROW>
    end
end
dependencies = reshape(unique(dependencies, "stable"), 1, []);
end

function port = localDirectSignalPort(rhsText, signalSources)
rhsText = strtrim(char(string(rhsText)));
if isfield(signalSources, rhsText)
    port = signalSources.(rhsText);
else
    port = '';
end
end

function port = localSignalPortForDependency(dependency, signalSources, clockSignal, timeVariable)
dependency = char(string(dependency));
if strcmp(dependency, char(string(timeVariable)))
    port = clockSignal;
    return;
end
if isfield(signalSources, dependency)
    port = signalSources.(dependency);
    return;
end
error("matlabv2native:MissingSignalDependency", ...
    "Missing signal dependency '%s' while wiring the native explicit-ODE model.", dependency);
end

function tf = localDeferredBlocksNeedClock(deferredBlocks, timeVariable)
tf = false;
timeName = char(string(timeVariable));
for index = 1:numel(deferredBlocks)
    dependencies = deferredBlocks(index).dependencies;
    for depIndex = 1:numel(dependencies)
        if strcmp(char(string(dependencies{depIndex})), timeName)
            tf = true;
            return;
        end
    end
end
end

function [signalPort, family, clockBlockName, clockSignal] = localNativeTimeExpressionRhsPort( ...
    modelName, stateName, rhsText, position, timeVariable, modelConfig, clockBlockName, clockSignal)

signalPort = '';
family = "";

if ~localExpressionDependsOnlyOnTime(rhsText, timeVariable)
    return;
end

rhsSpec = simucopilot.internal.recognizeExpressionInputSpec(rhsText, timeVariable);
if isempty(rhsSpec)
    rhsSpec = localRecognizeAffineTimeSpec(rhsText, timeVariable);
end
if isempty(rhsSpec)
    return;
end

blockName = ['rhs_' localSanitize(stateName)];
inputSpecs = struct();
inputSpecs.(blockName) = rhsSpec;
[signalPort, family, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, blockName, position, struct(), inputSpecs, struct(), {}, {}, ...
    timeVariable, modelConfig, clockBlockName, clockSignal);
end

function tf = localExpressionDependsOnlyOnTime(rhsText, timeVariable)
tf = false;
try
    vars = symvar(str2sym(rhsText));
catch
    return;
end

if isempty(vars)
    return;
end

timeName = char(string(timeVariable));
varNames = arrayfun(@char, vars, "UniformOutput", false);
tf = all(strcmp(varNames, timeName));
end

function spec = localRecognizeAffineTimeSpec(expr, timeVariable)
spec = [];
timeName = char(string(timeVariable));
if isempty(strtrim(timeName))
    return;
end

expr = strtrim(char(string(expr)));
if strcmp(expr, timeName)
    return;
end

try
    tSym = sym(timeName);
    exprSym = str2sym(expr);
    exprVars = arrayfun(@char, symvar(exprSym), "UniformOutput", false);
    if ~all(strcmp(exprVars, timeName))
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

function signalPort = localNativeAffineRhsPort( ...
    modelName, stateName, rhsText, position, signalSources, stateNames, inputNames, parameterNames)
[isAffine, affine] = localAffineSignalExpression(rhsText, stateNames, inputNames, parameterNames);
if ~isAffine
    signalPort = '';
    return;
end

mainName = ['rhs_' localSanitize(stateName)];
terms = affine.terms;
constantValue = affine.constant;
termPorts = cell(1, 0);

if abs(constantValue) <= 1e-12 && numel(terms) == 1 && abs(terms(1).coefficient - 1.0) > 1e-12
    add_block("simulink/Math Operations/Gain", [modelName '/' mainName], ...
        "Gain", localNumericString(terms(1).coefficient), ...
        "Position", position);
    add_line(modelName, signalSources.(terms(1).name), [mainName '/1'], "autorouting", "on");
    signalPort = [mainName '/1'];
    return;
end

for index = 1:numel(terms)
    sourcePort = signalSources.(terms(index).name);
    if abs(terms(index).coefficient - 1.0) <= 1e-12
        termPorts{end + 1} = sourcePort; %#ok<AGROW>
        continue;
    end

    gainName = sprintf('%s_gain_%s', mainName, localSanitize(terms(index).name));
    add_block("simulink/Math Operations/Gain", [modelName '/' gainName], ...
        "Gain", localNumericString(terms(index).coefficient), ...
        "Position", localAffineAuxPosition(position, index - 1));
    add_line(modelName, sourcePort, [gainName '/1'], "autorouting", "on");
    termPorts{end + 1} = [gainName '/1']; %#ok<AGROW>
end

if abs(constantValue) > 1e-12
    constName = [mainName '_const'];
    add_block("simulink/Sources/Constant", [modelName '/' constName], ...
        "Value", localNumericString(constantValue), ...
        "Position", localAffineAuxPosition(position, numel(termPorts)));
    termPorts{end + 1} = [constName '/1']; %#ok<AGROW>
end

if isempty(termPorts)
    signalPort = '';
    return;
end

if numel(termPorts) == 1
    signalPort = termPorts{1};
    return;
end

add_block("simulink/Math Operations/Sum", [modelName '/' mainName], ...
    "Inputs", repmat('+', 1, numel(termPorts)), ...
    "Position", position);
for index = 1:numel(termPorts)
    add_line(modelName, termPorts{index}, [mainName '/' num2str(index)], "autorouting", "on");
end
signalPort = [mainName '/1'];
end

function [signalPort, clockBlockName, clockSignal] = localNativeSignalPlusTimeRhsPort( ...
    modelName, stateName, rhsText, position, signalSources, stateNames, inputNames, parameterNames, ...
    timeVariable, modelConfig, clockBlockName, clockSignal)
[isMixed, affine, timeExpression] = localSignalPlusTimeExpression(rhsText, stateNames, inputNames, parameterNames, timeVariable);
signalPort = '';
if ~isMixed
    return;
end

timeSpec = simucopilot.internal.recognizeExpressionInputSpec(timeExpression, timeVariable);
if isempty(timeSpec)
    timeSpec = localRecognizeAffineTimeSpec(timeExpression, timeVariable);
end
if isempty(timeSpec)
    return;
end

mainName = ['rhs_' localSanitize(stateName)];
termPorts = cell(1, 0);
terms = affine.terms;

for index = 1:numel(terms)
    sourcePort = signalSources.(terms(index).name);
    if abs(terms(index).coefficient - 1.0) <= 1e-12
        termPorts{end + 1} = sourcePort; %#ok<AGROW>
        continue;
    end

    gainName = sprintf('%s_gain_%s', mainName, localSanitize(terms(index).name));
    add_block("simulink/Math Operations/Gain", [modelName '/' gainName], ...
        "Gain", localNumericString(terms(index).coefficient), ...
        "Position", localAffineAuxPosition(position, index - 1));
    add_line(modelName, sourcePort, [gainName '/1'], "autorouting", "on");
    termPorts{end + 1} = [gainName '/1']; %#ok<AGROW>
end

timeName = [mainName '_time'];
inputSpecs = struct();
inputSpecs.(timeName) = timeSpec;
[timePort, ~, clockBlockName, clockSignal] = localAddInputSource( ...
    modelName, timeName, localAffineAuxPosition(position, numel(termPorts)), ...
    struct(), inputSpecs, struct(), {}, {}, timeVariable, modelConfig, clockBlockName, clockSignal);
termPorts{end + 1} = timePort; %#ok<AGROW>

if isempty(termPorts)
    return;
end

if numel(termPorts) == 1
    signalPort = termPorts{1};
    return;
end

add_block("simulink/Math Operations/Sum", [modelName '/' mainName], ...
    "Inputs", repmat('+', 1, numel(termPorts)), ...
    "Position", position);
for index = 1:numel(termPorts)
    add_line(modelName, termPorts{index}, [mainName '/' num2str(index)], "autorouting", "on");
end
signalPort = [mainName '/1'];
end

function [signalPort, clockBlockName, clockSignal] = localNativeRecursiveRhsPort( ...
    modelName, stateName, rhsText, position, signalSources, dependencies, rhsStyle, timeVariable, modelConfig, clockBlockName, clockSignal)
signalPort = '';
switch char(string(rhsStyle))
    case 'subsystem_native'
        [signalPort, clockBlockName, clockSignal] = localNativeRecursiveSubsystemRhsPort( ...
            modelName, stateName, rhsText, position, signalSources, dependencies, ...
            timeVariable, modelConfig, clockBlockName, clockSignal);
    case 'flat_native'
        [signalPort, clockBlockName, clockSignal] = localNativeRecursiveFlatRhsPort( ...
            modelName, stateName, rhsText, position, signalSources, ...
            timeVariable, modelConfig, clockBlockName, clockSignal);
    otherwise
        signalPort = '';
end
end

function [signalPort, clockBlockName, clockSignal] = localNativeRecursiveFlatRhsPort( ...
    modelName, stateName, rhsText, position, signalSources, timeVariable, modelConfig, clockBlockName, clockSignal)
signalPort = '';
prefix = ['rhs_' localSanitize(stateName)];
[node, clockBlockName, clockSignal, ~] = localLowerRecursiveRhsExpression( ...
    modelName, ...
    rhsText, ...
    prefix, ...
    position, ...
    0, ...
    signalSources, ...
    timeVariable, ...
    modelConfig, ...
    clockBlockName, ...
    clockSignal, ...
    1);
if ~node.supported || node.is_constant
    return;
end
signalPort = node.port;
end

function [signalPort, clockBlockName, clockSignal] = localNativeRecursiveSubsystemRhsPort( ...
    modelName, stateName, rhsText, position, signalSources, dependencies, timeVariable, modelConfig, clockBlockName, clockSignal)
signalPort = '';
subsystemName = ['rhs_' localSanitize(stateName)];
subsystemPath = [modelName '/' subsystemName];
add_block("simulink/Ports & Subsystems/Subsystem", subsystemPath, ...
    "Position", position);
localClearSubsystemChildren(subsystemPath);

localSignalSources = struct();
inportY = 40;
for index = 1:numel(dependencies)
    dependency = char(string(dependencies{index}));
    inportBlockName = localSanitize(dependency);
    add_block("simulink/Ports & Subsystems/In1", [subsystemPath '/' inportBlockName], ...
        "Port", num2str(index), ...
        "Position", [35 inportY 65 inportY + 14]);
    localSignalSources.(dependency) = [inportBlockName '/1'];
    inportY = inportY + 40;
end

prefix = 'rhs_compute';
[node, clockBlockName, clockSignal, ~] = localLowerRecursiveRhsExpression( ...
    subsystemPath, ...
    rhsText, ...
    prefix, ...
    [190 80 330 140], ...
    0, ...
    localSignalSources, ...
    timeVariable, ...
    modelConfig, ...
    clockBlockName, ...
    clockSignal, ...
    1);
if ~node.supported || node.is_constant
    delete_block(subsystemPath);
    return;
end

add_block("simulink/Ports & Subsystems/Out1", [subsystemPath '/out'], ...
    "Port", "1", ...
    "Position", [560 100 590 114]);
add_line(subsystemPath, node.port, 'out/1', "autorouting", "on");

if any(strcmp(cellfun(@(item) char(string(item)), dependencies, "UniformOutput", false), char(string(timeVariable)))) && isempty(clockSignal)
    [clockBlockName, clockSignal] = localEnsureClock(modelName, clockBlockName, clockSignal);
end

for index = 1:numel(dependencies)
    dependency = char(string(dependencies{index}));
    dependencyPort = localSignalPortForDependency(dependency, signalSources, clockSignal, timeVariable);
    add_line(modelName, dependencyPort, [subsystemName '/' num2str(index)], "autorouting", "on");
end

signalPort = [subsystemName '/1'];
end

function localClearSubsystemChildren(subsystemPath)
childBlocks = find_system(subsystemPath, "SearchDepth", 1, "Type", "Block");
for index = 1:numel(childBlocks)
    childPath = char(string(childBlocks{index}));
    if strcmp(childPath, subsystemPath)
        continue;
    end
    delete_block(childPath);
end
end

function [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
    modelName, exprText, preferredName, basePosition, depth, signalSources, timeVariable, ...
    modelConfig, clockBlockName, clockSignal, nextId)
node = localUnsupportedRecursiveNode();
exprText = localRecursiveStripOuterParens(strtrim(char(string(exprText))));
if strlength(string(exprText)) == 0
    return;
end

if isfield(signalSources, exprText)
    node = localSignalRecursiveNode(signalSources.(exprText));
    return;
end

[isNumericConstant, numericConstant] = localTryNumericExpressionValue(exprText);
if isNumericConstant
    node = localConstantRecursiveNode(numericConstant);
    return;
end

[timeSpec, recognizedTimeExpression] = localRecognizedRecursiveTimeSpec(exprText, timeVariable);
if recognizedTimeExpression && ~isfield(signalSources, char(string(timeVariable)))
    blockName = localResolvedRecursiveBlockName(preferredName, nextId, 'time');
    if strlength(string(preferredName)) == 0
        nextId = nextId + 1;
    end
    inputSpecs = struct();
    inputSpecs.(blockName) = timeSpec;
    [signalPort, ~, clockBlockName, clockSignal] = localAddInputSource( ...
        modelName, ...
        blockName, ...
        localRecursivePosition(basePosition, depth, nextId), ...
        struct(), ...
        inputSpecs, ...
        signalSources, ...
        {}, ...
        {}, ...
        timeVariable, ...
        modelConfig, ...
        clockBlockName, ...
        clockSignal);
    node = localSignalRecursiveNode(signalPort);
    return;
end

[isAdditive, additiveParts] = localRecursiveAdditiveParts(exprText);
if isAdditive
    [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveAdditiveRhs( ...
        modelName, additiveParts, preferredName, basePosition, depth, signalSources, ...
        timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
    return;
end

[isMultiplicative, multiplicativeParts] = localRecursiveMultiplicativeParts(exprText);
if isMultiplicative
    [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveMultiplicativeRhs( ...
        modelName, multiplicativeParts, preferredName, basePosition, depth, signalSources, ...
        timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
    return;
end

[isPower, powerBase, powerExponent] = localRecursivePowerParts(exprText);
if isPower
    [node, clockBlockName, clockSignal, nextId] = localLowerRecursivePowerRhs( ...
        modelName, powerBase, powerExponent, preferredName, basePosition, depth, signalSources, ...
        timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
    return;
end

[functionName, functionArgs] = localRecursiveFunctionParts(exprText);
if strlength(string(functionName)) ~= 0
    [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveFunctionRhs( ...
        modelName, functionName, functionArgs, preferredName, basePosition, depth, signalSources, ...
        timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
end
end

function [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveAdditiveRhs( ...
    modelName, parts, preferredName, basePosition, depth, signalSources, timeVariable, ...
    modelConfig, clockBlockName, clockSignal, nextId)
node = localUnsupportedRecursiveNode();
termPorts = {};
termSigns = '';
constantValue = 0.0;

for index = 1:numel(parts)
    [childName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [childNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
        modelName, parts(index).text, childName, basePosition, depth + 1, signalSources, ...
        timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
    if ~childNode.supported
        return;
    end
    signValue = 1.0;
    if parts(index).sign == '-'
        signValue = -1.0;
    end
    if childNode.is_constant
        constantValue = constantValue + signValue * childNode.constant_value;
        continue;
    end
    termPorts{end + 1} = childNode.port; %#ok<AGROW>
    termSigns(end + 1) = parts(index).sign; %#ok<AGROW>
end

if abs(constantValue) > 1e-12
    [constantName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [constantNode, nextId] = localRecursiveConstantBlock( ...
        modelName, abs(constantValue), constantName, basePosition, depth + 1, nextId);
    termPorts{end + 1} = constantNode.port; %#ok<AGROW>
    if constantValue < 0
        termSigns(end + 1) = '-'; %#ok<AGROW>
    else
        termSigns(end + 1) = '+'; %#ok<AGROW>
    end
end

if isempty(termPorts)
    node = localConstantRecursiveNode(constantValue);
    return;
end

if numel(termPorts) == 1
    if termSigns(1) == '+'
        node = localSignalRecursiveNode(termPorts{1});
        return;
    end
    [node, nextId] = localRecursiveGainBlock( ...
        modelName, termPorts{1}, -1.0, preferredName, basePosition, depth, nextId);
    return;
end

blockName = localResolvedRecursiveBlockName(preferredName, nextId, 'sum');
if strlength(string(preferredName)) == 0
    nextId = nextId + 1;
end
add_block("simulink/Math Operations/Sum", [modelName '/' blockName], ...
    "Inputs", termSigns, ...
    "Position", localRecursivePosition(basePosition, depth, nextId));
for index = 1:numel(termPorts)
    add_line(modelName, termPorts{index}, [blockName '/' num2str(index)], "autorouting", "on");
end
node = localSignalRecursiveNode([blockName '/1']);
end

function [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveMultiplicativeRhs( ...
    modelName, parts, preferredName, basePosition, depth, signalSources, timeVariable, ...
    modelConfig, clockBlockName, clockSignal, nextId)
node = localUnsupportedRecursiveNode();

[childName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
[currentNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
    modelName, parts(1).text, childName, basePosition, depth + 1, signalSources, ...
    timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
if ~currentNode.supported
    return;
end

for index = 2:numel(parts)
    [childName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [rhsNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
        modelName, parts(index).text, childName, basePosition, depth + 1, signalSources, ...
        timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
    if ~rhsNode.supported
        return;
    end
    stepName = preferredName;
    if index ~= numel(parts)
        [stepName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    end
    [currentNode, nextId] = localCombineRecursiveProductNodes( ...
        modelName, currentNode, parts(index).operator, rhsNode, stepName, basePosition, depth, nextId);
    if ~currentNode.supported
        return;
    end
end

node = currentNode;
end

function [node, clockBlockName, clockSignal, nextId] = localLowerRecursivePowerRhs( ...
    modelName, baseExpr, exponentExpr, preferredName, basePosition, depth, signalSources, ...
    timeVariable, modelConfig, clockBlockName, clockSignal, nextId)
node = localUnsupportedRecursiveNode();
[isNumericExponent, exponentValue] = localTryNumericExpressionValue(exponentExpr);
if ~isNumericExponent
    return;
end

[childName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
[baseNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
    modelName, baseExpr, childName, basePosition, depth + 1, signalSources, ...
    timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
if ~baseNode.supported
    return;
end

roundedExponent = round(exponentValue);
if abs(exponentValue - roundedExponent) <= 1e-12 && roundedExponent >= 0
    if baseNode.is_constant
        node = localConstantRecursiveNode(baseNode.constant_value ^ roundedExponent);
        return;
    end
    switch roundedExponent
        case 0
            node = localConstantRecursiveNode(1.0);
            return;
        case 1
            node = baseNode;
            return;
        otherwise
            currentNode = baseNode;
            for powerIndex = 2:roundedExponent
                stepName = preferredName;
                if powerIndex ~= roundedExponent
                    [stepName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
                end
                [currentNode, nextId] = localCombineRecursiveProductNodes( ...
                    modelName, currentNode, '*', baseNode, stepName, basePosition, depth, nextId);
                if ~currentNode.supported
                    return;
                end
            end
            node = currentNode;
            return;
    end
end

if abs(exponentValue - 0.5) <= 1e-12
    [node, nextId] = localRecursiveUnaryBlock( ...
        modelName, baseNode, "sqrt", preferredName, basePosition, depth, nextId);
    return;
end

if abs(exponentValue + 1.0) <= 1e-12
    oneNode = localConstantRecursiveNode(1.0);
    [node, nextId] = localCombineRecursiveProductNodes( ...
        modelName, oneNode, '/', baseNode, preferredName, basePosition, depth, nextId);
end
end

function [node, clockBlockName, clockSignal, nextId] = localLowerRecursiveFunctionRhs( ...
    modelName, functionName, functionArgs, preferredName, basePosition, depth, signalSources, ...
    timeVariable, modelConfig, clockBlockName, clockSignal, nextId)
node = localUnsupportedRecursiveNode();
functionName = lower(char(string(functionName)));
switch functionName
    case {"sin", "cos", "atan", "exp", "log", "sqrt", "abs", "sign"}
        if numel(functionArgs) ~= 1
            return;
        end
        [childName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
        [inputNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
            modelName, functionArgs{1}, childName, basePosition, depth + 1, signalSources, ...
            timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
        if ~inputNode.supported
            return;
        end
        [node, nextId] = localRecursiveUnaryBlock( ...
            modelName, inputNode, functionName, preferredName, basePosition, depth, nextId);
    case {"atan2", "min", "max"}
        if numel(functionArgs) ~= 2
            return;
        end
        [leftName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
        [rightName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
        [leftNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
            modelName, functionArgs{1}, leftName, basePosition, depth + 1, signalSources, ...
            timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
        if ~leftNode.supported
            return;
        end
        [rightNode, clockBlockName, clockSignal, nextId] = localLowerRecursiveRhsExpression( ...
            modelName, functionArgs{2}, rightName, basePosition, depth + 1, signalSources, ...
            timeVariable, modelConfig, clockBlockName, clockSignal, nextId);
        if ~rightNode.supported
            return;
        end
        [node, nextId] = localRecursiveBinaryBlock( ...
            modelName, leftNode, rightNode, functionName, preferredName, basePosition, depth, nextId);
end
end

function [node, nextId] = localCombineRecursiveProductNodes( ...
    modelName, leftNode, operatorToken, rightNode, preferredName, basePosition, depth, nextId)
node = localUnsupportedRecursiveNode();

if leftNode.is_constant && rightNode.is_constant
    if operatorToken == '/'
        node = localConstantRecursiveNode(leftNode.constant_value / rightNode.constant_value);
    else
        node = localConstantRecursiveNode(leftNode.constant_value * rightNode.constant_value);
    end
    return;
end

if operatorToken == '*'
    if leftNode.is_constant && abs(leftNode.constant_value) <= 1e-12
        node = leftNode;
        return;
    end
    if rightNode.is_constant && abs(rightNode.constant_value) <= 1e-12
        node = rightNode;
        return;
    end
    if leftNode.is_constant && abs(leftNode.constant_value - 1.0) <= 1e-12
        node = rightNode;
        return;
    end
    if rightNode.is_constant && abs(rightNode.constant_value - 1.0) <= 1e-12
        node = leftNode;
        return;
    end
    if leftNode.is_constant && ~rightNode.is_constant
        [node, nextId] = localRecursiveGainBlock( ...
            modelName, rightNode.port, leftNode.constant_value, preferredName, basePosition, depth, nextId);
        return;
    end
    if rightNode.is_constant && ~leftNode.is_constant
        [node, nextId] = localRecursiveGainBlock( ...
            modelName, leftNode.port, rightNode.constant_value, preferredName, basePosition, depth, nextId);
        return;
    end
else
    if rightNode.is_constant
        if abs(rightNode.constant_value) <= 1e-12
            return;
        end
        if leftNode.is_constant
            node = localConstantRecursiveNode(leftNode.constant_value / rightNode.constant_value);
            return;
        end
        [node, nextId] = localRecursiveGainBlock( ...
            modelName, leftNode.port, 1.0 / rightNode.constant_value, preferredName, basePosition, depth, nextId);
        return;
    end
    if leftNode.is_constant && abs(leftNode.constant_value) <= 1e-12
        node = leftNode;
        return;
    end
end

blockName = localResolvedRecursiveBlockName(preferredName, nextId, 'product');
if strlength(string(preferredName)) == 0
    nextId = nextId + 1;
end
productParams = {"Position", localRecursivePosition(basePosition, depth, nextId)};
leftPort = leftNode.port;
rightPort = rightNode.port;

if leftNode.is_constant
    [constantName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [constantNode, nextId] = localRecursiveConstantBlock( ...
        modelName, leftNode.constant_value, constantName, basePosition, depth + 1, nextId);
    leftPort = constantNode.port;
end
if rightNode.is_constant
    [constantName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [constantNode, nextId] = localRecursiveConstantBlock( ...
        modelName, rightNode.constant_value, constantName, basePosition, depth + 1, nextId);
    rightPort = constantNode.port;
end

if operatorToken == '/'
    productParams = [productParams, {"Inputs", "*/"}]; %#ok<AGROW>
else
    productParams = [productParams, {"Inputs", "2"}]; %#ok<AGROW>
end
add_block("simulink/Math Operations/Product", [modelName '/' blockName], productParams{:});
add_line(modelName, leftPort, [blockName '/1'], "autorouting", "on");
add_line(modelName, rightPort, [blockName '/2'], "autorouting", "on");
node = localSignalRecursiveNode([blockName '/1']);
end

function [node, nextId] = localRecursiveUnaryBlock( ...
    modelName, inputNode, functionName, preferredName, basePosition, depth, nextId)
node = localUnsupportedRecursiveNode();
functionName = lower(char(string(functionName)));
if inputNode.is_constant
    switch functionName
        case "sin"
            node = localConstantRecursiveNode(sin(inputNode.constant_value));
        case "cos"
            node = localConstantRecursiveNode(cos(inputNode.constant_value));
        case "atan"
            node = localConstantRecursiveNode(atan(inputNode.constant_value));
        case "exp"
            node = localConstantRecursiveNode(exp(inputNode.constant_value));
        case "log"
            node = localConstantRecursiveNode(log(inputNode.constant_value));
        case "sqrt"
            node = localConstantRecursiveNode(sqrt(inputNode.constant_value));
        case "abs"
            node = localConstantRecursiveNode(abs(inputNode.constant_value));
        case "sign"
            node = localConstantRecursiveNode(sign(inputNode.constant_value));
    end
    return;
end

blockName = localResolvedRecursiveBlockName(preferredName, nextId, functionName);
if strlength(string(preferredName)) == 0
    nextId = nextId + 1;
end
blockPosition = localRecursivePosition(basePosition, depth, nextId);

switch functionName
    case {"sin", "cos", "atan"}
        add_block("simulink/Math Operations/Trigonometric Function", [modelName '/' blockName], ...
            "Operator", functionName, ...
            "Position", blockPosition);
    case {"exp", "log", "sqrt"}
        add_block("simulink/Math Operations/Math Function", [modelName '/' blockName], ...
            "Operator", functionName, ...
            "Position", blockPosition);
    case "abs"
        add_block("simulink/Math Operations/Abs", [modelName '/' blockName], ...
            "Position", blockPosition);
    case "sign"
        add_block("simulink/Math Operations/Sign", [modelName '/' blockName], ...
            "Position", blockPosition);
    otherwise
        return;
end
add_line(modelName, inputNode.port, [blockName '/1'], "autorouting", "on");
node = localSignalRecursiveNode([blockName '/1']);
end

function [node, nextId] = localRecursiveBinaryBlock( ...
    modelName, leftNode, rightNode, functionName, preferredName, basePosition, depth, nextId)
node = localUnsupportedRecursiveNode();
functionName = lower(char(string(functionName)));

if leftNode.is_constant && rightNode.is_constant
    switch functionName
        case "atan2"
            node = localConstantRecursiveNode(atan2(leftNode.constant_value, rightNode.constant_value));
        case "min"
            node = localConstantRecursiveNode(min(leftNode.constant_value, rightNode.constant_value));
        case "max"
            node = localConstantRecursiveNode(max(leftNode.constant_value, rightNode.constant_value));
    end
    return;
end

leftPort = leftNode.port;
rightPort = rightNode.port;
if leftNode.is_constant
    [constantName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [constantNode, nextId] = localRecursiveConstantBlock( ...
        modelName, leftNode.constant_value, constantName, basePosition, depth + 1, nextId);
    leftPort = constantNode.port;
end
if rightNode.is_constant
    [constantName, nextId] = localTakeRecursiveChildName(preferredName, nextId);
    [constantNode, nextId] = localRecursiveConstantBlock( ...
        modelName, rightNode.constant_value, constantName, basePosition, depth + 1, nextId);
    rightPort = constantNode.port;
end

blockName = localResolvedRecursiveBlockName(preferredName, nextId, functionName);
if strlength(string(preferredName)) == 0
    nextId = nextId + 1;
end
blockPosition = localRecursivePosition(basePosition, depth, nextId);

switch functionName
    case "atan2"
        add_block("simulink/Math Operations/Trigonometric Function", [modelName '/' blockName], ...
            "Operator", "atan2", ...
            "Position", blockPosition);
    case {"min", "max"}
        add_block("simulink/Math Operations/MinMax", [modelName '/' blockName], ...
            "Function", functionName, ...
            "Inputs", "2", ...
            "Position", blockPosition);
    otherwise
        return;
end
add_line(modelName, leftPort, [blockName '/1'], "autorouting", "on");
add_line(modelName, rightPort, [blockName '/2'], "autorouting", "on");
node = localSignalRecursiveNode([blockName '/1']);
end

function [node, nextId] = localRecursiveGainBlock( ...
    modelName, sourcePort, gainValue, preferredName, basePosition, depth, nextId)
if abs(gainValue - 1.0) <= 1e-12
    node = localSignalRecursiveNode(sourcePort);
    return;
end
if abs(gainValue) <= 1e-12
    node = localConstantRecursiveNode(0.0);
    return;
end

blockName = localResolvedRecursiveBlockName(preferredName, nextId, 'gain');
if strlength(string(preferredName)) == 0
    nextId = nextId + 1;
end
add_block("simulink/Math Operations/Gain", [modelName '/' blockName], ...
    "Gain", localNumericString(gainValue), ...
    "Position", localRecursivePosition(basePosition, depth, nextId));
add_line(modelName, sourcePort, [blockName '/1'], "autorouting", "on");
node = localSignalRecursiveNode([blockName '/1']);
end

function [node, nextId] = localRecursiveConstantBlock( ...
    modelName, constantValue, preferredName, basePosition, depth, nextId)
blockName = localResolvedRecursiveBlockName(preferredName, nextId, 'const');
if strlength(string(preferredName)) == 0
    nextId = nextId + 1;
end
add_block("simulink/Sources/Constant", [modelName '/' blockName], ...
    "Value", localNumericString(constantValue), ...
    "Position", localRecursivePosition(basePosition, depth, nextId));
node = localSignalRecursiveNode([blockName '/1']);
end

function [spec, tf] = localRecognizedRecursiveTimeSpec(exprText, timeVariable)
tf = false;
spec = [];
if ~localExpressionDependsOnlyOnTime(exprText, timeVariable)
    return;
end
spec = simucopilot.internal.recognizeExpressionInputSpec(exprText, timeVariable);
if isempty(spec)
    spec = localRecognizeAffineTimeSpec(exprText, timeVariable);
end
tf = ~isempty(spec);
end

function [tf, value] = localTryNumericExpressionValue(exprText)
tf = false;
value = NaN;
try
    exprSym = str2sym(exprText);
    if ~isempty(symvar(exprSym))
        return;
    end
    value = double(exprSym);
    tf = true;
catch
    tf = false;
    value = NaN;
end
end

function [tf, parts] = localRecursiveAdditiveParts(exprText)
exprText = localRecursiveStripOuterParens(exprText);
parts = struct("sign", {}, "text", {});
if strlength(string(exprText)) == 0
    tf = false;
    return;
end

currentSign = '+';
tokenStart = 1;
if exprText(1) == '+' || exprText(1) == '-'
    currentSign = exprText(1);
    tokenStart = 2;
end

depthParen = 0;
depthBracket = 0;
for index = tokenStart:numel(exprText)
    ch = exprText(index);
    if ch == '('
        depthParen = depthParen + 1;
        continue;
    end
    if ch == ')'
        depthParen = depthParen - 1;
        continue;
    end
    if ch == '['
        depthBracket = depthBracket + 1;
        continue;
    end
    if ch == ']'
        depthBracket = depthBracket - 1;
        continue;
    end
    if depthParen ~= 0 || depthBracket ~= 0
        continue;
    end
    if (ch == '+' || ch == '-') && localIsRecursiveBinaryAddSub(exprText, index)
        token = strtrim(exprText(tokenStart:index-1));
        if strlength(string(token)) ~= 0
            parts(end + 1) = struct("sign", currentSign, "text", token); %#ok<AGROW>
        end
        currentSign = ch;
        tokenStart = index + 1;
    end
end

token = strtrim(exprText(tokenStart:end));
if strlength(string(token)) ~= 0
    parts(end + 1) = struct("sign", currentSign, "text", token); %#ok<AGROW>
end

tf = numel(parts) > 1 || (numel(parts) == 1 && parts(1).sign == '-');
end

function [tf, parts] = localRecursiveMultiplicativeParts(exprText)
exprText = localRecursiveStripOuterParens(exprText);
parts = struct("operator", {}, "text", {});
depthParen = 0;
depthBracket = 0;
tokenStart = 1;
currentOperator = '*';

for index = 1:numel(exprText)
    ch = exprText(index);
    if ch == '('
        depthParen = depthParen + 1;
        continue;
    end
    if ch == ')'
        depthParen = depthParen - 1;
        continue;
    end
    if ch == '['
        depthBracket = depthBracket + 1;
        continue;
    end
    if ch == ']'
        depthBracket = depthBracket - 1;
        continue;
    end
    if depthParen ~= 0 || depthBracket ~= 0
        continue;
    end
    if (ch == '*' || ch == '/') && localIsRecursiveBinaryMulDiv(exprText, index)
        token = strtrim(exprText(tokenStart:index-1));
        if strlength(string(token)) == 0
            tf = false;
            parts = struct("operator", {}, "text", {});
            return;
        end
        parts(end + 1) = struct("operator", currentOperator, "text", token); %#ok<AGROW>
        currentOperator = ch;
        tokenStart = index + 1;
    end
end

token = strtrim(exprText(tokenStart:end));
if strlength(string(token)) == 0
    tf = false;
    parts = struct("operator", {}, "text", {});
    return;
end
parts(end + 1) = struct("operator", currentOperator, "text", token); %#ok<AGROW>
tf = numel(parts) > 1;
end

function [tf, baseExpr, exponentExpr] = localRecursivePowerParts(exprText)
exprText = localRecursiveStripOuterParens(exprText);
tf = false;
baseExpr = '';
exponentExpr = '';
depthParen = 0;
depthBracket = 0;
for index = numel(exprText):-1:1
    ch = exprText(index);
    if ch == ')'
        depthParen = depthParen + 1;
        continue;
    end
    if ch == '('
        depthParen = depthParen - 1;
        continue;
    end
    if ch == ']'
        depthBracket = depthBracket + 1;
        continue;
    end
    if ch == '['
        depthBracket = depthBracket - 1;
        continue;
    end
    if depthParen ~= 0 || depthBracket ~= 0
        continue;
    end
    if ch == '^'
        baseExpr = strtrim(exprText(1:index-1));
        exponentExpr = strtrim(exprText(index+1:end));
        tf = strlength(string(baseExpr)) ~= 0 && strlength(string(exponentExpr)) ~= 0;
        return;
    end
end
end

function [functionName, args] = localRecursiveFunctionParts(exprText)
functionName = "";
args = {};
exprText = localRecursiveStripOuterParens(exprText);
openIndex = find(exprText == '(', 1, 'first');
if isempty(openIndex) || exprText(end) ~= ')'
    return;
end
candidateName = strtrim(exprText(1:openIndex-1));
if isempty(candidateName) || ~isstrprop(candidateName(1), 'alpha')
    return;
end
for index = 2:numel(candidateName)
    if ~(isstrprop(candidateName(index), 'alphanum') || candidateName(index) == '_')
        functionName = "";
        args = {};
        return;
    end
end
if strlength(string(candidateName)) == 0
    return;
end
functionName = candidateName;
args = localRecursiveSplitTopLevel(exprText(openIndex + 1:end - 1));
end

function parts = localRecursiveSplitTopLevel(exprText)
parts = {};
exprText = char(string(exprText));
depthParen = 0;
depthBracket = 0;
tokenStart = 1;
for index = 1:numel(exprText)
    ch = exprText(index);
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
                parts{end + 1} = localRecursiveStripOuterParens(strtrim(exprText(tokenStart:index-1))); %#ok<AGROW>
                tokenStart = index + 1;
            end
    end
end
parts{end + 1} = localRecursiveStripOuterParens(strtrim(exprText(tokenStart:end)));
end

function tf = localIsRecursiveBinaryAddSub(exprText, index)
previousIndex = index - 1;
while previousIndex >= 1 && isspace(exprText(previousIndex))
    previousIndex = previousIndex - 1;
end
if previousIndex < 1
    tf = false;
    return;
end
previousChar = exprText(previousIndex);
tf = isempty(strfind('([,+-*/^', previousChar)); %#ok<STREMP>
end

function tf = localIsRecursiveBinaryMulDiv(exprText, index)
previousIndex = index - 1;
while previousIndex >= 1 && isspace(exprText(previousIndex))
    previousIndex = previousIndex - 1;
end
if previousIndex < 1
    tf = false;
    return;
end
previousChar = exprText(previousIndex);
tf = isempty(strfind('([,+-*/^', previousChar)); %#ok<STREMP>
end

function exprText = localRecursiveStripOuterParens(exprText)
exprText = strtrim(char(string(exprText)));
while strlength(string(exprText)) >= 2 && exprText(1) == '(' && exprText(end) == ')'
    depth = 0;
    balanced = true;
    for index = 1:numel(exprText)
        if exprText(index) == '('
            depth = depth + 1;
        elseif exprText(index) == ')'
            depth = depth - 1;
            if depth == 0 && index < numel(exprText)
                balanced = false;
                break;
            end
        end
    end
    if ~balanced || depth ~= 0
        break;
    end
    exprText = strtrim(exprText(2:end-1));
end
end

function name = localResolvedRecursiveBlockName(preferredName, nextId, suffix)
preferredName = char(string(preferredName));
if strlength(string(preferredName)) ~= 0
    name = preferredName;
    return;
end
name = sprintf('rhs_%s_%d', localSanitize(suffix), nextId);
end

function name = localGeneratedRecursiveChildName(preferredName, nextId)
baseName = localSanitize(char(string(preferredName)));
if strlength(string(baseName)) == 0
    baseName = 'rhs';
end
name = sprintf('%s_n%d', baseName, nextId);
end

function [name, nextId] = localTakeRecursiveChildName(preferredName, nextId)
name = localGeneratedRecursiveChildName(preferredName, nextId);
nextId = nextId + 1;
end

function position = localRecursivePosition(basePosition, depth, nextId)
xShift = 150 * max(depth, 0);
yShift = 34 * max(nextId - 1, 0);
position = [ ...
    basePosition(1) - xShift, ...
    basePosition(2) + yShift, ...
    basePosition(3) - xShift, ...
    basePosition(4) + yShift ...
];
end

function node = localUnsupportedRecursiveNode()
node = struct( ...
    "supported", false, ...
    "is_constant", false, ...
    "constant_value", NaN, ...
    "port", "");
end

function node = localSignalRecursiveNode(signalPort)
node = struct( ...
    "supported", true, ...
    "is_constant", false, ...
    "constant_value", NaN, ...
    "port", char(string(signalPort)));
end

function node = localConstantRecursiveNode(constantValue)
node = struct( ...
    "supported", true, ...
    "is_constant", true, ...
    "constant_value", double(constantValue), ...
    "port", "");
end

function [isMixed, affine, timeExpression] = localSignalPlusTimeExpression(rhsText, stateNames, inputNames, parameterNames, timeVariable)
isMixed = false;
affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
timeExpression = "";

signalNames = [reshape(stateNames, 1, []), reshape(inputNames, 1, []), reshape(parameterNames, 1, [])];
timeName = char(string(timeVariable));
if isempty(strtrim(timeName))
    return;
end

try
    rhsExpression = str2sym(rhsText);
catch
    return;
end

timeOnlyExpression = rhsExpression;
for index = 1:numel(signalNames)
    timeOnlyExpression = subs(timeOnlyExpression, sym(signalNames{index}), 0);
end

timeVars = arrayfun(@char, symvar(timeOnlyExpression), "UniformOutput", false);
if isempty(timeVars)
    return;
end
if ~all(strcmp(timeVars, timeName))
    return;
end

signalExpression = simplify(rhsExpression - timeOnlyExpression);
terms = struct("name", {}, "coefficient", {});
for index = 1:numel(signalNames)
    signalName = signalNames{index};
    coefficientExpression = simplify(diff(signalExpression, sym(signalName)));
    if ~isempty(symvar(coefficientExpression))
        return;
    end
    try
        coefficientValue = double(coefficientExpression);
    catch
        return;
    end
    if abs(coefficientValue) > 1e-12
        terms(end + 1) = struct("name", signalName, "coefficient", coefficientValue); %#ok<AGROW>
    end
    signalExpression = simplify(signalExpression - coefficientExpression * sym(signalName));
end

try
    residualValue = double(signalExpression);
catch
    return;
end
if abs(residualValue) > 1e-12
    return;
end

if isempty(terms)
    return;
end

isMixed = true;
affine = struct("constant", 0.0, "terms", terms);
timeExpression = char(formula(simplify(timeOnlyExpression)));
end

function [isAffine, affine] = localAffineSignalExpression(rhsText, stateNames, inputNames, parameterNames)
signalNames = [reshape(stateNames, 1, []), reshape(inputNames, 1, []), reshape(parameterNames, 1, [])];
rhsExpression = str2sym(rhsText);
constantExpression = rhsExpression;
for index = 1:numel(signalNames)
    constantExpression = subs(constantExpression, sym(signalNames{index}), 0);
end

if ~isempty(symvar(constantExpression))
    isAffine = false;
    affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
    return;
end

try
    constantValue = double(constantExpression);
catch
    isAffine = false;
    affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
    return;
end

residual = simplify(rhsExpression - constantExpression);
terms = struct("name", {}, "coefficient", {});
for index = 1:numel(signalNames)
    signalName = signalNames{index};
    coefficientExpression = simplify(diff(residual, sym(signalName)));
    if ~isempty(symvar(coefficientExpression))
        isAffine = false;
        affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
        return;
    end

    try
        coefficientValue = double(coefficientExpression);
    catch
        isAffine = false;
        affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
        return;
    end

    if abs(coefficientValue) > 1e-12
        terms(end + 1) = struct("name", signalName, "coefficient", coefficientValue); %#ok<AGROW>
    end
    residual = simplify(residual - coefficientExpression * sym(signalName));
end

if ~isempty(symvar(residual))
    isAffine = false;
    affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
    return;
end

try
    residualValue = double(residual);
catch
    isAffine = false;
    affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
    return;
end

if abs(residualValue) > 1e-12
    isAffine = false;
    affine = struct("constant", 0.0, "terms", struct("name", {}, "coefficient", {}));
    return;
end

isAffine = true;
affine = struct("constant", constantValue, "terms", terms);
end

function position = localAffineAuxPosition(rhsPosition, offsetIndex)
x1 = rhsPosition(1) - 130;
x2 = rhsPosition(1) - 50;
y1 = rhsPosition(2) + 8 + 28 * offsetIndex;
y2 = y1 + 22;
position = [x1 y1 x2 y2];
end

function reference = localBuildMatlabReferenceSimulation(preview, opts, stateNames, modelConfig)
timeVariable = char(string(localScalar(preview, "TimeVariable", "t")));
parameterNames = localOrderedCell(preview, "Parameters");
inputNames = localOrderedCell(preview, "Inputs");
parameterValues = localStruct(opts.RuntimeOverride, "parameter_values");
inputValues = localStruct(opts.RuntimeOverride, "input_values");
inputSpecs = localStruct(opts.RuntimeOverride, "input_specs");
initialConditions = localStruct(opts.RuntimeOverride, "initial_conditions");
referenceTime = localReferenceTimeGrid(modelConfig);
y0 = zeros(numel(stateNames), 1);
for index = 1:numel(stateNames)
    y0(index) = double(localScalar(initialConditions, stateNames{index}, 0));
end

tSym = sym(timeVariable);
stateSyms = localNamedSymbols(stateNames);
inputExpressions = cell(1, numel(inputNames));
for index = 1:numel(inputNames)
    inputExpressions{index} = localInputExpression( ...
        inputNames{index}, ...
        inputValues, ...
        inputSpecs, ...
        tSym);
    for paramIndex = 1:numel(parameterNames)
        paramName = parameterNames{paramIndex};
        inputExpressions{index} = subs(inputExpressions{index}, sym(paramName), double(localScalar(parameterValues, paramName, 0)));
    end
end

stateEquations = preview.FirstOrderPreview.StateEquations;
rhsExpressions = sym(zeros(numel(stateNames), 1));
for index = 1:numel(stateNames)
    rhsText = localStateEquationRhs(stateEquations, stateNames{index});
    rhsExpression = str2sym(rhsText);
    for inputIndex = 1:numel(inputNames)
        rhsExpression = subs(rhsExpression, sym(inputNames{inputIndex}), inputExpressions{inputIndex});
    end
    for paramIndex = 1:numel(parameterNames)
        paramName = parameterNames{paramIndex};
        rhsExpression = subs(rhsExpression, sym(paramName), double(localScalar(parameterValues, paramName, 0)));
    end
    rhsExpressions(index) = rhsExpression;
end

solverName = localResolvedReferenceSolver(modelConfig.Solver);
solverHandle = str2func(solverName);
solverOptions = localReferenceSolverOptions(modelConfig);
rhsHandle = matlabFunction(rhsExpressions, "Vars", [{tSym}, num2cell(stateSyms)]);
odeRhs = @(t, y) localEvaluateStateVector(rhsHandle, t, y);

if isempty(solverOptions)
    [solverTime, solverStates] = solverHandle(odeRhs, referenceTime, y0);
else
    [solverTime, solverStates] = solverHandle(odeRhs, referenceTime, y0, solverOptions);
end

alignedStates = localAlignStateSamples(referenceTime, double(solverTime(:)), double(solverStates));
signals = struct();
for index = 1:numel(stateNames)
    signals.(matlab.lang.makeValidName(stateNames{index})) = alignedStates(:, index);
end

reference = struct( ...
    "t", referenceTime, ...
    "states", alignedStates, ...
    "state_names", {reshape(stateNames, 1, [])}, ...
    "signals", signals, ...
    "reference_kind", "matlab_ode", ...
    "reference_solver", solverName, ...
    "solver_t", double(solverTime(:)), ...
    "solver_states", double(solverStates) ...
);
end

function expression = localInputExpression(inputName, inputValues, inputSpecs, timeSymbol)
if isfield(inputValues, inputName)
    expression = sym(double(localScalar(inputValues, inputName, 0)));
    return;
end

if ~isfield(inputSpecs, inputName)
    expression = sym(0);
    return;
end

spec = inputSpecs.(inputName);
kind = lower(char(string(localScalar(spec, "kind", "expression"))));
switch kind
    case "constant"
        expression = sym(double(localScalar(spec, "value", 0)));
    case "time"
        expression = timeSymbol;
    case "step"
        before = double(localScalar(spec, "bias", localScalar(spec, "initial_value", 0)));
        amplitude = double(localScalar(spec, "amplitude", localScalar(spec, "final_value", 1) - before));
        after = before + amplitude;
        stepTime = double(localScalar(spec, "step_time", localScalar(spec, "start_time", 0)));
        expression = sym(before) + sym(after - before) * heaviside(timeSymbol - sym(stepTime));
    case "pulse"
        amplitude = double(localScalar(spec, "amplitude", localScalar(spec, "value", 1)));
        startTime = double(localScalar(spec, "start_time", 0));
        width = double(localScalar(spec, "width", 0.1));
        bias = double(localScalar(spec, "bias", 0));
        expression = sym(bias) + sym(amplitude) * ( ...
            heaviside(timeSymbol - sym(startTime)) - heaviside(timeSymbol - sym(startTime + width)));
    case "ramp"
        slope = double(localScalar(spec, "slope", 1));
        startTime = double(localScalar(spec, "start_time", 0));
        initialOutput = double(localScalar(spec, "initial_output", 0));
        expression = sym(initialOutput) + sym(slope) * (timeSymbol - sym(startTime)) * heaviside(timeSymbol - sym(startTime));
    case "sine"
        amplitude = double(localScalar(spec, "amplitude", 1));
        frequency = double(localScalar(spec, "frequency", localScalar(spec, "omega", 1)));
        phase = double(localScalar(spec, "phase", 0));
        bias = double(localScalar(spec, "bias", 0));
        expression = sym(bias) + sym(amplitude) * sin(sym(frequency) * timeSymbol + sym(phase));
    case "square"
        amplitude = double(localScalar(spec, "amplitude", 1));
        frequency = double(localScalar(spec, "frequency", localScalar(spec, "omega", 1)));
        phase = double(localScalar(spec, "phase", 0));
        bias = double(localScalar(spec, "bias", 0));
        expression = sym(bias) + sym(amplitude) * sign(sin(sym(frequency) * timeSymbol + sym(phase)));
    case {"sawtooth", "triangle"}
        amplitude = double(localScalar(spec, "amplitude", 1));
        frequency = double(localScalar(spec, "frequency", localScalar(spec, "omega", 1)));
        phase = double(localScalar(spec, "phase", 0));
        bias = double(localScalar(spec, "bias", 0));
        width = double(localScalar(spec, "width", 0.5));
        if strcmp(kind, "sawtooth")
            width = double(localScalar(spec, "width", 1.0));
        end
        wave = localSawtoothSymbolicWave(timeSymbol, frequency, phase, width);
        expression = sym(bias) + sym(amplitude) * wave;
    case "saturation"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        lowerLimit = double(localScalar(spec, "lower_limit", -1));
        upperLimit = double(localScalar(spec, "upper_limit", 1));
        expression = min(max(innerExpression, sym(lowerLimit)), sym(upperLimit));
    case "dead_zone"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        lowerLimit = double(localScalar(spec, "lower_limit", -1));
        upperLimit = double(localScalar(spec, "upper_limit", 1));
        expression = max(innerExpression - sym(upperLimit), sym(0)) + ...
            min(innerExpression - sym(lowerLimit), sym(0));
    case "sign"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = sign(innerExpression);
    case "abs"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = abs(innerExpression);
    case "minmax"
        inputAName = [inputName '_a'];
        inputBName = [inputName '_b'];
        innerSpecs = struct();
        innerSpecs.(inputAName) = localScalar(spec, "input_a", struct("kind", "constant", "value", 0));
        innerSpecs.(inputBName) = localScalar(spec, "input_b", struct("kind", "constant", "value", 0));
        inputAExpression = localInputExpression(inputAName, struct(), innerSpecs, timeSymbol);
        inputBExpression = localInputExpression(inputBName, struct(), innerSpecs, timeSymbol);
        if strcmpi(char(string(localScalar(spec, "function", "max"))), "min")
            expression = min(inputAExpression, inputBExpression);
        else
            expression = max(inputAExpression, inputBExpression);
        end
    case "affine"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = sym(double(localScalar(spec, "bias", 0))) + ...
            sym(double(localScalar(spec, "gain", 1))) * innerExpression;
    case "atan"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = atan(innerExpression);
    case "atan2"
        inputAName = [inputName '_a'];
        inputBName = [inputName '_b'];
        innerSpecs = struct();
        innerSpecs.(inputAName) = localScalar(spec, "input_a", struct("kind", "constant", "value", 0));
        innerSpecs.(inputBName) = localScalar(spec, "input_b", struct("kind", "constant", "value", 0));
        inputAExpression = localInputExpression(inputAName, struct(), innerSpecs, timeSymbol);
        inputBExpression = localInputExpression(inputBName, struct(), innerSpecs, timeSymbol);
        expression = atan2(inputAExpression, inputBExpression);
    case "exp"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = exp(innerExpression);
    case "log"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = log(innerExpression);
    case "sqrt"
        innerName = [inputName '_inner'];
        innerSpecs = struct();
        innerSpecs.(innerName) = localScalar(spec, "input", struct("kind", "time"));
        innerExpression = localInputExpression(innerName, struct(), innerSpecs, timeSymbol);
        expression = sqrt(innerExpression);
    case "expression"
        expressionText = char(string(localScalar(spec, "expression", "0")));
        recognizedSpec = simucopilot.internal.recognizeExpressionInputSpec(expressionText, char(string(timeSymbol)));
        if ~isempty(recognizedSpec)
            innerSpecs = struct();
            innerSpecs.(inputName) = recognizedSpec;
            expression = localInputExpression(inputName, struct(), innerSpecs, timeSymbol);
            return;
        end
        [isStep, stepPayload] = localExpressionIsStep(expressionText, char(string(timeSymbol)));
        if isStep
            before = double(stepPayload.before);
            after = double(stepPayload.after);
            stepTime = double(stepPayload.step_time);
            expression = sym(before) + sym(after - before) * heaviside(timeSymbol - sym(stepTime));
            return;
        end
        [isPulse, pulsePayload] = localExpressionIsPulse(expressionText, char(string(timeSymbol)), [0, 1]);
        if isPulse
            amplitude = double(pulsePayload.amplitude);
            startTime = double(pulsePayload.start_time);
            width = double(pulsePayload.width);
            expression = sym(amplitude) * ( ...
                heaviside(timeSymbol - sym(startTime)) - heaviside(timeSymbol - sym(startTime + width)));
            return;
        end
        [isRamp, rampPayload] = localExpressionIsRamp(expressionText, char(string(timeSymbol)));
        if isRamp
            slope = double(rampPayload.slope);
            startTime = double(rampPayload.start_time);
            initialOutput = double(rampPayload.initial_output);
            expression = sym(initialOutput) + sym(slope) * (timeSymbol - sym(startTime)) * heaviside(timeSymbol - sym(startTime));
            return;
        end
        [isSine, sinePayload] = localExpressionIsSineWave(expressionText, char(string(timeSymbol)));
        if isSine
            expression = sym(double(sinePayload.bias)) + sym(double(sinePayload.amplitude)) * ...
                sin(sym(double(sinePayload.frequency)) * timeSymbol + sym(double(sinePayload.phase)));
            return;
        end
        [isSquare, squarePayload] = localExpressionIsSquareWave(expressionText, char(string(timeSymbol)));
        if isSquare
            expression = sym(double(squarePayload.bias)) + sym(double(squarePayload.amplitude)) * ...
                sign(sin(sym(double(squarePayload.frequency)) * timeSymbol + sym(double(squarePayload.phase))));
            return;
        end
        [isRepeating, repeatingPayload] = localExpressionIsRepeatingSequenceWave(expressionText, char(string(timeSymbol)));
        if isRepeating
            wave = localSawtoothSymbolicWave( ...
                timeSymbol, ...
                double(repeatingPayload.frequency), ...
                double(repeatingPayload.phase), ...
                double(repeatingPayload.width));
            expression = sym(double(repeatingPayload.bias)) + sym(double(repeatingPayload.amplitude)) * wave;
            return;
        end
        expression = str2sym(expressionText);
    otherwise
        if isfield(spec, "expression")
            expression = str2sym(char(string(spec.expression)));
        else
            error("matlabv2native:UnsupportedReferenceInputSpec", ...
                "Unsupported reference input spec kind '%s' for input '%s'.", kind, inputName);
        end
end

function wave = localSawtoothSymbolicWave(timeSymbol, frequency, phase, width)
argument = sym(frequency) * timeSymbol + sym(phase);
cycle = mod(argument, sym(2) * sym(pi)) / (sym(2) * sym(pi));
if width >= 1.0 - 1e-12
    wave = sym(2) * cycle - sym(1);
    return;
end
if abs(width - 0.5) <= 1e-12
    wave = sym(1) - sym(4) * abs(cycle - sym(0.5));
    return;
end

widthSym = sym(width);
wave = piecewise( ...
    cycle < widthSym, sym(2) * cycle / widthSym - sym(1), ...
    sym(1) - sym(2) * (cycle - widthSym) / (sym(1) - widthSym));
end
end

function rhsText = localStateEquationRhs(stateEquations, stateName)
rhsText = "";
for index = 1:numel(stateEquations)
    if strcmp(char(string(stateEquations(index).state)), char(string(stateName)))
        rhsText = char(string(stateEquations(index).rhs));
        return;
    end
end
error("matlabv2native:MissingReferenceStateEquation", ...
    "Missing first-order state equation for '%s' while building the MATLAB reference solve.", stateName);
end

function symbols = localNamedSymbols(names)
symbols = sym.empty(1, 0);
for index = 1:numel(names)
    symbols(1, index) = sym(names{index});
end
end

function values = localEvaluateStateVector(handle, t, y)
args = [{double(t)}, num2cell(double(y(:).'))];
values = handle(args{:});
values = double(values(:));
end

function aligned = localAlignStateSamples(referenceTime, sampleTime, sampleStates)
if isequal(referenceTime, sampleTime)
    aligned = sampleStates;
    return;
end

aligned = zeros(numel(referenceTime), size(sampleStates, 2));
for column = 1:size(sampleStates, 2)
    aligned(:, column) = interp1(sampleTime, sampleStates(:, column), referenceTime, "linear", "extrap");
end
end

function solverName = localResolvedReferenceSolver(configuredSolver)
token = lower(strtrim(char(string(configuredSolver))));
switch token
    case {"ode15s", "ode45", "ode23", "ode23s", "ode23t", "ode113"}
        solverName = token;
    otherwise
        solverName = "ode45";
end
end

function solverOptions = localReferenceSolverOptions(modelConfig)
nameValue = {};
relTol = localMinPositive(str2double(char(string(modelConfig.RelTol))), 1e-9);
absTol = localMinPositive(str2double(char(string(modelConfig.AbsTol))), 1e-12);
nameValue = [nameValue, {"RelTol", relTol, "AbsTol", absTol}]; %#ok<AGROW>
maxStep = str2double(char(string(modelConfig.MaxStep)));
if ~isnan(maxStep) && maxStep > 0
    nameValue = [nameValue, {"MaxStep", maxStep}]; %#ok<AGROW>
end
solverOptions = odeset(nameValue{:});
end

function referenceTime = localReferenceTimeGrid(modelConfig)
if isfield(modelConfig, "OutputTimesVector") && ~isempty(modelConfig.OutputTimesVector)
    referenceTime = double(modelConfig.OutputTimesVector(:));
    return;
end

raw = char(string(localScalar(modelConfig, "OutputTimes", "")));
try
    parsed = str2num(raw); %#ok<ST2NM>
catch
    parsed = [];
end
if ~isempty(parsed)
    referenceTime = double(parsed(:));
    return;
end

startTime = str2double(char(string(localScalar(modelConfig, "StartTime", "0.0"))));
stopTime = str2double(char(string(localScalar(modelConfig, "StopTime", "10.0"))));
referenceTime = linspace(startTime, stopTime, 101).';
end

function value = localMinPositive(parsed, fallback)
if isnan(parsed) || parsed <= 0
    value = fallback;
else
    value = min(parsed, fallback);
end
end

function simulation = localSimulateModel(modelPath, modelName, stateNames)
load_system(modelPath);
simOut = sim(modelName, "ReturnWorkspaceOutputs", "on");
yout = simOut.get("yout");
time = double(yout.time(:));
states = zeros(numel(time), numel(stateNames));
signals = struct();
for index = 1:numel(stateNames)
    values = double(yout.signals(index).values(:));
    states(:, index) = values;
    signals.(matlab.lang.makeValidName(stateNames{index})) = values;
end
simulation = struct( ...
    "t", time, ...
    "states", states, ...
    "state_names", {reshape(stateNames, 1, [])}, ...
    "signals", signals, ...
    "model_name", modelName, ...
    "model_file", modelPath ...
);
close_system(modelName, 0);
end

function comparison = localCompareSimulations(referenceResult, candidateResult, tolerance)
referenceTime = double(referenceResult.t(:));
referenceStates = double(referenceResult.states);
candidateTime = double(candidateResult.t(:));
candidateStates = double(candidateResult.states);
stateNames = reshape(referenceResult.state_names, 1, []);

if size(referenceStates, 2) ~= size(candidateStates, 2)
    error("matlabv2native:StateDimensionMismatch", ...
        "Native/Python comparison requires matching state dimensions.");
end

if isequal(referenceTime, candidateTime)
    alignedCandidate = candidateStates;
else
    alignedCandidate = zeros(numel(referenceTime), size(candidateStates, 2));
    for column = 1:size(candidateStates, 2)
        alignedCandidate(:, column) = interp1(candidateTime, candidateStates(:, column), referenceTime, "linear", "extrap");
    end
end

errorMatrix = referenceStates - alignedCandidate;
rmse = sqrt(mean(errorMatrix(:).^2));
maxAbs = max(abs(errorMatrix(:)));
perStateRmse = struct();
perStateMax = struct();
for index = 1:numel(stateNames)
    field = matlab.lang.makeValidName(stateNames{index});
    perStateRmse.(field) = sqrt(mean(errorMatrix(:, index).^2));
    perStateMax.(field) = max(abs(errorMatrix(:, index)));
end

comparison = struct( ...
    "rmse", rmse, ...
    "max_abs_error", maxAbs, ...
    "per_state_rmse", perStateRmse, ...
    "per_state_max_abs_error", perStateMax, ...
    "tolerance", tolerance, ...
    "passes", rmse < tolerance && maxAbs < tolerance ...
);
end

function parityReport = localAugmentParityReport(parityReport, nativeFamilies, oracleFamilies, matlabReference, nativeVsMatlab, pythonVsMatlab, nativeVsPython, nativeValidation, oracleValidation)
nativeFamilyMatch = localCompareFamilyStructs(nativeFamilies, oracleFamilies);
oraclePasses = localOracleValidationPasses(oracleValidation);

parityReport.Kind = "parity_phase4_matlab_reference";
parityReport.Matches.source_block_family = nativeFamilyMatch;
parityReport.Matches.simulation_traces = logical(nativeVsMatlab.passes) && logical(pythonVsMatlab.passes) && logical(nativeVsPython.passes);
parityReport.Matches.native_vs_matlab_reference = logical(nativeVsMatlab.passes);
parityReport.Matches.python_vs_matlab_reference = logical(pythonVsMatlab.passes);
parityReport.Matches.native_vs_python_delegate = logical(nativeVsPython.passes);
parityReport.Matches.validation_status = logical(nativeValidation.passes);
parityReport.ComparedFields = localUniqueStable([parityReport.ComparedFields, {"source_block_family", "simulation_traces", "native_vs_matlab_reference", "python_vs_matlab_reference", "native_vs_python_delegate", "validation_status"}]);
parityReport.AllComparedFieldsMatch = all(cellfun(@(name) logical(parityReport.Matches.(name)), parityReport.ComparedFields));
parityReport.Native.source_block_family = nativeFamilies;
parityReport.Python.source_block_family = oracleFamilies;
parityReport.Reference = struct( ...
    "kind", matlabReference.reference_kind, ...
    "solver", matlabReference.reference_solver);
parityReport.Native.validation = nativeValidation;
parityReport.Python.validation = struct( ...
    "oracle_validation", oracleValidation, ...
    "vs_matlab_reference", pythonVsMatlab, ...
    "oracle_validation_passes", oraclePasses);
parityReport.Native.lowering_mode = "native_explicit_ode";
parityReport.Python.lowering_mode = "python_delegate";
end

function parityReport = localRuntimeOnlyParityReport(preview, nativeFamilies, matlabReference, nativeValidation)
parityReport = struct();
parityReport.Kind = "runtime_phase5_native_only";
parityReport.Matches = struct( ...
    "native_vs_matlab_reference", logical(nativeValidation.native_vs_matlab_reference.passes), ...
    "validation_status", logical(nativeValidation.passes) ...
);
parityReport.ComparedFields = {"native_vs_matlab_reference", "validation_status"};
parityReport.AllComparedFieldsMatch = all(cellfun(@(name) logical(parityReport.Matches.(name)), parityReport.ComparedFields));
parityReport.Native = struct( ...
    "states", {localOrderedCell(preview, "States")}, ...
    "algebraics", {localOrderedCell(preview, "Algebraics")}, ...
    "inputs", {localOrderedCell(preview, "Inputs")}, ...
    "parameters", {localOrderedCell(preview, "Parameters")}, ...
    "time_variable", char(string(localScalar(preview, "TimeVariable", ""))), ...
    "route", char(string(localScalar(preview, "Route", ""))), ...
    "source_block_family", nativeFamilies, ...
    "validation", nativeValidation, ...
    "lowering_mode", "native_runtime_only" ...
);
parityReport.Reference = struct( ...
    "kind", matlabReference.reference_kind, ...
    "solver", matlabReference.reference_solver ...
);
parityReport.Python = struct( ...
    "lowering_mode", "parity_not_run" ...
);
parityReport.UncomparedFields = {"source_block_family", "python_parity", "generated_block_structure"};
parityReport.DelegatedFields = localOrderedCell(preview, "DelegatedFields");
end

function families = localSourceBlockFamiliesForModel(modelPath, modelName, inputNames)
families = struct();
load_system(modelPath);
cleanupModel = onCleanup(@() localBestEffortClose(modelName));
for index = 1:numel(inputNames)
    inputName = inputNames{index};
    family = localInputFamilyForModel(modelName, inputName);
    if strlength(string(family)) == 0
        continue;
    end
    families.(inputName) = family;
end
clear cleanupModel
close_system(modelName, 0);
end

function family = localInputFamilyForModel(modelName, inputName)
family = "";
blockPath = [modelName '/' inputName];
handle = getSimulinkBlockHandle(blockPath);
if isnumeric(handle) && handle > 0
    baseFamily = localBlockFamily(blockPath);
    sourcePath = [modelName '/' inputName '_src'];
    sourceHandle = getSimulinkBlockHandle(sourcePath);
    if strcmp(baseFamily, "TransportDelay") && isnumeric(sourceHandle) && sourceHandle > 0
        sourceFamily = localBlockFamily(sourcePath);
        if strcmp(sourceFamily, "RepeatingSequence")
            family = "RepeatingSequence";
            return;
        end
    end
    family = baseFamily;
    return;
end

signPath = [modelName '/' inputName '_sign'];
sourcePath = [modelName '/' inputName '_src'];
signHandle = getSimulinkBlockHandle(signPath);
sourceHandle = getSimulinkBlockHandle(sourcePath);
if isnumeric(signHandle) && signHandle > 0 && isnumeric(sourceHandle) && sourceHandle > 0
    if strcmp(localBlockFamily(signPath), "Sign") && strcmp(localBlockFamily(sourcePath), "SineWave")
        family = "SquareWave";
    end
end
end

function family = localBlockFamily(blockPath)
blockType = char(string(get_param(blockPath, "BlockType")));
if strcmp(blockType, "SubSystem")
    try
        maskType = char(string(get_param(blockPath, "MaskType")));
        if strcmp(maskType, "Ramp")
            family = "Ramp";
            return;
        end
    catch
        % Fall through to other subsystem detection.
    end
    try
        sfType = char(string(get_param(blockPath, "SFBlockType")));
        if strcmp(sfType, "MATLAB Function")
            family = "MATLAB Function";
            return;
        end
    catch
        % Fall through to BlockType.
    end
end
if strcmp(blockType, "DiscretePulseGenerator")
    family = "PulseGenerator";
    return;
end
if strcmp(blockType, "Sin")
    family = "SineWave";
    return;
end
if strcmp(blockType, "Signum")
    family = "Sign";
    return;
end
if strcmp(blockType, "Trigonometry") || strcmp(blockType, "TrigonometricFunction")
    family = "TrigonometricFunction";
    return;
end
if strcmp(blockType, "Math") || strcmp(blockType, "MathFunction")
    family = "MathFunction";
    return;
end
if strcmp(blockType, "RepeatingSequenceInterpolated")
    family = "RepeatingSequence";
    return;
end
family = blockType;
end

function config = localReadModelConfig(modelPath, modelName)
load_system(modelPath);
config = struct( ...
    "StartTime", char(string(get_param(modelName, "StartTime"))), ...
    "StopTime", char(string(get_param(modelName, "StopTime"))), ...
    "Solver", char(string(get_param(modelName, "Solver"))), ...
    "RelTol", char(string(get_param(modelName, "RelTol"))), ...
    "AbsTol", char(string(get_param(modelName, "AbsTol"))), ...
    "MaxStep", char(string(get_param(modelName, "MaxStep"))), ...
    "OutputOption", char(string(get_param(modelName, "OutputOption"))), ...
    "OutputTimes", char(string(get_param(modelName, "OutputTimes"))), ...
    "OutputTimesVector", [], ...
    "SaveOutput", char(string(get_param(modelName, "SaveOutput"))), ...
    "OutputSaveName", char(string(get_param(modelName, "OutputSaveName"))), ...
    "SaveFormat", char(string(get_param(modelName, "SaveFormat"))) ...
);
end

function localApplyModelConfig(modelName, config)
set_param(modelName, ...
    "StartTime", config.StartTime, ...
    "StopTime", config.StopTime, ...
    "Solver", config.Solver, ...
    "RelTol", config.RelTol, ...
    "AbsTol", config.AbsTol, ...
    "MaxStep", config.MaxStep, ...
    "OutputOption", config.OutputOption, ...
    "OutputTimes", config.OutputTimes, ...
    "SaveOutput", "on", ...
    "OutputSaveName", "yout", ...
    "SaveFormat", "StructureWithTime");
end

function positions = localLayoutPlan(numInputs, numParameters, numStates)
inputCount = max(numInputs, 1);
paramCount = max(numParameters, 1);
stateCount = max(numStates, 1);

positions.inputs = zeros(inputCount, 4);
for index = 1:inputCount
    y = 80 + 90 * (index - 1);
    positions.inputs(index, :) = [40 y 140 y + 40];
end

positions.parameters = zeros(paramCount, 4);
for index = 1:paramCount
    y = 220 + 80 * (index - 1);
    positions.parameters(index, :) = [40 y 140 y + 40];
end

positions.rhs = zeros(stateCount, 4);
positions.integrators = zeros(stateCount, 4);
positions.outputs = zeros(stateCount, 4);
for index = 1:stateCount
    y = 80 + 120 * (index - 1);
    positions.rhs(index, :) = [330 y 470 y + 60];
    positions.integrators(index, :) = [610 y + 10 650 y + 40];
    positions.outputs(index, :) = [860 y + 10 890 y + 30];
end
end

function outputDir = localResolvedOutputDir(opts)
if ~isempty(strtrim(char(string(opts.SimulinkOutputDir))))
    outputDir = char(string(opts.SimulinkOutputDir));
    return;
end
outputDir = fullfile(opts.RepoRoot, "workspace", "bedillion_demo");
end

function value = localResolvedModelName(rawModelName)
modelName = strtrim(char(string(rawModelName)));
if isempty(modelName)
    value = "matlabv2native_explicit_ode";
else
    value = matlab.lang.makeValidName(modelName);
end
value = char(string(value));
end

function config = localDefaultModelConfig(opts)
runtimeOverride = localStruct(opts, "RuntimeOverride");
tEval = [];
if isfield(runtimeOverride, "t_eval") && ~isempty(runtimeOverride.t_eval)
    tEval = double(runtimeOverride.t_eval(:));
elseif isfield(runtimeOverride, "t_span") && numel(runtimeOverride.t_span) == 2
    rawSpan = double(runtimeOverride.t_span(:));
    sampleCount = 101;
    if isfield(runtimeOverride, "sample_count") && isnumeric(runtimeOverride.sample_count) && isscalar(runtimeOverride.sample_count)
        sampleCount = max(2, round(double(runtimeOverride.sample_count)));
    end
    tEval = linspace(rawSpan(1), rawSpan(2), sampleCount).';
else
    tEval = linspace(0.0, 10.0, 101).';
end

if numel(tEval) < 2
    error("matlabv2native:InvalidRuntimeGrid", ...
        "Native runtime requires a t_eval grid with at least two samples.");
end

tSpan = [double(tEval(1)), double(tEval(end))];
maxStep = max(min(diff(tEval)), eps);
config = struct( ...
    "StartTime", num2str(tSpan(1), 17), ...
    "StopTime", num2str(tSpan(2), 17), ...
    "Solver", "ode45", ...
    "RelTol", "1e-9", ...
    "AbsTol", "1e-12", ...
    "MaxStep", num2str(maxStep, 17), ...
    "OutputOption", "SpecifiedOutputTimes", ...
    "OutputTimes", mat2str(tEval(:).', 17), ...
    "OutputTimesVector", tEval(:), ...
    "SaveOutput", "on", ...
    "OutputSaveName", "yout", ...
    "SaveFormat", "StructureWithTime" ...
);
end

function tolerance = localResolvedTolerance(opts)
if isempty(opts.Tolerance)
    tolerance = 1e-6;
else
    tolerance = double(opts.Tolerance);
end
end

function pattern = localNumberPattern()
pattern = '[-+]?(?:[0-9]*\\.?[0-9]+|[0-9]+/[0-9]+)';
end

function value = localNumericTokenToDouble(token)
value = double(vpa(str2sym(char(string(token)))));
end

function value = localDefaultPulsePeriodFromSpan(startTime, width, tSpan)
simulationEnd = double(tSpan(2));
value = max(width * 2.0, (simulationEnd - startTime) + width + max(width, 1.0));
end

function period = localPeriodicSourcePeriod(frequency)
if abs(frequency) <= 1e-12
    error("matlabv2native:InvalidPeriodicFrequency", ...
        "Native periodic input frequency must be non-zero.");
end
period = abs((2.0 * pi) / double(frequency));
end

function [times, values] = localRepeatingSequencePoints(period, amplitude, bias, width)
normalizedWidth = min(max(double(width), 1e-6), 1.0);
if normalizedWidth >= 1.0 - 1e-12
    epsilon = max(period * 1e-9, 1e-9);
    times = [0.0, max(period - epsilon, 0.0), period];
    values = [bias - amplitude, bias + amplitude, bias - amplitude];
    return;
end
riseTime = normalizedWidth * period;
times = [0.0, riseTime, period];
values = [bias - amplitude, bias + amplitude, bias - amplitude];
end

function delayTime = localPeriodicPhaseDelay(frequency, phase)
period = localPeriodicSourcePeriod(frequency);
delayTime = mod((-double(phase) / double(frequency)), period);
if delayTime < 0.0
    delayTime = delayTime + period;
end
end

function tSpan = localModelConfigSpan(modelConfig)
startTime = str2double(char(string(localScalar(modelConfig, "StartTime", "0.0"))));
stopTime = str2double(char(string(localScalar(modelConfig, "StopTime", "10.0"))));
tSpan = [startTime, stopTime];
end

function mode = localInvocationParityMode(invocation)
if isstruct(invocation) && isfield(invocation, "ParityMode") && ~isempty(invocation.ParityMode)
    mode = char(string(invocation.ParityMode));
else
    mode = "runtime";
end
end

function tf = localOracleValidationPasses(validation)
tf = false;
if ~isstruct(validation) || ~isfield(validation, "simulink_validation")
    return;
end
simValidation = validation.simulink_validation;
if ~isstruct(simValidation) || ~isfield(simValidation, "passes")
    return;
end
tf = logical(simValidation.passes);
end

function publicOptions = localPublicOptions(opts)
publicOptions = struct( ...
    "States", {opts.States}, ...
    "Algebraics", {opts.Algebraics}, ...
    "Inputs", {opts.Inputs}, ...
    "Parameters", {opts.Parameters}, ...
    "TimeVariable", opts.TimeVariable, ...
    "NativeRhsStyle", opts.NativeRhsStyle, ...
    "ModelName", opts.ModelName, ...
    "OpenModel", opts.OpenModel ...
);
end

function rhsStyle = localResolvedNativeRhsStyle(opts)
rhsStyle = char(string(localScalar(opts, "NativeRhsStyle", "subsystem_native")));
end

function problem = localNormalizedProblemFromPreview(preview)
problem = struct( ...
    "states", {localOrderedCell(preview, "States")}, ...
    "algebraics", {localOrderedCell(preview, "Algebraics")}, ...
    "inputs", {localOrderedCell(preview, "Inputs")}, ...
    "parameters", {localOrderedCell(preview, "Parameters")}, ...
    "time_variable", char(string(localScalar(preview, "TimeVariable", ""))) ...
);
end

function firstOrder = localFirstOrderFromPreview(preview)
firstPreview = localStruct(preview, "FirstOrderPreview");
stateEquations = struct("state", {}, "rhs", {});
if isfield(firstPreview, "StateEquations")
    stateEquations = firstPreview.StateEquations;
end
firstOrder = struct( ...
    "states", {localOrderedCell(firstPreview, "States")}, ...
    "inputs", {localOrderedCell(firstPreview, "Inputs")}, ...
    "parameters", {localOrderedCell(firstPreview, "Parameters")}, ...
    "state_equations", stateEquations ...
);
end

function values = localOrderedCell(container, fieldName)
if isstruct(container) && isfield(container, fieldName)
    raw = container.(fieldName);
else
    raw = {};
end
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
    values = reshape(cellfun(@(item) char(string(item)), raw, "UniformOutput", false), 1, []);
    return;
end
values = {char(string(raw))};
end

function value = localScalar(container, fieldName, fallback)
if isstruct(container) && isfield(container, fieldName)
    value = container.(fieldName);
else
    value = fallback;
end
end

function values = localUniqueStable(values)
if isempty(values)
    values = {};
    return;
end
values = reshape(cellfun(@(item) char(string(item)), values, "UniformOutput", false), 1, []);
values = unique(values, "stable");
end

function value = localStruct(container, fieldName)
if isstruct(container) && isfield(container, fieldName) && isstruct(container.(fieldName))
    value = container.(fieldName);
else
    value = struct();
end
end

function pairs = localStructNameValuePairs(values)
fields = fieldnames(values);
pairs = cell(1, numel(fields) * 2);
for index = 1:numel(fields)
    pairs{(index - 1) * 2 + 1} = fields{index};
    pairs{(index - 1) * 2 + 2} = values.(fields{index});
end
end

function tf = localCompareFamilyStructs(nativeFamilies, oracleFamilies)
nativeNames = sort(fieldnames(nativeFamilies));
oracleNames = sort(fieldnames(oracleFamilies));
if ~isequal(nativeNames, oracleNames)
    tf = false;
    return;
end
tf = true;
for index = 1:numel(nativeNames)
    name = nativeNames{index};
    if ~localFamiliesSemanticallyMatch(nativeFamilies.(name), oracleFamilies.(name))
        tf = false;
        return;
    end
end
end

function tf = localFamiliesSemanticallyMatch(nativeFamily, oracleFamily)
nativeText = char(string(nativeFamily));
oracleText = char(string(oracleFamily));
if strcmp(nativeText, oracleText)
    tf = true;
    return;
end

equivalentPairs = {
    "SquareWave", "Sum"
};
tf = false;
for index = 1:size(equivalentPairs, 1)
    lhs = char(equivalentPairs{index, 1});
    rhs = char(equivalentPairs{index, 2});
    if (strcmp(nativeText, lhs) && strcmp(oracleText, rhs)) || ...
            (strcmp(nativeText, rhs) && strcmp(oracleText, lhs))
        tf = true;
        return;
    end
end
end

function token = localSanitize(name)
token = regexprep(char(string(name)), "[^A-Za-z0-9_]", "_");
end

function text = localNumericString(value)
text = num2str(double(value), 17);
end

function localBestEffortClose(modelName)
if bdIsLoaded(modelName)
    try
        close_system(modelName, 0);
    catch
        % Best effort cleanup only.
    end
end
end
