# MATLAB Native Backend Parity Ledger

This ledger tracks the current parity status of `matlabv2native` relative to the Python backend.

The goal is to keep claims explicit:

- `runtime-native`: supported in the default MATLAB runtime path without Python in the hot path
- `matlab-reference`: validated against the MATLAB numerical reference path
- `python-parity`: explicitly comparable against the Python backend when requested
- `delegated`: still routed to Python or not yet trustworthy natively

## Current Checkpoint

- branch: `matlab-native-backend-campaign`
- latest parity-expansion phase after runtime split: symbolic math runtime widening for `atan`, `atan2`, `exp`, `log`, and `sqrt`
- latest benchmark-stability phase: cart-pendulum, planar-quadrotor, and acrobot MATLAB-symbolic runtime coverage
- latest route-boundary phase: reducible single-algebraic DAE reduction plus explicit `sawtooth` / `triangle` MATLAB-symbolic boundary documentation
- latest lowering-quality phase: native pure-time RHS lowering for explicit ODEs and reducible DAE outputs
- latest matrix/vector intake phase: vector-form MATLAB symbolic equation arrays plus mixed signal-plus-time RHS lowering for affine vector systems

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
| coupled explicit ODE system | Yes | Yes | Yes | Yes | Runtime-native and parity-mode integration coverage exist; cart-pendulum, planar-quadrotor, and acrobot benchmark regressions now also pass on the MATLAB-symbolic runtime path |
| vector / matrix-form explicit ODE system represented as plain vector-valued `sym` / `symfun` equations | Yes | Yes | Yes | No | `diff(X,t) == A*X` and `diff(X,t) == A*X + B*u(t)` now flatten cleanly into the existing native explicit-ODE path; `symmatrix` is not claimed |
| parameterized explicit ODE | Yes | Yes | Yes | Yes for current anchor-style cases | Parameters must still be provided numerically |
| non-explicit / ambiguous systems | Partial / delegated | No | No | Python only | Still delegated |
| reducible DAE / algebraic system | Yes | Yes for the current single-algebraic reduction path | Yes | No | Native route now supports a bounded subset by solving one algebraic variable and substituting it before explicit-ODE lowering |
| vector / matrix-form reducible DAE represented as plain vector-valued `sym` / `symfun` equations | Yes | Yes for the current single-algebraic reduction path | Yes | No | Vector-form systems that flatten into the same one-algebraic-variable elimination path are now covered |
| irreducible DAE / descriptor-style systems | Yes for route classification | No | No | Python only | Native preview now labels these explicitly as `dae_algebraic`; do not overclaim |

## Input Family Status

| Family | Runtime-Native | MATLAB Reference | Python Parity | Symbolic Recognition | Struct-Spec Native | Python Required In Hot Path | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| constant | Yes | Yes | Yes | Yes | Yes | No | Stable |
| step | Yes | Yes | Yes | Yes | Yes | No | Stable; biased/scaled `heaviside(...)` forms such as `1 + heaviside(t)` now normalize back into native step specs |
| delayed step | Yes | Yes | Yes | Yes | Yes | No | Stable for current native step path |
| pulse | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic `heaviside(...)` pulse recognition now lowers natively |
| ramp | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic ramp recognition now lowers natively |
| sine | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic sine/cosine-form recognition now lowers natively |
| cosine | No | No | Python only | No | No | Yes | Still pending native promotion |
| square | Yes | Yes | Yes | Yes | Yes | No | Direct symbolic square recognition now lowers natively; parity uses semantic family matching because Python may compose it as `Sum` |
| sawtooth | Yes | Yes | No | No | Yes | No | Runtime-native through expression/input-spec path; raw MATLAB symbolic `sawtooth(sym)` is rejected by MATLAB itself, so this family remains intentionally expression-spec-only and Python parity is still pending |
| triangle | Yes | Yes | No | No | Yes | No | Runtime-native through expression/input-spec path; raw MATLAB symbolic `sawtooth(sym,0.5)` is rejected by MATLAB itself, so this family remains intentionally expression-spec-only and Python parity is still pending |
| saturation | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `min(max(...))` clamp now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| dead zone | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic dead-zone piecewise form now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| sign | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `sign(...)` now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| abs | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `abs(...)` now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| min/max | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic two-input `min(...)` / `max(...)` now lowers natively and validates against the MATLAB reference; Python parity is not yet claimed |
| impulse approximation | No | No | Python only | No | No | Yes | Pending native promotion |
| `atan` | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `atan(...)` now lowers natively through a `Trigonometric Function` block and validates against the MATLAB reference; Python parity is not yet claimed |
| `atan2` | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `atan2(...)` now lowers natively; MATLAB canonical `angle(...)` rewrites are normalized back into a native `atan2` input spec |
| `exp` | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `exp(...)` now lowers natively through a `Math Function` block and validates against the MATLAB reference; Python parity is not yet claimed |
| `log` | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `log(...)` now lowers natively through a `Math Function` block and validates against the MATLAB reference; Python parity is not yet claimed |
| `sqrt` | Yes | Yes | No | Yes | Yes | No | Direct MATLAB symbolic `sqrt(...)` now lowers natively; MATLAB canonical power rewrites such as `(t+1)^(1/2)` are normalized back into a native `sqrt` input spec |
| unsupported symbolic expression via `MATLAB Function` fallback | Yes | Yes | Limited | Partial | Yes | No | Runtime-native fallback exists, but parity is not yet broad |

## Important Notes

- `pulse`, `ramp`, `sine`, `square`, `saturation`, and `dead zone` now have direct MATLAB symbolic-expression recognition in the native path, not just struct-style input specs.
- `sign`, `abs`, and two-input `min/max` now also have direct MATLAB symbolic-expression recognition in the native path, not just struct-style input specs.
- `atan`, `atan2`, `exp`, `log`, and `sqrt` now also have direct MATLAB symbolic-expression recognition in the native path, not just struct-style input specs.
- Larger MATLAB-symbolic nonlinear benchmarks now have committed runtime coverage: a coupled cart-pendulum, a planar quadrotor with biased step thrust input, and an acrobot with biased step torque input.
- For simple affine explicit-ODE RHS expressions, the native builder now uses `Sum` / `Gain` composition instead of dropping straight to a `MATLAB Function` block.
- Plain vector-valued MATLAB symbolic equation arrays such as `diff(X,t) == A*X` and `diff(X,t) == A*X + B*u(t)` now flatten into the existing native explicit-ODE path, and explicit user-provided state order is preserved for those vector-form systems.
- Mixed signal-plus-time RHS expressions such as `-x1 - 2*x2 - 3*x3 + 1 + heaviside(t - 1/2)` now lower natively instead of falling through to a broken MATLAB Function fallback, which is what unblocked the affine vector-form build case.
- MATLAB symbolic canonical forms such as `max([1/5, sin(t)], [], 2, ...)` and `min([1/5, sin(t)], [], 2, ...)` are now normalized back into native `MinMax` input specs.
- MATLAB symbolic canonical forms such as `angle(t*(1 + 1i) + 1)` and `(t + 1)^(1/2)` are now normalized back into native `atan2` and `sqrt` input specs.
- Biased/scaled/fractional `heaviside(...)` step forms such as `1 + heaviside(t)` and `heaviside(t - 1/2)/5 + 1/10` now normalize back into native step specs instead of falling through to MATLAB Function source fallback.
- `square` parity is semantic rather than byte-identical: the native path uses `SquareWave`, while the Python backend may compose the same symbolic square wave as a `Sum`-based subgraph.
- `sawtooth` and `triangle` are runtime-native through expression/input-spec forms, but not broad direct-symbolic families because MATLAB itself rejects raw `sawtooth(sym)` / `sawtooth(sym, 0.5)` constructions before `matlabv2native` can analyze them.
- Reducible DAE/algebraic systems with one algebraic variable solved from one algebraic equation now have a bounded native route through algebraic elimination followed by the existing explicit-ODE lowering path.
- Vector-form reducible DAE/algebraic systems now share that same bounded native route when MATLAB presents them as flattenable vector-valued `sym` / `symfun` equations.
- Recognized pure-time RHS expressions such as `sin(t)` and `t + 1` now lower natively instead of falling through to deferred `MATLAB Function` RHS blocks, which also improves readability for reducible-DAE outputs that simplify to pure-time expressions.
- `symmatrix` is still intentionally out of scope in this checkpoint; the claimed matrix/vector surface is plain vector-valued `sym` / `symfun` equation arrays, not MATLAB's broader matrix-symbolic object model.
- Irreducible DAE/algebraic systems are now labeled explicitly as `dae_algebraic` with delegated status instead of being left as a vague non-explicit boundary.
- Python parity for `sawtooth` and `triangle` expression/input-spec forms is still pending because the current Python oracle model path fails during model initialization for those cases.
- `saturation` and `dead zone` are now MATLAB-symbolic runtime-native with MATLAB-reference validation, but this checkpoint does not claim Python-parity cleanliness for those families yet.
- The default runtime path stays lean for runtime-native cases. Python parity remains explicit and heavier.
- The current comparison surface is strongest for explicit ODEs. DAE / descriptor parity is still Python-only.

## Next Gaps To Close

1. Decide whether to widen matrix/vector symbolic intake beyond plain vector-valued `sym` / `symfun` arrays and whether `symmatrix` should stay out of scope.
2. Decide whether to widen DAE reduction beyond the current single-algebraic-variable elimination path.
3. Add committed native coverage for `cosine` and impulse-style symbolic inputs.
4. Expand benchmark coverage beyond the current cart-pendulum, planar-quadrotor, acrobot, and vector-form regression checkpoints.
5. Decide whether to claim Python parity for the runtime-native nonlinear and math families that are already MATLAB-reference clean.
6. Keep reducing `MATLAB Function` fallback for source and RHS expressions that are simple enough to draw with standard Simulink blocks, especially for time-plus-parameter or other non-pure-time symbolic RHS forms.
