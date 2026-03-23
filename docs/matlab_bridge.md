# MATLAB Bridge

This repo now exposes a first MATLAB-facing bridge layer on top of the existing Python pipeline and existing `matlab.engine`-based Simulink build path.

The bridge is intentionally thin:

1. MATLAB packages a request
2. MATLAB writes request JSON to a temp directory
3. MATLAB calls the Python backend entrypoint
4. Python runs the shared normalization, classification, validation, and lowering pipeline
5. Python optionally builds the `.slx` model through the existing MATLAB engine path
6. Python writes a response JSON file
7. MATLAB parses the response and returns a MATLAB struct

This is a MATLAB front door, not a native MATLAB rewrite of the compiler.

## Public MATLAB Functions

The bridge lives under [matlab/](../matlab/).

Public entrypoints:

- [analyzeEquationSupport.m](../matlab/analyzeEquationSupport.m)
- [generateSimulinkFromLatex.m](../matlab/generateSimulinkFromLatex.m)
- [generateSimulinkFromEquationText.m](../matlab/generateSimulinkFromEquationText.m)
- [generateSimulinkFromSymbolicMatlab.m](../matlab/generateSimulinkFromSymbolicMatlab.m)
- [generateSimulinkFromODEFunction.m](../matlab/generateSimulinkFromODEFunction.m)

Internal helpers:

- [backendDefaults.m](../matlab/+simucopilot/+internal/backendDefaults.m)
- [callBackend.m](../matlab/+simucopilot/+internal/callBackend.m)
- [makeRequestStruct.m](../matlab/+simucopilot/+internal/makeRequestStruct.m)
- [parseBackendResponse.m](../matlab/+simucopilot/+internal/parseBackendResponse.m)
- [validateOptions.m](../matlab/+simucopilot/+internal/validateOptions.m)

## Supported Source Types

The MATLAB bridge exposes the same four front doors as the backend:

- `latex`
- `matlab_symbolic`
- `matlab_equation_text`
- `matlab_ode_function`

These converge to the same normalized IR described in [ir_schema.md](ir_schema.md).

The bridge broadens product access, not math support. DAE support boundaries remain those described in [dae_support.md](dae_support.md).

## Setup

1. Add the bridge folder to the MATLAB path.

Recommended:

```matlab
repoRoot = pwd;
run(fullfile(repoRoot, "matlab", "setupEqn2Sim.m"))
```

If you are already inside the repo:

```matlab
run(fullfile(pwd, "matlab", "setupEqn2Sim.m"))
```

Manual fallback:

```matlab
repoRoot = pwd;
addpath(genpath(fullfile(repoRoot, "matlab")))
```

2. Make sure Python can import the repo modules.

The bridge calls:

```text
python -m pipeline.run_pipeline --request <request.json> --response <response.json>
```

from the repo root.

3. If needed, point MATLAB at a specific Python executable:

```matlab
out = analyzeEquationSupport( ...
    "SourceType","latex", ...
    "Equations","\dot{x} = -x + u", ...
    "PythonExecutable","/usr/bin/python3");
```

The default resolution order is:

- `SIMULINKCOPILOT_PYTHON` environment variable
- fallback to `python3`

## Request / Response Contract

The v1 bridge uses a JSON request/response contract.

Request shape:

```json
{
  "source_type": "matlab_equation_text",
  "equations": ["xdot = z", "0 = z + sin(x)"],
  "states": ["x"],
  "algebraics": ["z"],
  "time_variable": "t",
  "options": {
    "build": false,
    "run_sim": true
  }
}
```

Response shape:

```json
{
  "status": "ok",
  "route": "reducible_semi_explicit_dae",
  "message": "Backend request completed successfully.",
  "diagnostics": [],
  "validation": {...},
  "normalized_problem": {...},
  "generated_model_path": null,
  "model_name": null,
  "artifacts": {...}
}
```

Error responses stay deterministic:

```json
{
  "status": "error",
  "error_code": "opaque_matlab_ode_function",
  "message": "matlab_ode_function currently supports only structured exported RHS expressions, not opaque function handles or arbitrary MATLAB source."
}
```

## Examples

Analysis-only from LaTeX:

```matlab
report = analyzeEquationSupport( ...
    "SourceType","latex", ...
    "Equations","\dot{x} = -x + z, z^3 + z - x = 0", ...
    "States",["x"], ...
    "Algebraics",["z"]);
```

Build from LaTeX:

```matlab
out = generateSimulinkFromLatex( ...
    "\dot{x} = -x + u", ...
    "States",["x"], ...
    "Inputs",["u"], ...
    "ModelName","demo_model", ...
    "OpenModel",true);
```

Build from MATLAB equation text:

```matlab
out = generateSimulinkFromEquationText( ...
    ["xdot = -x + z", "0 = z^3 + z - x"], ...
    "States",["x"], ...
    "Algebraics",["z"], ...
    "ModelName","dae_demo");
```

Build from symbolic-style MATLAB equations:

```matlab
syms x t u
eqn = diff(x,t) == -x + u;
out = generateSimulinkFromSymbolicMatlab( ...
    eqn, ...
    "States",["x"], ...
    "Inputs",["u"], ...
    "ModelName","sym_demo");
```

Build from a structured ODE function spec:

```matlab
spec = struct();
spec.representation = "vector_rhs";
spec.state_vector_name = "x";
spec.input_vector_name = "u";
spec.rhs = {"-x(1) + u(1)", "x(1) - x(2)"};

out = generateSimulinkFromODEFunction( ...
    spec, ...
    "States",["x1","x2"], ...
    "Inputs",["u1"], ...
    "ModelName","ode_spec_demo");
```

## Options

Shared wrapper options include:

- `States`
- `Algebraics`
- `Inputs`
- `Parameters`
- `TimeVariable`
- `Build`
- `RunSim`
- `OpenModel`
- `ModelName`
- `PythonExecutable`
- `BackendEntryPoint`
- `KeepTempFiles`
- `Verbose`
- `ClassificationMode`
- `SymbolConfig`
- `RuntimeOverride`
- `SimulinkOutputDir`
- `Assumptions`
- `DerivativeMap`
- `Tolerance`

Defaults:

- `Build = false` for `analyzeEquationSupport`
- `Build = true` for `generateSimulink...`
- `OpenModel = false`
- `TimeVariable = "t"`

## Honest Limitations

- `generateSimulinkFromODEFunction` supports only structured exported RHS specs.
- Opaque MATLAB function handles are intentionally rejected.
- The bridge does not reimplement the classifier or DAE logic in MATLAB.
- The final `.slx` generation still runs through the existing Python pipeline and existing `matlab.engine` build path.
- This is not yet a native MATLAB-only backend.
