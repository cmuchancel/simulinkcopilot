function snapshot = callerWorkspaceSnapshot(depth)
% callerWorkspaceSnapshot Capture the wrapper caller workspace into a struct.

if nargin < 1 || isempty(depth)
    depth = 1;
end
if ~isscalar(depth) || depth < 1 || depth ~= floor(depth)
    error("simucopilot:InvalidWorkspaceSnapshotDepth", ...
        "callerWorkspaceSnapshot depth must be a positive integer scalar.");
end

names = evalin("caller", localCallerExpression("who", depth));
snapshot = struct();
for index = 1:numel(names)
    name = names{index};
    if ~isvarname(name)
        continue;
    end
    try
        escapedName = strrep(char(string(name)), "'", "''");
        snapshot.(name) = evalin("caller", localCallerExpression(escapedName, depth));
    catch
        % Ignore values that cannot be materialized deterministically.
    end
end
end

function expression = localCallerExpression(baseExpression, depth)
expression = char(string(baseExpression));
for index = 1:depth
    expression = sprintf("evalin('caller', '%s')", strrep(expression, "'", "''"));
end
end
