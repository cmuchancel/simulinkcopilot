# Phase 3 Report

- examples run: 9
- passed: 9
- failed: 0
- tolerance: 1e-06

## Supported Syntax
- \dot{x}
- \ddot{x}
- \frac{d^n x}{dt^n} for explicit integer n
- \frac{...}{...} including nested fractions
- implicit multiplication such as 2x, k(x-y), m\frac{dx}{dt}
- indexed symbols such as x_1, x_2, k_12
- \left...\right normalization

## Supported System Classes
- linear first-order ODE systems
- linear higher-order ODE systems reduced to first-order form
- coupled multi-state linear systems
- mixed first/second-order systems
- explicit nonlinear polynomial first-order systems

## Known Unsupported Classes
- DAE-like algebraic constraints mixed with differential equations
- implicit nonlinear derivative coupling with non-unique solves
- unsupported LaTeX commands outside the restricted grammar
- nonlinear systems in state-space conversion

## Graph Lowering Coverage
- ops: add, constant, div, gain, integrator, mul, negate, pow, state_signal, sum, symbol_input

## Simulink Regression Examples
- damped_forced_system
- driven_oscillator
- mass_spring_damper
- three_mass_coupled
- two_mass_coupled

## Example Results
### coupled_system
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: skipped (Simulink backend not requested)
- simulink_compare: skipped (Simulink backend not requested)
- graph_ops: constant, integrator, mul, state_signal, sum, symbol_input
### damped_forced_system
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=1.719e-16, max=4.441e-16)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/backend_models/damped_forced_system_simulink.slx)
- simulink_compare: passed (rmse=8.530e-11, max=2.117e-10)
- graph_ops: constant, integrator, mul, pow, state_signal, sum, symbol_input
### driven_oscillator
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/backend_models/driven_oscillator_simulink.slx)
- simulink_compare: passed (rmse=5.924e-10, max=1.553e-09)
- graph_ops: add, constant, integrator, mul, pow, state_signal, symbol_input
### mass_spring_damper
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/backend_models/mass_spring_damper_simulink.slx)
- simulink_compare: passed (rmse=2.328e-10, max=4.764e-10)
- graph_ops: constant, div, integrator, mul, state_signal, sum, symbol_input
### mixed_parameter_forms
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=4.636e-15, max=1.421e-14)
- simulink_build: skipped (Simulink backend not requested)
- simulink_compare: skipped (Simulink backend not requested)
- graph_ops: constant, div, gain, integrator, mul, negate, state_signal, sum, symbol_input
### nonlinear_pendulum
- overall_pass: True
- expected_linear: False
- inferred_linear: False
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: skipped (nonlinear explicit system)
- comparison: skipped (state-space comparison not available)
- simulink_build: skipped (Simulink backend not requested)
- simulink_compare: skipped (Simulink backend not requested)
- graph_ops: constant, integrator, mul, pow, state_signal, sum, symbol_input
### third_order_system
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=1.966e-15, max=1.066e-14)
- simulink_build: skipped (Simulink backend not requested)
- simulink_compare: skipped (Simulink backend not requested)
- graph_ops: constant, div, integrator, mul, state_signal, sum, symbol_input
### three_mass_coupled
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=1.901e-15, max=7.105e-15)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/backend_models/three_mass_coupled_simulink.slx)
- simulink_compare: passed (rmse=1.840e-09, max=8.006e-09)
- graph_ops: constant, div, gain, integrator, mul, state_signal, sum, symbol_input
### two_mass_coupled
- overall_pass: True
- expected_linear: True
- inferred_linear: True
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- state_space: passed
- comparison: passed (rmse=2.357e-15, max=1.066e-14)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/backend_models/two_mass_coupled_simulink.slx)
- simulink_compare: passed (rmse=2.811e-09, max=1.172e-08)
- graph_ops: constant, div, gain, integrator, mul, state_signal, sum, symbol_input
