function snapshot = captureCallerWorkspace()
% captureCallerWorkspace Capture the wrapper caller workspace into a struct.

snapshot = simucopilot.internal.callerWorkspaceSnapshot(2);
end
