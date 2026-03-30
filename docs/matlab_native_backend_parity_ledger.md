# MATLAB Native Backend Parity Ledger

This ledger tracks the current parity status of `matlabv2native` relative to the Python backend.

The goal is to keep claims explicit:

- `runtime-native`: supported in the default MATLAB runtime path without Python in the hot path
- `matlab-reference`: validated against the MATLAB numerical reference path
- `python-parity`: explicitly comparable against the Python backend when requested
- `delegated`: still routed to Python or not yet trustworthy natively

## Current Checkpoint

- branch: `matlab-native-backend-campaign`
- latest parity-expansion phase after runtime split: pulse/ramp/sine promotion plus coupled explicit-system coverage

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
| coupled explicit ODE system | Yes | Yes | Yes | Not yet committed in parity mode | Runtime-native integration coverage exists |
| parameterized explicit ODE | Yes | Yes | Yes | Yes for current anchor-style cases | Parameters must still be provided numerically |
| non-explicit / ambiguous systems | Partial / delegated | No | No | Python only | Still delegated |
| DAE / descriptor-style systems | No meaningful native parity yet | No | No | Python only | Do not overclaim |

## Input Family Status

| Family | Runtime-Native | MATLAB Reference | Python Parity | Python Required In Hot Path | Notes |
| --- | --- | --- | --- | --- | --- |
| constant | Yes | Yes | Yes | No | Stable |
| step | Yes | Yes | Yes | No | Stable |
| delayed step | Yes | Yes | Yes | No | Stable for current native step path |
| pulse | Yes | Yes | Yes | No | Verified through native input spec struct path |
| ramp | Yes | Yes | Yes | No | Verified through native input spec struct path |
| sine | Yes | Yes | Yes | No | Verified through native input spec struct path |
| cosine | No | No | Python only | Yes | Still pending native promotion |
| square | No | No | Python only | Yes | Pending native promotion |
| sawtooth | No | No | Python only | Yes | Pending native promotion |
| triangle | No | No | Python only | Yes | Pending native promotion |
| saturation | No | No | Python only | Yes | Pending native promotion |
| dead zone | No | No | Python only | Yes | Pending native promotion |
| sign | No | No | Python only | Yes | Pending native promotion |
| abs | No | No | Python only | Yes | Pending native promotion |
| min/max | No | No | Python only | Yes | Pending native promotion |
| impulse approximation | No | No | Python only | Yes | Pending native promotion |
| `atan` | No | No | Python only | Yes | Pending native promotion |
| `atan2` | No | No | Python only | Yes | Pending native promotion |
| `exp` | No | No | Python only | Yes | Pending native promotion |
| `log` | No | No | Python only | Yes | Pending native promotion |
| `sqrt` | No | No | Python only | Yes | Pending native promotion |
| unsupported symbolic expression via `MATLAB Function` fallback | Yes | Yes | Limited | No | Runtime-native fallback exists, but parity is not yet broad |

## Important Notes

- `pulse`, `ramp`, and `sine` are currently verified as runtime-native through the caller-workspace input-spec path, for example `u = struct('kind', 'sine', ...)` after the symbolic equation is formed.
- Native symbolic-expression recognition for these widened families is not yet broad enough to claim full front-door parity with the Python expression normalizer.
- The default runtime path stays lean for runtime-native cases. Python parity remains explicit and heavier.
- The current comparison surface is strongest for explicit ODEs. DAE / descriptor parity is still Python-only.

## Next Gaps To Close

1. Promote the next waveform families: `square`, `sawtooth`, `triangle`.
2. Promote nonlinear source families: `saturation`, `dead_zone`, `sign`, `abs`, `min/max`.
3. Promote unary math families: `atan`, `atan2`, `exp`, `log`, `sqrt`.
4. Improve symbolic-expression recognition so widened families work natively without requiring struct-style input specs.
5. Expand the heavy comparison API so parity beyond preview metadata is easier to run and inspect.
