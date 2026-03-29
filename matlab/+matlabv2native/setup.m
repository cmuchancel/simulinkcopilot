function info = setup(varargin)
% matlabv2native.setup Add the MATLAB bridge and matlabv2native package to the MATLAB path.

info = setupEqn2Sim(varargin{:});
info.Api = "matlabv2native";
info.BackendKind = "native_phase1_scaffold";
end
