function equations = equationTexts(primaryInput)
% equationTexts Convert supported MATLAB inputs into a cell array of equation strings.

if isa(primaryInput, "symfun")
    primaryInput = formula(primaryInput);
end
if isa(primaryInput, "sym")
    equations = cellstr(string(primaryInput(:)));
    return;
end
if ischar(primaryInput)
    equations = {char(primaryInput)};
    return;
end
if isstring(primaryInput)
    equations = cellstr(primaryInput(:).');
    return;
end
if iscell(primaryInput)
    equations = cellfun(@localCharString, primaryInput, "UniformOutput", false);
    return;
end
equations = {};
end

function value = localCharString(item)
if isa(item, "sym")
    value = char(item);
    return;
end
value = char(string(item));
end
