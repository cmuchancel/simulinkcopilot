# Campaign Prompt: Stabilize Larger MATLAB-Symbolic Benchmark Systems

Use this prompt to continue the native MATLAB backend campaign from the current repo state with the explicit goal of making larger MATLAB-symbolic benchmark systems reliable on the `matlabv2native` path.

## Prompt

You are continuing work inside the `simulinkcopilot` repository on branch:

- `matlab-native-backend-campaign`

Start from the current repo state after the benchmark-stability checkpoint where:

- the cart-pendulum benchmark builds through `matlabv2native.generate(...)`
- the planar quadrotor benchmark builds through `matlabv2native.generate(...)`
- the acrobot benchmark builds through `matlabv2native.generate(...)`
- the planar quadrotor biased step input `1 + heaviside(t)` lowers natively as a `Step` source
- the acrobot biased step torque input `0.1 + 0.2*heaviside(t - 0.5)` lowers natively as a `Step` source even after MATLAB canonicalizes it to `heaviside(t - 1/2)/5 + 1/10`
- user-provided symbolic state order is preserved instead of being alphabetized internally

## Scope Lock

This campaign is only about:

- the `matlab_symbolic` front door
- larger coupled nonlinear benchmark systems
- native runtime generation quality and reliability
- keeping lowering behavior readable and predictable

Do not broaden this campaign into:

- LaTeX parity
- equation-text parity
- structured ODE specs
- DAE/descriptor parity beyond what current benchmark systems actually exercise
- Python-parity polishing unless it directly helps benchmark reliability

## Current Complex-System Baseline

The repo now has committed MATLAB-symbolic runtime coverage for at least:

- a coupled cart-pendulum benchmark
- a planar quadrotor benchmark with trigonometric coupling and biased step/constant thrust inputs
- an acrobot benchmark with coupled trigonometric dynamics and biased step torque input

Those are the new “don’t regress” anchors for complex MATLAB-symbolic systems.

## Mission

Advance `matlabv2native` from “complex-system probes pass” to “complex-system benchmark path is stable and intentional.”

Focus on:

- more complex benchmark coverage
- native source recognition for realistic input combinations
- readable native lowering where possible
- explicit fallback boundaries where native lowering is still not the right answer

## Primary Objective

Use the new benchmark anchor style to close the next complex-system gaps in this order:

1. add one more larger nonlinear benchmark beyond cart-pendulum, planar quadrotor, and acrobot
2. harden mixed realistic input families used by larger systems:
   - biased/scaled steps
   - mixed constant + step thrust/force profiles
   - multiple coordinated inputs
3. keep user-specified state ordering stable through preview, generation, and result structs
4. reduce avoidable `MATLAB Function` fallback in benchmark models where native block composition is practical

## Required Testing

Add or extend MATLAB-backed integration coverage for:

- at least one new larger benchmark system
- at least one multi-input benchmark case
- state-order preservation for complex symbolic systems
- native source-block-family assertions for realistic benchmark inputs

## Required Documentation

Update:

- [matlab_native_backend_architecture.md](./matlab_native_backend_architecture.md)
- [matlab_native_backend_parity_ledger.md](./matlab_native_backend_parity_ledger.md)

Document explicitly:

- which larger benchmark systems are now regression anchors
- which parts of those systems are lowered natively
- where `MATLAB Function` fallback is still intentional

## Concrete First Step

Start by selecting one more benchmark-sized MATLAB-symbolic system that is clearly larger than the current scalar-family tests, then:

1. prove it analyzes and generates through `matlabv2native`
2. decide whether it should be `native_runtime_only` or intentionally delegated
3. add a committed regression test
4. document the boundary honestly
