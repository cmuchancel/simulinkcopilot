function info = setupEqn2Sim(varargin)
% setupEqn2Sim Add the repo MATLAB bridge to the MATLAB path.
%
% Usage:
%   info = setupEqn2Sim()
%   info = setupEqn2Sim("SavePath", true)
%
% This function derives the repo location from its own file path so users
% do not have to edit machine-specific addpath(...) calls.

savePath = false;
if nargin >= 1
    for idx = 1:2:numel(varargin)
        name = string(varargin{idx});
        value = varargin{idx + 1};
        if name == "SavePath"
            savePath = logical(value);
        else
            error("simucopilot:UnknownSetupOption", ...
                "Unknown setup option: %s", name);
        end
    end
end

matlabRoot = fileparts(mfilename("fullpath"));
repoRoot = fileparts(matlabRoot);
addpath(genpath(matlabRoot));

if savePath
    savepath();
end

info = struct( ...
    "MatlabRoot", matlabRoot, ...
    "RepoRoot", repoRoot, ...
    "PathSaved", savePath);
end
