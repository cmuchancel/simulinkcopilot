# Hard Examples Report

Commit: `a501761b86f5bdd6c379d9876ff97c1e5f5add64`

This document summarizes the harder nonlinear and coupled examples that were run through the deterministic pipeline and passed. Each passed case completed the supported stages:

- parse
- deterministic state extraction
- solve-for-derivatives
- first-order conversion
- graph lowering
- graph validation
- Python ODE simulation
- Simulink model build
- Simulink simulation
- numerical comparison against the Python ODE result

State-space generation is omitted for these systems when they are nonlinear.

## Summary

| Example | Type | States | Simulink | RMSE vs ODE | Max Abs Error vs ODE |
| --- | --- | --- | --- | --- | --- |
| `cart_pendulum_hw3` | coupled nonlinear second-order trig system | 4 | pass | `1.2302390546687176e-09` | `2.1170118102986635e-08` |
| `coupled_trig_difference` | nonlinear coupled first-order trig difference system | 4 | pass | `2.875034594340875e-10` | `8.758288538857073e-10` |
| `nested_nonlinear` | nested nonlinear first-order system | 2 | pass | `4.877339491562638e-10` | `6.760112691850395e-09` |
| `higher_order_nonlinear` | third-order nonlinear scalar system | 3 | pass | `1.9129905564475133e-09` | `1.671633453881327e-08` |
| `double_pendulum_hard_test` | coupled nonlinear second-order pendulum-like system | 4 | pass | `1.1566707045733199e-10` | `2.5843843731720995e-10` |

All listed examples passed the validation tolerance of `1e-6`.

## 1. HW3 Cart-Pendulum / Spring Coupled Nonlinear System

### Input equations

```latex
(m_1 + m_2)\ddot{x}
+ \frac{m_2 l}{2}\cos(\theta)\ddot{\theta}
- \frac{m_2 l}{2}\sin(\theta)\dot{\theta}^2
+ kx = 0

\frac{m_2 l}{2}\cos(\theta)\ddot{x}
+ \frac{1}{4}(m_2 l^2 + 4I)\ddot{\theta}
+ \frac{m_2 g l}{2}\sin(\theta) = 0
```

### Runtime used

- parameters: `m_1=10.0`, `m_2=2.0`, `l=1.0`, `k=100.0`, `I=0.17`, `g=9.81`
- initial conditions: `x(0)=1.0`, `x_dot(0)=0.0`, `theta(0)=pi/4`, `theta_dot(0)=0.0`
- internal normalized state names: `x`, `x_dot`, `q`, `q_dot`
- time span: `[0.0, 10.0]`
- sample count: `600`

### Stage result

- parse: pass
- state extraction: pass
- solve derivatives: pass
- first-order conversion: pass
- graph lowering: pass
- graph validation: pass
- Python ODE simulation: pass
- Simulink build: pass
- Simulink simulation: pass
- comparison vs ODE: pass

### Outputs

- states: `["q", "q_dot", "x", "x_dot"]`
- inputs: `[]`
- parameters: `["I", "g", "k", "l", "m_1", "m_2"]`
- graph size: `47 nodes`, `101 edges`
- graph ops: `constant`, `cos`, `div`, `gain`, `integrator`, `mul`, `pow`, `sin`, `state_signal`, `sum`, `symbol_input`

### Validation metrics

- RMSE vs ODE: `1.2302390546687176e-09`
- max abs error vs ODE: `2.1170118102986635e-08`
- pass tolerance: `1e-6`

### Artifacts

- verbose bundle: `reports/verbose/cart_pendulum_hw3/`
- runtime file: `reports/verbose/cart_pendulum_hw3/runtime.json`
- summary file: `reports/verbose/cart_pendulum_hw3/summary.json`
- simulation plot: `reports/verbose/cart_pendulum_hw3/simulation_plot.png`
- Simulink model image: `reports/verbose/cart_pendulum_hw3/simulink_model.png`
- Simulink model file: `generated_models/backend_models/cart_pendulum_coupled_simulink.slx`

## 2. Coupled Trig Difference

### Input equations

```latex
\dot{\theta}_1 = \omega_1
\dot{\omega}_1 = -\sin(\theta_1 - \theta_2)
\dot{\theta}_2 = \omega_2
\dot{\omega}_2 = \sin(\theta_1 - \theta_2)
```

### Notes

- this case originally failed before the frontend supported derivative-target subscripts like `\dot{\theta}_1`
- after the normalization/parser fix, it passed the full nonlinear pipeline

### Runtime used

- initial conditions: `theta_1(0)=0.5`, `omega_1(0)=0.0`, `theta_2(0)=-0.25`, `omega_2(0)=0.1`
- internal normalized state names: `q_1`, `w_1`, `q_2`, `w_2`
- time span: `[0.0, 8.0]`
- sample count: `400`

### Stage result

- parse: pass
- state extraction: pass
- solve derivatives: pass
- first-order conversion: pass
- graph lowering: pass
- graph validation: pass
- Python ODE simulation: pass
- Simulink build: pass
- Simulink simulation: pass
- comparison vs ODE: pass

### Outputs

- states: `["q_1", "q_2", "w_1", "w_2"]`
- inputs: `[]`
- parameters: `[]`

### Validation metrics

- RMSE vs ODE: `2.875034594340875e-10`
- max abs error vs ODE: `8.758288538857073e-10`
- pass tolerance: `1e-6`

### Artifacts

- Simulink model file: `generated_models/stress_models/coupled_trig_difference_simulink.slx`

## 3. Nested Nonlinear

### Input equations

```latex
\dot{x} = \sin(x^2 + \theta)
\dot{\theta} = x + \cos(\theta)
```

### Runtime used

- initial conditions: `x(0)=0.3`, `theta(0)=0.5`
- internal normalized state names: `x`, `q`
- time span: `[0.0, 8.0]`
- sample count: `400`

### Stage result

- parse: pass
- state extraction: pass
- solve derivatives: pass
- first-order conversion: pass
- graph lowering: pass
- graph validation: pass
- Python ODE simulation: pass
- Simulink build: pass
- Simulink simulation: pass
- comparison vs ODE: pass

### Outputs

- states: `["q", "x"]`
- inputs: `[]`
- parameters: `[]`
- graph size: `10 nodes`, `12 edges`

### Validation metrics

- RMSE vs ODE: `4.877339491562638e-10`
- max abs error vs ODE: `6.760112691850395e-09`
- pass tolerance: `1e-6`

### Artifacts

- Simulink model file: `generated_models/stress_models/nested_nonlinear_simulink.slx`

## 4. Higher-Order Nonlinear

### Input equations

```latex
\frac{d^3 x}{dt^3} + \sin(x) = u
```

### Runtime used

- initial conditions: `x(0)=0.2`, `x_dot(0)=0.0`, `x_ddot(0)=0.0`
- input: constant `u=0.6`
- time span: `[0.0, 6.0]`
- sample count: `360`

### Stage result

- parse: pass
- state extraction: pass
- solve derivatives: pass
- first-order conversion: pass
- graph lowering: pass
- graph validation: pass
- Python ODE simulation: pass
- Simulink build: pass
- Simulink simulation: pass
- comparison vs ODE: pass

### Outputs

- states: `["x", "x_dot", "x_ddot"]`
- inputs: `["u"]`
- parameters: `[]`
- graph size: `10 nodes`, `10 edges`

### Validation metrics

- RMSE vs ODE: `1.9129905564475133e-09`
- max abs error vs ODE: `1.671633453881327e-08`
- pass tolerance: `1e-6`

### Artifacts

- Simulink model file: `generated_models/stress_models/higher_order_nonlinear_simulink.slx`

## 5. Double Pendulum Hard Test

### Input equations

```latex
\ddot{\theta}_1 + \sin(\theta_1) + 0.1(\dot{\theta}_1 - \dot{\theta}_2) = 0
\ddot{\theta}_2 + \sin(\theta_2) + 0.1(\dot{\theta}_2 - \dot{\theta}_1) = 0
```

### Notes

- this case also originally failed before derivative-target subscript normalization was added
- after the frontend fix, it passed the full nonlinear pipeline

### Runtime used

- initial conditions: `theta_1(0)=0.6`, `theta_1_dot(0)=0.0`, `theta_2(0)=-0.35`, `theta_2_dot(0)=0.05`
- internal normalized state names: `q_1`, `q_1_dot`, `q_2`, `q_2_dot`
- time span: `[0.0, 10.0]`
- sample count: `500`

### Stage result

- parse: pass
- state extraction: pass
- solve derivatives: pass
- first-order conversion: pass
- graph lowering: pass
- graph validation: pass
- Python ODE simulation: pass
- Simulink build: pass
- Simulink simulation: pass
- comparison vs ODE: pass

### Outputs

- states: `["q_1", "q_1_dot", "q_2", "q_2_dot"]`
- inputs: `[]`
- parameters: `[]`

### Validation metrics

- RMSE vs ODE: `1.1566707045733199e-10`
- max abs error vs ODE: `2.5843843731720995e-10`
- pass tolerance: `1e-6`

### Artifacts

- Simulink model file: `generated_models/stress_models/double_pendulum_hard_test_simulink.slx`

## Capability Boundary Demonstrated By These Examples

These passed examples show that the current deterministic system can handle:

- nonlinear trigonometric dynamics
- coupled multi-state systems
- higher-order nonlinear scalar systems
- derivative-target subscripts such as `\dot{\theta}_1`
- nonlinear graph lowering into Simulink-compatible structures
- nonlinear Simulink model generation without requiring state-space form
- numerical validation of `Simulink vs Python ODE` within `1e-6`

These examples do not imply support for:

- arbitrary DAEs
- unsupported LaTeX constructs outside the documented grammar
- symbolic state-space conversion for nonlinear systems

