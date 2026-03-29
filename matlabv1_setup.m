function info = matlabv1_setup(varargin)
% matlabv1_setup Bootstrap the matlabv1 MATLAB API from the repo root.
%
% Usage:
%   info = matlabv1_setup()
%   info = matlabv1_setup("SavePath", true)

repoRoot = fileparts(mfilename("fullpath"));
matlabRoot = fullfile(repoRoot, "matlab");
addpath(genpath(matlabRoot));

info = setupEqn2Sim(varargin{:});
info.Api = "matlabv1";
end
