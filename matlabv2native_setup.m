function info = matlabv2native_setup(varargin)
% matlabv2native_setup Bootstrap the matlabv2native MATLAB API from the repo root.
%
% Usage:
%   info = matlabv2native_setup()
%   info = matlabv2native_setup("SavePath", true)

repoRoot = fileparts(mfilename("fullpath"));
matlabRoot = fullfile(repoRoot, "matlab");
addpath(genpath(matlabRoot));

info = setupEqn2Sim(varargin{:});
info.Api = "matlabv2native";
info.BackendKind = "native_phase1_scaffold";
end
