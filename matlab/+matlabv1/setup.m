function info = setup(varargin)
% matlabv1.setup Add the MATLAB bridge and matlabv1 package to the MATLAB path.

info = setupEqn2Sim(varargin{:});
info.Api = "matlabv1";
end
