# MATLAB Native Backend Parity Ledger

This ledger tracks the current parity status of `matlabv2native` relative to the Python backend.

The goal is to keep claims explicit:

- `runtime-native`: supported in the default MATLAB runtime path without Python in the hot path
- `matlab-reference`: validated against the MATLAB numerical reference path
- `python-parity`: explicitly comparable against the Python backend when requested
- `delegated`: still routed to Python or not yet trustworthy natively

## Current Checkpoint

- branch: `matlab-native-backend-campaign`
- latest parity-expansion phase after runtime split: symbolic nonlinear runtime widening for saturation and dead zone

## Front Doors

| Front Door | Native Intake | Runtime-Native Build | Python Delegate / Parity Notes |
| --- | --- | --- | --- |
| `matlab_symbolic` | Yes | Yes for current explicit-ODE native set | Primary native front door today |
| MATLAB equation text | Partial preview / delegation | No | Delegates to Python for build/runtime |
| LaTeX | No native lowering yet | No | Delegates to Python |
| structured ODE spec | No native lowering yet | No | Delegates to Python |

## Route / Problem Shape Status

| Problem Shape | Native Preview | Runtime-Native | MATLAB Reference | Python Parity | Notes |
| --- | --- | --- | --- | --- | --- |
| first-order explicit scalar ODE | Yes | Yes | Yes | Yes | Anchor path is stable |
| second-order scalar ODE reduced to first order | Yes | Yes | Yes | Yes | Anchor path is stable |
| coupled explicit ODE system | Yes | Yes | Yes | Yes | Runtime-native and parity-mode integration coverage exist |
| parameterized explicit ODE | Yes | Yes | Yes | Yes for current anchor-style cases | Parameters must still be provided numerically |
| non-explicit / ambiguous systems | Partial / delegated | No | No | Python only | Still delegated |
| DAE / descriptor-style systems | No meaningful native parity yet | No | No | Python only | Do not overclaim |

## Input Family Status

| Family | Runtime-Native | MATLAB Reference | Python Parity | Symbolic Recognition | Struct-Spec Native | Python Required In Hot Path | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| constant | Yes | Yes | Yes | Yes | Yes | No | Stable |
| step | Yes | Yes | Yes | Yes | Yes | No | Stable |
| delayed step | Yes | Yes | Yes | Yes | Yes | No | Stable for current native step path |
| pulse | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic `heaviside(...)` pulse recognition now lowers natively |
| ramp | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic ramp recognition now lowers natively |
| sine | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic sine/cosine-form recognition now lowers natively |
| cosine | No | No | Python only | No | No | Yes | Still pending native promotion |
| square | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic square recognition now lowers natively; parity uses semantic family matching because Python may compose it as `Sum` |
| sawtooth | Yes | Yes | No | No | Yes | No | Runtime-native through expression/input-spec path; direct MATLAB symbolic `sawtooth(sym)` is not reliable and Python parity is still pending |
| triangle | Yes | Yes | No | No | Yes | No | Runtime-native through expression/input-spec path; direct MATLAB symbolic `sawtooth(sym,0.5)` is not reliable and Python parity is still pending |
| saturation | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `min(max(...))` clamp now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| dead zone | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic dead-zone piecewise form now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| sign | No | No | Python only | No | No | Yes | Pending native promotion |
| abs | No | No | Python only | No | No | Yes | Pending native promotion |
| min/max | No | No | Python only | No | No | Yes | Pending native promotion |
| impulse approximation | No | No | Python only | No | No | Yes | Pending native promotion |
| `atan` | No | No | Python only | No | No | Yes | Pending native promotion |
| `atan2` | No | No | Python only | No | No | Yes | Pending native promotion |
| `exp` | No | No | Python only | No | No | Yes | Pending native promotion |
| `log` | No | No | Python only | No | No | Yes | Pending native promotion |
| `sqrt` | No | No | Python only | No | No | Yes | Pending native promotion |
| unsupported symbolic expression via `MATLAB Function` fallback | Yes | Yes | Limited | Partial | Yes | No | Runtime-native fallback exists, but parity is not yet broad |

## Important Notes

- `pulse`, `ramp`, `sine`, `square`, `saturation`, and `dead zone` now have direct MATLAB symbolic-expression recognition in the native path, not just struct-style input specs.
- For simple affine explicit-ODE RHS expressions, the native builder now uses `Sum` / `Gain` composition instead of dropping straight to a `MATLAB Function` block.
- `square` parity is semantic rather than byte-identical: the native path uses `SquareWave`, while the Python backend may compose the same symbolic square wave as a `Sum`-based subgraph.
- `sawtooth` and `triangle` are runtime-native through expression/input-spec forms, but not yet claimed as broad direct-symbolic families because MATLAB does not reliably preserve raw `sawtooth(sym)` forms as symbolic expressions.
- Python parity for `sawtooth` and `triangle` expression/input-spec forms is still pending because the current Python oracle model path fails during model initialization for those cases.
- `saturation` and `dead zone` are now MATLAB-symbolic runtime-native with MATLAB-reference validation, but this checkpoint does not claim Python-parity cleanliness for those families yet.
- The default runtime path stays lean for runtime-native cases. Python parity remains explicit and heavier.
- The current comparison surface is strongest for explicit ODEs. DAE / descriptor parity is still Python-only.

## Next Gaps To Close

1. Finish Python-parity support for runtime-native repeating-sequence families: `sawtooth`, `triangle`.
2. Decide whether to claim Python parity for runtime-native nonlinear families: `saturation`, `dead_zone`.
3. Promote the next nonlinear source families: `sign`, `abs`, `min/max`.
4. Promote unary math families: `atan`, `atan2`, `exp`, `log`, `sqrt`.
5. Add committed native coverage for `cosine` and impulse-style symbolic inputs.
6. Expand the heavy comparison API so parity beyond preview metadata is easier to run and inspect.
