function varargout = frontDoorSupport(action, varargin)
% frontDoorSupport Shared helpers for matlabv2native front-door validation, readouts, and diagnostics.

action = char(string(action));
switch action
    case "build_readout"
        varargout{1} = localBuildReadout(varargin{:});
    case "validate_contract"
        [varargout{1}, varargout{2}] = localValidateContract(varargin{:});
    case "attach_preview"
        varargout{1} = localAttachPreview(varargin{:});
    case "validate_state_binding"
        varargout{1} = localValidateStateBinding(varargin{:});
    case "attach_outcome"
        varargout{1} = localAttachOutcome(varargin{:});
    case "diagnose"
        varargout{1} = localDiagnose(varargin{:});
    case "raise"
        localRaise(varargin{:});
    case "raise_unexpected"
        localRaiseUnexpected(varargin{:});
    case "is_diagnostic_identifier"
        varargout{1} = localIsDiagnosticIdentifier(varargin{:});
    otherwise
        error("matlabv2native:UnknownFrontDoorAction", ...
            "Unknown matlabv2native front-door helper action '%s'.", action);
end
end

function readout = localBuildReadout(sourceType, primaryInput, opts)
sourceType = char(string(sourceType));
readout = struct( ...
    "FrontDoor", sourceType, ...
    "SourceType", sourceType, ...
    "RepresentationKind", localRepresentationKind(primaryInput), ...
    "ScalarizedEquationCount", double(numel(matlabv2native.internal.equationTexts(primaryInput))), ...
    "DeclaredStates", {localToCellstr(localScalar(opts, "States", {}))}, ...
    "BoundStates", {{}}, ...
    "Algebraics", {localToCellstr(localScalar(opts, "Algebraics", {}))}, ...
    "Inputs", {localToCellstr(localScalar(opts, "Inputs", {}))}, ...
    "Parameters", {localToCellstr(localScalar(opts, "Parameters", {}))}, ...
    "TimeVariable", char(string(localScalar(opts, "TimeVariable", ""))), ...
    "Route", "", ...
    "RouteStatus", "", ...
    "NativeEligible", false, ...
    "NativeEligibilityReason", "", ...
    "FallbackUsed", false, ...
    "Delegated", false, ...
    "SupportStatus", "", ...
    "DelegationReason", "", ...
    "NativeSourceBlockFamilies", struct(), ...
    "UnderlyingErrorIdentifier", "", ...
    "UnderlyingErrorMessage", "", ...
    "FailedStage", "", ...
    "Stages", localInitialStages() ...
);
readout.Stages.source_type_validation = "passed";
end

function [opts, readout] = localValidateContract(sourceType, opts, readout)
sourceType = char(string(sourceType));
readout.Stages.option_validation = "running";
if ~strcmp(sourceType, "matlab_symbolic")
    readout.Stages.option_validation = "passed";
    return;
end

states = localNormalizeDeclaredStates(localScalar(opts, "States", {}));
algebraics = localNormalizeDeclaredStates(localScalar(opts, "Algebraics", {}));
inputs = localNormalizeDeclaredStates(localScalar(opts, "Inputs", {}));
parameters = localNormalizeDeclaredStates(localScalar(opts, "Parameters", {}));

if isempty(states)
    diagnostic = localDiagnostic( ...
        "matlabv2native:FrontDoorMissingStateDeclaration", ...
        "option_validation", ...
        "State / States is required for matlab_symbolic.", ...
        "matlabv2native requires an explicit ordered state list for MATLAB symbolic input so state ownership and ordering stay deterministic.", ...
        "No State or States option was provided.", ...
        "Pass 'State', 'x' for a scalar system or 'State', {'x','theta'} for a multi-state system.", ...
        "unsupported", ...
        readout);
    localRaise(diagnostic);
end

if numel(unique(states, "stable")) ~= numel(states)
    diagnostic = localDiagnostic( ...
        "matlabv2native:FrontDoorDuplicateStateNames", ...
        "option_validation", ...
        "Declared state names must be unique.", ...
        "The State / States list contains duplicates, which makes front-door binding ambiguous.", ...
        "The same state name was declared more than once.", ...
        "Remove duplicate names so State / States contains each original state basis exactly once.", ...
        "unsupported", ...
        localWithField(readout, "DeclaredStates", states));
    localRaise(diagnostic);
end

overlap = intersect(states, algebraics, "stable");
if ~isempty(overlap)
    diagnostic = localDiagnostic( ...
        "matlabv2native:FrontDoorStateAlgebraicOverlap", ...
        "option_validation", ...
        "Declared states cannot also be declared as algebraics.", ...
        "The same symbolic name cannot be both a state and an algebraic variable at the MATLAB-symbolic front door.", ...
        "One or more declared states also appear in Algebraics.", ...
        "Remove the overlap so each symbolic name appears in exactly one role. Overlapping names: " + localList(overlap), ...
        "unsupported", ...
        localWithField(readout, "DeclaredStates", states));
    localRaise(diagnostic);
end

overlap = intersect(states, inputs, "stable");
if ~isempty(overlap)
    diagnostic = localDiagnostic( ...
        "matlabv2native:FrontDoorStateInputOverlap", ...
        "option_validation", ...
        "Declared states cannot also be declared as inputs.", ...
        "The same symbolic name cannot be both a state and an input at the MATLAB-symbolic front door.", ...
        "One or more declared states also appear in Inputs.", ...
        "Remove the overlap so each symbolic name appears in exactly one role. Overlapping names: " + localList(overlap), ...
        "unsupported", ...
        localWithField(readout, "DeclaredStates", states));
    localRaise(diagnostic);
end

overlap = intersect(states, parameters, "stable");
if ~isempty(overlap)
    diagnostic = localDiagnostic( ...
        "matlabv2native:FrontDoorStateParameterOverlap", ...
        "option_validation", ...
        "Declared states cannot also be declared as parameters.", ...
        "The same symbolic name cannot be both a state and a parameter at the MATLAB-symbolic front door.", ...
        "One or more declared states also appear in Parameters.", ...
        "Remove the overlap so each symbolic name appears in exactly one role. Overlapping names: " + localList(overlap), ...
        "unsupported", ...
        localWithField(readout, "DeclaredStates", states));
    localRaise(diagnostic);
end

opts.States = states;
readout.DeclaredStates = states;
readout.Stages.option_validation = "passed";
end

function readout = localAttachPreview(readout, primaryInput, preview)
readout.Stages.symbolic_normalization = "passed";
readout.Stages.route_classification = "passed";
readout.BoundStates = localBoundStateBases(primaryInput, preview);
readout.TimeVariable = char(string(localScalar(preview, "TimeVariable", readout.TimeVariable)));
readout.Route = char(string(localScalar(preview, "Route", "")));
readout.RouteStatus = char(string(localScalar(preview, "RouteStatus", "")));
readout.Delegated = strcmp(readout.RouteStatus, "delegated");
readout.SupportStatus = localSupportStatusFromRoute(readout.RouteStatus);
readout.DelegationReason = localDelegationReason(preview);
end

function readout = localValidateStateBinding(sourceType, primaryInput, opts, preview, readout)
sourceType = char(string(sourceType));
readout.Stages.state_binding = "running";
if ~strcmp(sourceType, "matlab_symbolic")
    readout.Stages.state_binding = "passed";
    return;
end

declared = localNormalizeDeclaredStates(localScalar(opts, "States", {}));
bound = localBoundStateBases(primaryInput, preview);
readout.BoundStates = bound;
if isempty(bound)
    readout.Stages.state_binding = "delegated";
    return;
end

missing = setdiff(bound, declared, "stable");
unexpected = setdiff(declared, bound, "stable");
if ~isempty(missing) || ~isempty(unexpected) || numel(bound) ~= numel(declared)
    [likelyCause, suggestedFix] = localStateBindingAdvice(bound, declared, missing, unexpected);
    diagnostic = localDiagnostic( ...
        "matlabv2native:FrontDoorStateBindingMismatch", ...
        "state_binding", ...
        "Declared State / States does not match the symbolic system.", ...
        "The declared state list must name the original symbolic state basis exactly once and in the intended user-owned order.", ...
        likelyCause, ...
        suggestedFix, ...
        "unsupported", ...
        localWithField(readout, "BoundStates", bound));
    localRaise(diagnostic);
end

readout.Stages.state_binding = "passed";
end

function readout = localAttachOutcome(readout, out, canNativeLower, nativeReason)
if nargin < 3
    canNativeLower = false;
end
if nargin < 4
    nativeReason = "";
end
readout.NativeEligible = logical(canNativeLower);
readout.NativeEligibilityReason = char(string(nativeReason));

backendKind = char(string(localScalar(out, "BackendKind", "")));
readout.Delegated = strcmp(backendKind, "python_delegate");
if readout.Delegated
    readout.SupportStatus = "delegated";
else
    readout.SupportStatus = "supported";
end

if isfield(out, "SourceBlockFamilies") && isstruct(out.SourceBlockFamilies)
    readout.NativeSourceBlockFamilies = out.SourceBlockFamilies;
    readout.FallbackUsed = localHasMatlabFunctionFamily(out.SourceBlockFamilies);
end

readout.Route = char(string(localScalar(out, "Route", readout.Route)));
if isfield(out, "NativePreview") && isstruct(out.NativePreview)
    readout.RouteStatus = char(string(localScalar(out.NativePreview, "RouteStatus", readout.RouteStatus)));
end

readout.Stages.native_eligibility = localStageOutcome(canNativeLower, "delegated");
if readout.Delegated
    readout.Stages.lowering = "delegated";
    readout.Stages.simulation = "delegated";
    readout.Stages.matlab_reference = "delegated";
else
    readout.Stages.lowering = "passed";
    readout.Stages.simulation = "passed";
    readout.Stages.matlab_reference = "passed";
end

parityMode = "";
if isfield(out, "Invocation") && isstruct(out.Invocation) && isfield(out.Invocation, "ParityMode")
    parityMode = char(string(out.Invocation.ParityMode));
end
if strcmp(parityMode, "python")
    readout.Stages.parity = "passed";
else
    readout.Stages.parity = "not_run";
end
end

function diagnosis = localDiagnose(readout)
mode = "deterministic";
if ~isempty(char(string(localScalar(readout, "FailedStage", ""))))
    diagnosis = struct( ...
        "Mode", mode, ...
        "Code", "matlabv2native:FrontDoorFailed", ...
        "Stage", char(string(localScalar(readout, "FailedStage", "unknown"))), ...
        "Summary", "The MATLAB-symbolic front door failed.", ...
        "Details", "Inspect the structured readout and the wrapped diagnostic for the exact failure boundary.", ...
        "LikelyCause", char(string(localScalar(readout, "UnderlyingErrorMessage", "See wrapped error details."))), ...
        "SuggestedFix", "Inspect the front-door diagnostic fields and fix the declared states or unsupported construct identified there.", ...
        "SupportStatus", char(string(localScalar(readout, "SupportStatus", "internal_error"))) ...
    );
    return;
end

if logical(localScalar(readout, "Delegated", false))
    diagnosis = struct( ...
        "Mode", mode, ...
        "Code", "matlabv2native:FrontDoorDelegatedRoute", ...
        "Stage", "route_classification", ...
        "Summary", "The MATLAB-symbolic front door accepted the input but delegated the route.", ...
        "Details", "The problem is outside the current native lowering boundary and was sent down the delegated path.", ...
        "LikelyCause", char(string(localScalar(readout, "DelegationReason", "The route preview remained delegated."))), ...
        "SuggestedFix", "Rewrite the system into a currently supported explicit-ODE or bounded reducible-DAE form, or use the delegated path intentionally.", ...
        "SupportStatus", "delegated" ...
    );
    return;
end

diagnosis = struct( ...
    "Mode", mode, ...
    "Code", "matlabv2native:FrontDoorAccepted", ...
    "Stage", "completed", ...
    "Summary", "The MATLAB-symbolic front door accepted the problem.", ...
    "Details", "The declared states bound cleanly, the route was classified explicitly, and the problem proceeded through the supported path.", ...
    "LikelyCause", "The input used a currently supported MATLAB-symbolic form with a valid explicit state declaration.", ...
    "SuggestedFix", "No fix required.", ...
    "SupportStatus", char(string(localScalar(readout, "SupportStatus", "supported"))) ...
);
end

function localRaise(diagnostic)
identifier = char(string(localScalar(diagnostic, "Code", "matlabv2native:FrontDoorDiagnostic")));
message = localFormatDiagnosticMessage(diagnostic);
throwAsCaller(MException(identifier, "%s", message));
end

function localRaiseUnexpected(stage, exc, readout)
if nargin < 3 || isempty(readout)
    readout = struct();
end
if localIsDiagnosticIdentifier(exc.identifier)
    rethrow(exc);
end
readout = localWithField(readout, "FailedStage", char(string(stage)));
readout = localWithField(readout, "UnderlyingErrorIdentifier", char(string(exc.identifier)));
readout = localWithField(readout, "UnderlyingErrorMessage", char(string(exc.message)));
diagnostic = localDiagnostic( ...
    "matlabv2native:FrontDoorInternalError", ...
    char(string(stage)), ...
    "The MATLAB-symbolic front door hit an internal error.", ...
    "A lower-level MATLAB or backend error escaped the expected front-door diagnostic flow.", ...
    "An internal code path or underlying MATLAB/Simulink operation failed unexpectedly.", ...
    "Inspect UnderlyingErrorIdentifier and UnderlyingErrorMessage in this diagnostic. If the input should be supported, treat this as a backend bug.", ...
    "internal_error", ...
    readout);
diagnostic.UnderlyingErrorIdentifier = char(string(exc.identifier));
diagnostic.UnderlyingErrorMessage = char(string(exc.message));
localRaise(diagnostic);
end

function tf = localIsDiagnosticIdentifier(identifier)
identifier = char(string(identifier));
tf = startsWith(identifier, "matlabv2native:FrontDoor");
end

function diagnostic = localDiagnostic(code, stage, summary, details, likelyCause, suggestedFix, supportStatus, readout)
diagnostic = struct( ...
    "Code", char(string(code)), ...
    "Stage", char(string(stage)), ...
    "Summary", char(string(summary)), ...
    "Details", char(string(details)), ...
    "LikelyCause", char(string(likelyCause)), ...
    "SuggestedFix", char(string(suggestedFix)), ...
    "SupportStatus", char(string(supportStatus)), ...
    "RepresentationKind", char(string(localScalar(readout, "RepresentationKind", ""))), ...
    "DeclaredStates", {localToCellstr(localScalar(readout, "DeclaredStates", {}))}, ...
    "BoundStates", {localToCellstr(localScalar(readout, "BoundStates", {}))}, ...
    "ScalarizedEquationCount", double(localScalar(readout, "ScalarizedEquationCount", 0)), ...
    "Route", char(string(localScalar(readout, "Route", ""))), ...
    "RouteStatus", char(string(localScalar(readout, "RouteStatus", ""))), ...
    "FallbackUsed", logical(localScalar(readout, "FallbackUsed", false)), ...
    "Delegated", logical(localScalar(readout, "Delegated", false)), ...
    "UnderlyingErrorIdentifier", char(string(localScalar(readout, "UnderlyingErrorIdentifier", ""))), ...
    "UnderlyingErrorMessage", char(string(localScalar(readout, "UnderlyingErrorMessage", ""))), ...
    "Readout", readout ...
);
end

function message = localFormatDiagnosticMessage(diagnostic)
lines = { ...
    "[matlabv2native] MATLAB-symbolic front door diagnostic", ...
    "Code: " + string(localScalar(diagnostic, "Code", "")), ...
    "Stage: " + string(localScalar(diagnostic, "Stage", "")), ...
    "Summary: " + string(localScalar(diagnostic, "Summary", "")), ...
    "Details: " + string(localScalar(diagnostic, "Details", "")), ...
    "LikelyCause: " + string(localScalar(diagnostic, "LikelyCause", "")), ...
    "SuggestedFix: " + string(localScalar(diagnostic, "SuggestedFix", "")), ...
    "SupportStatus: " + string(localScalar(diagnostic, "SupportStatus", "")), ...
    "RepresentationKind: " + string(localScalar(diagnostic, "RepresentationKind", "")), ...
    "DeclaredStates: " + localList(localToCellstr(localScalar(diagnostic, "DeclaredStates", {}))), ...
    "BoundStates: " + localList(localToCellstr(localScalar(diagnostic, "BoundStates", {}))), ...
    "ScalarizedEquationCount: " + string(localScalar(diagnostic, "ScalarizedEquationCount", 0)), ...
    "Route: " + string(localScalar(diagnostic, "Route", "")), ...
    "RouteStatus: " + string(localScalar(diagnostic, "RouteStatus", "")) ...
};
underlyingId = char(string(localScalar(diagnostic, "UnderlyingErrorIdentifier", "")));
underlyingMessage = char(string(localScalar(diagnostic, "UnderlyingErrorMessage", "")));
if ~isempty(underlyingId)
    lines{end + 1} = "UnderlyingErrorIdentifier: " + string(underlyingId); %#ok<AGROW>
end
if ~isempty(underlyingMessage)
    lines{end + 1} = "UnderlyingErrorMessage: " + string(underlyingMessage); %#ok<AGROW>
end
message = strjoin(cellstr(string(lines)), newline);
end

function stages = localInitialStages
stages = struct( ...
    "source_type_validation", "not_run", ...
    "option_validation", "not_run", ...
    "caller_capture", "not_run", ...
    "symbolic_normalization", "not_run", ...
    "state_binding", "not_run", ...
    "route_classification", "not_run", ...
    "native_eligibility", "not_run", ...
    "lowering", "not_run", ...
    "simulation", "not_run", ...
    "matlab_reference", "not_run", ...
    "parity", "not_run" ...
);
end

function kind = localRepresentationKind(primaryInput)
if isa(primaryInput, "symfun")
    kind = localSizedKind("symbolic", primaryInput);
    return;
end
if isa(primaryInput, "sym")
    kind = localSizedKind("symbolic", primaryInput);
    return;
end
if iscell(primaryInput)
    kind = "cell";
    return;
end
if isstring(primaryInput)
    kind = localSizedKind("string", primaryInput);
    return;
end
if ischar(primaryInput)
    kind = "char";
    return;
end
kind = string(class(primaryInput));
end

function kind = localSizedKind(prefix, value)
if isscalar(value)
    kind = prefix + "_scalar";
    return;
end
if isvector(value)
    kind = prefix + "_vector";
    return;
end
kind = prefix + "_matrix";
end

function status = localSupportStatusFromRoute(routeStatus)
routeStatus = char(string(routeStatus));
switch routeStatus
    case "native_supported"
        status = "supported";
    case "delegated"
        status = "delegated";
    otherwise
        status = "";
end
end

function reason = localDelegationReason(preview)
reason = "";
notes = {};
if isstruct(preview) && isfield(preview, "Notes")
    notes = localToCellstr(preview.Notes);
end
for index = 1:numel(notes)
    if contains(notes{index}, "delegated", "IgnoreCase", true)
        reason = notes{index};
        return;
    end
end
if isstruct(preview) && isfield(preview, "RouteStatus") && strcmp(char(string(preview.RouteStatus)), "delegated")
    reason = "Native route preview remained delegated.";
end
end

function [likelyCause, suggestedFix] = localStateBindingAdvice(bound, declared, missing, unexpected)
declaredDerivative = any(endsWith(string(unexpected), ["_dot", "_ddot"]) | contains(string(unexpected), "_d"));
if declaredDerivative
    likelyCause = "The declared State / States list appears to use expanded first-order names instead of the original symbolic state basis.";
    suggestedFix = "Declare the original state basis only. Expected bases: " + localList(bound) + ".";
    return;
end

likelyCause = "The declared State / States list does not match the symbolic state basis extracted from the equations.";
parts = {};
if ~isempty(missing)
    parts{end + 1} = "missing bases " + localList(missing); %#ok<AGROW>
end
if ~isempty(unexpected)
    parts{end + 1} = "unexpected bases " + localList(unexpected); %#ok<AGROW>
end
if isempty(parts)
    parts{end + 1} = "expected " + localList(bound) + " but received " + localList(declared); %#ok<AGROW>
end
suggestedFix = "Make State / States exactly match the original symbolic state basis: " + localList(bound) + " (" + strjoin(cellstr(string(parts)), "; ") + ").";
end

function bound = localBoundStateBases(primaryInput, preview)
bound = {};
firstPreview = localStruct(preview, "FirstOrderPreview");
if isstruct(firstPreview) && logical(localScalar(firstPreview, "Available", false))
    canonicalStates = localToCellstr(localScalar(firstPreview, "States", {}));
    bound = localStateBasesFromCanonical(canonicalStates);
    if ~isempty(bound)
        return;
    end
end

previewStates = localToCellstr(localScalar(preview, "States", {}));
if ~isempty(previewStates)
    bound = previewStates;
    return;
end

equations = matlabv2native.internal.equationTexts(primaryInput);
bound = localInferStateBasesFromEquations(equations, char(string(localScalar(preview, "TimeVariable", ""))));
end

function bases = localInferStateBasesFromEquations(equations, timeVariable)
bases = {};
for index = 1:numel(equations)
    matches = regexp(equations{index}, "diff\\((?<state>[A-Za-z][A-Za-z0-9_]*)\\s*,\\s*(?<time>[A-Za-z][A-Za-z0-9_]*)", "names");
    for matchIndex = 1:numel(matches)
        if isempty(timeVariable) || strcmp(matches(matchIndex).time, timeVariable)
            bases{end + 1} = matches(matchIndex).state; %#ok<AGROW>
        end
    end
end
bases = localNormalizeDeclaredStates(bases);
end

function bases = localStateBasesFromCanonical(states)
bases = cell(1, numel(states));
for index = 1:numel(states)
    [bases{index}, ~] = localSplitCanonicalStateName(states{index});
end
bases = unique(bases, "stable");
end

function [base, order] = localSplitCanonicalStateName(name)
token = char(string(name));
token = token(:).';
match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)_ddot$", "names");
if ~isempty(match)
    base = match.base;
    order = 2;
    return;
end

match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)_dot$", "names");
if ~isempty(match)
    base = match.base;
    order = 1;
    return;
end

match = regexp(token, "^(?<base>[A-Za-z][A-Za-z0-9_]*)_d(?<order>[0-9]+)$", "names");
if ~isempty(match)
    base = match.base;
    order = str2double(match.order);
    return;
end

base = token;
order = 0;
end

function values = localNormalizeDeclaredStates(raw)
values = localToCellstr(raw);
for index = 1:numel(values)
    values{index} = strtrim(values{index});
end
values = values(~cellfun(@isempty, values));
end

function tf = localHasMatlabFunctionFamily(families)
tf = false;
if ~isstruct(families)
    return;
end
fields = fieldnames(families);
for index = 1:numel(fields)
    value = char(string(families.(fields{index})));
    if strcmp(value, "MATLAB Function")
        tf = true;
        return;
    end
end
end

function outcome = localStageOutcome(tf, negative)
if logical(tf)
    outcome = "passed";
    return;
end
outcome = char(string(negative));
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
    values = cellfun(@(item) char(string(item)), raw, "UniformOutput", false);
    return;
end
values = {char(string(raw))};
end

function value = localScalar(container, fieldName, defaultValue)
if isstruct(container) && isfield(container, fieldName)
    value = container.(fieldName);
    return;
end
value = defaultValue;
end

function values = localStruct(container, fieldName)
if isstruct(container) && isfield(container, fieldName)
    values = container.(fieldName);
    return;
end
values = struct();
end

function container = localWithField(container, fieldName, value)
container.(fieldName) = value;
end

function rendered = localList(values)
values = localToCellstr(values);
if isempty(values)
    rendered = "{}";
    return;
end
rendered = "{" + strjoin(string(values), ", ") + "}";
end
