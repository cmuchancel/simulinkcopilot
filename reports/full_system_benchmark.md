# Full System Benchmark

- cases run: 21
- passed: 21
- failed: 0
- tolerance: 1e-06

## Category 1 - Basic First-Order Systems
### basic_decay
- overall_pass: True
- latex: `\dot{x}=-ax`
- state_count: 1
- graph_nodes: 5
- simulink_blocks: 5
- ode_simulation_time_sec: 0.015862457978073508
- state_space_simulation_time_sec: 0.05242324998835102
- simulink_build_time_sec: 26.37953562499024
- simulink_simulation_time_sec: 1.3185246660141274
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/basic_decay_simulink.slx)
- simulink_compare: passed (rmse=3.613e-11, max=1.974e-10)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=3.613e-11, max=1.974e-10
### affine_first_order_input
- overall_pass: True
- latex: `\dot{x}=ax+bu`
- state_count: 1
- graph_nodes: 8
- simulink_blocks: 5
- ode_simulation_time_sec: 0.004791167040821165
- state_space_simulation_time_sec: 0.0038186669698916376
- simulink_build_time_sec: 0.9289472500095144
- simulink_simulation_time_sec: 0.11403233301825821
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/affine_first_order_input_simulink.slx)
- simulink_compare: passed (rmse=3.319e-10, max=7.505e-10)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=3.319e-10, max=7.505e-10

## Category 10 - Nonlinear Coupled Systems
### nonlinear_coupled
- overall_pass: True
- latex: `\dot{x}=y^2
\dot{y}=-x^3`
- state_count: 2
- graph_nodes: 9
- simulink_blocks: 7
- ode_simulation_time_sec: 0.001132250006776303
- state_space_simulation_time_sec: None
- simulink_build_time_sec: 1.3114803329808637
- simulink_simulation_time_sec: 0.20759645802900195
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: skipped (nonlinear explicit system)
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: skipped (state-space comparison not available)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/nonlinear_coupled_simulink.slx)
- simulink_compare: passed (rmse=1.861e-11, max=4.890e-11)
- simulink_metrics: rmse=1.861e-11, max=4.890e-11

## Category 11 - Nonlinear Physical Systems
### nonlinear_pendulum
- overall_pass: True
- latex: `\ddot{\theta}+\frac{g}{l}\sin(\theta)=0`
- state_count: 2
- graph_nodes: 10
- simulink_blocks: 9
- ode_simulation_time_sec: 0.011541750049218535
- state_space_simulation_time_sec: None
- simulink_build_time_sec: 1.4851378749590367
- simulink_simulation_time_sec: 0.22225375002017245
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: skipped (nonlinear explicit system)
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: skipped (state-space comparison not available)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/nonlinear_pendulum_simulink.slx)
- simulink_compare: passed (rmse=3.674e-10, max=1.068e-09)
- simulink_metrics: rmse=3.674e-10, max=1.068e-09

## Category 12 - Systems That SHOULD FAIL
### fail_dae
- overall_pass: True
- latex: `x+y=1
\dot{x}=y`
- failure_stage: solve
- failure_reason: Equation 0 does not contain a highest-order derivative target; algebraic/DAE-like constraints are unsupported.
- state_count: 1
- graph_nodes: None
- simulink_blocks: None
- ode_simulation_time_sec: None
- state_space_simulation_time_sec: None
- simulink_build_time_sec: None
- simulink_simulation_time_sec: None
- parse: passed
- state_extraction: passed
- solve: expected_failure (Equation 0 does not contain a highest-order derivative target; algebraic/DAE-like constraints are unsupported.)
- first_order: skipped
- state_space: skipped
- graph_lowering: skipped
- graph_validation: skipped
- ode_simulation: skipped
- comparison: skipped
- simulink_build: skipped
- simulink_compare: skipped
### fail_implicit_derivative
- overall_pass: True
- latex: `\dot{x}+\sin(\dot{x})=u`
- failure_stage: solve
- failure_reason: Failed to isolate highest-order derivatives; implicit nonlinear derivative coupling is unsupported.
- state_count: 1
- graph_nodes: None
- simulink_blocks: None
- ode_simulation_time_sec: None
- state_space_simulation_time_sec: None
- simulink_build_time_sec: None
- simulink_simulation_time_sec: None
- parse: passed
- state_extraction: passed
- solve: expected_failure (Failed to isolate highest-order derivatives; implicit nonlinear derivative coupling is unsupported.)
- first_order: skipped
- state_space: skipped
- graph_lowering: skipped
- graph_validation: skipped
- ode_simulation: skipped
- comparison: skipped
- simulink_build: skipped
- simulink_compare: skipped
### fail_underdetermined
- overall_pass: True
- latex: `\dot{x}+y=u`
- failure_stage: state_extraction
- failure_reason: Ambiguous external-symbol classification encountered in pure forcing terms: -y -> y
- state_count: None
- graph_nodes: None
- simulink_blocks: None
- ode_simulation_time_sec: None
- state_space_simulation_time_sec: None
- simulink_build_time_sec: None
- simulink_simulation_time_sec: None
- parse: passed
- state_extraction: expected_failure (Ambiguous external-symbol classification encountered in pure forcing terms: -y -> y)
- solve: skipped
- first_order: skipped
- state_space: skipped
- graph_lowering: skipped
- graph_validation: skipped
- ode_simulation: skipped
- comparison: skipped
- simulink_build: skipped
- simulink_compare: skipped
### fail_unsupported_syntax
- overall_pass: True
- latex: `\int x dt`
- failure_stage: parse
- failure_reason: Unsupported LaTeX command '\int' at position 0.
- state_count: None
- graph_nodes: None
- simulink_blocks: None
- ode_simulation_time_sec: None
- state_space_simulation_time_sec: None
- simulink_build_time_sec: None
- simulink_simulation_time_sec: None
- parse: expected_failure (Unsupported LaTeX command '\int' at position 0.)
- state_extraction: skipped
- solve: skipped
- first_order: skipped
- state_space: skipped
- graph_lowering: skipped
- graph_validation: skipped
- ode_simulation: skipped
- comparison: skipped
- simulink_build: skipped
- simulink_compare: skipped

## Category 2 - Second-Order Single-State Systems
### mass_spring
- overall_pass: True
- latex: `m\ddot{x}+kx=u`
- state_count: 2
- graph_nodes: 11
- simulink_blocks: 10
- ode_simulation_time_sec: 0.011849041969981045
- state_space_simulation_time_sec: 0.013949999993201345
- simulink_build_time_sec: 0.8816004170221277
- simulink_simulation_time_sec: 0.2283280419651419
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/mass_spring_simulink.slx)
- simulink_compare: passed (rmse=4.277e-10, max=1.117e-09)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=4.277e-10, max=1.117e-09
### mass_spring_damped
- overall_pass: True
- latex: `m\ddot{x}+c\dot{x}+kx=u`
- state_count: 2
- graph_nodes: 13
- simulink_blocks: 12
- ode_simulation_time_sec: 0.01202733302488923
- state_space_simulation_time_sec: 0.014635166036896408
- simulink_build_time_sec: 1.8201395419891924
- simulink_simulation_time_sec: 0.1701115000178106
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/mass_spring_damped_simulink.slx)
- simulink_compare: passed (rmse=1.924e-10, max=4.000e-10)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=1.924e-10, max=4.000e-10

## Category 3 - Higher-Order Single-State Systems
### third_order_single_state
- overall_pass: True
- latex: `\frac{d^3 x}{dt^3}+a\ddot{x}+b\dot{x}+cx=u`
- state_count: 3
- graph_nodes: 15
- simulink_blocks: 15
- ode_simulation_time_sec: 0.009236874990165234
- state_space_simulation_time_sec: 0.01193016697652638
- simulink_build_time_sec: 2.1893566660000943
- simulink_simulation_time_sec: 0.24228808301268145
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=2.613e-16, max=1.332e-15)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/third_order_single_state_simulink.slx)
- simulink_compare: passed (rmse=5.860e-10, max=1.549e-09)
- comparison_metrics: rmse=2.613e-16, max=1.332e-15
- simulink_metrics: rmse=5.860e-10, max=1.549e-09
### fourth_order_single_state
- overall_pass: True
- latex: `\frac{d^4 x}{dt^4}+a\frac{d^3 x}{dt^3}+b\ddot{x}+c\dot{x}+dx=u`
- state_count: 4
- graph_nodes: 19
- simulink_blocks: 19
- ode_simulation_time_sec: 0.006813125044573098
- state_space_simulation_time_sec: 0.01083049998851493
- simulink_build_time_sec: 2.141631292004604
- simulink_simulation_time_sec: 0.11179204197833315
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=3.540e-16, max=1.776e-15)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/fourth_order_single_state_simulink.slx)
- simulink_compare: passed (rmse=3.814e-10, max=1.382e-09)
- comparison_metrics: rmse=3.540e-16, max=1.776e-15
- simulink_metrics: rmse=3.814e-10, max=1.382e-09

## Category 4 - Multi-State Linear Systems
### two_state_linear
- overall_pass: True
- latex: `\dot{x}=ax+by
\dot{y}=cx+dy`
- state_count: 2
- graph_nodes: 14
- simulink_blocks: 10
- ode_simulation_time_sec: 0.007909417035989463
- state_space_simulation_time_sec: 0.008704167034011334
- simulink_build_time_sec: 0.9019490000209771
- simulink_simulation_time_sec: 0.1882565839914605
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/two_state_linear_simulink.slx)
- simulink_compare: passed (rmse=2.180e-11, max=1.531e-10)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=2.180e-11, max=1.531e-10
### harmonic_pair
- overall_pass: True
- latex: `\dot{x_1}=x_2
\dot{x_2}=-x_1`
- state_count: 2
- graph_nodes: 5
- simulink_blocks: 5
- ode_simulation_time_sec: 0.005806249973829836
- state_space_simulation_time_sec: 0.0055259999935515225
- simulink_build_time_sec: 0.9818292920244858
- simulink_simulation_time_sec: 0.1805833749822341
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/harmonic_pair_simulink.slx)
- simulink_compare: passed (rmse=2.972e-10, max=6.836e-10)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=2.972e-10, max=6.836e-10

## Category 5 - Coupled Second-Order Systems
### two_mass_undamped
- overall_pass: True
- latex: `m_1\ddot{x_1}=-k(x_1-x_2)
m_2\ddot{x_2}=k(x_1-x_2)`
- state_count: 4
- graph_nodes: 19
- simulink_blocks: 16
- ode_simulation_time_sec: 0.010446667030919343
- state_space_simulation_time_sec: 0.01295504200970754
- simulink_build_time_sec: 2.058143333008047
- simulink_simulation_time_sec: 0.20664449996547773
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=4.445e-16, max=1.166e-15)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/two_mass_undamped_simulink.slx)
- simulink_compare: passed (rmse=1.692e-10, max=5.591e-10)
- comparison_metrics: rmse=4.445e-16, max=1.166e-15
- simulink_metrics: rmse=1.692e-10, max=5.591e-10
### two_mass_damped
- overall_pass: True
- latex: `m_1\ddot{x_1}=-k(x_1-x_2)-c(\dot{x_1}-\dot{x_2})
m_2\ddot{x_2}=k(x_1-x_2)+c(\dot{x_1}-\dot{x_2})`
- state_count: 4
- graph_nodes: 25
- simulink_blocks: 23
- ode_simulation_time_sec: 0.010084624984301627
- state_space_simulation_time_sec: 0.013188166019972414
- simulink_build_time_sec: 1.930342167033814
- simulink_simulation_time_sec: 0.1073011250118725
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=3.749e-16, max=9.992e-16)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/two_mass_damped_simulink.slx)
- simulink_compare: passed (rmse=1.054e-10, max=2.866e-10)
- comparison_metrics: rmse=3.749e-16, max=9.992e-16
- simulink_metrics: rmse=1.054e-10, max=2.866e-10

## Category 6 - Multi-Mass Systems (Scaling)
### three_mass_chain
- overall_pass: True
- latex: `m_1\ddot{x_1}=-k(x_1-x_2)
m_2\ddot{x_2}=k(x_1-x_2)-k(x_2-x_3)
m_3\ddot{x_3}=k(x_2-x_3)`
- state_count: 6
- graph_nodes: 30
- simulink_blocks: 26
- ode_simulation_time_sec: 0.010557290981523693
- state_space_simulation_time_sec: 0.01722433394752443
- simulink_build_time_sec: 1.3070353750372306
- simulink_simulation_time_sec: 0.21610712504480034
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=2.301e-16, max=1.180e-15)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/three_mass_chain_simulink.slx)
- simulink_compare: passed (rmse=5.594e-11, max=1.918e-10)
- comparison_metrics: rmse=2.301e-16, max=1.180e-15
- simulink_metrics: rmse=5.594e-11, max=1.918e-10

## Category 7 - Driven Systems
### driven_mass_spring
- overall_pass: True
- latex: `m\ddot{x}+c\dot{x}+kx=u(t)`
- state_count: 2
- graph_nodes: 13
- simulink_blocks: 12
- ode_simulation_time_sec: 0.0056219170219264925
- state_space_simulation_time_sec: 0.006884292000904679
- simulink_build_time_sec: 1.0439465829986148
- simulink_simulation_time_sec: 0.21248024998931214
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/driven_mass_spring_simulink.slx)
- simulink_compare: passed (rmse=1.510e-08, max=3.158e-08)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=1.510e-08, max=3.158e-08

## Category 8 - Mixed First + Second Order
### mixed_first_second
- overall_pass: True
- latex: `\dot{x}=v
m\dot{v}+kv=u`
- state_count: 2
- graph_nodes: 11
- simulink_blocks: 10
- ode_simulation_time_sec: 0.004470625019166619
- state_space_simulation_time_sec: 0.00512983399676159
- simulink_build_time_sec: 1.7346647499944083
- simulink_simulation_time_sec: 0.2178876250400208
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: passed
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: passed (rmse=0.000e+00, max=0.000e+00)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/mixed_first_second_simulink.slx)
- simulink_compare: passed (rmse=1.718e-10, max=4.194e-10)
- comparison_metrics: rmse=0.000e+00, max=0.000e+00
- simulink_metrics: rmse=1.718e-10, max=4.194e-10

## Category 9 - Nonlinear Polynomial Systems
### nonlinear_square
- overall_pass: True
- latex: `\dot{x}=x^2`
- state_count: 1
- graph_nodes: 4
- simulink_blocks: 3
- ode_simulation_time_sec: 0.0006052079843357205
- state_space_simulation_time_sec: None
- simulink_build_time_sec: 1.066801457956899
- simulink_simulation_time_sec: 0.17185024998616427
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: skipped (nonlinear explicit system)
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: skipped (state-space comparison not available)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/nonlinear_square_simulink.slx)
- simulink_compare: passed (rmse=4.778e-11, max=1.110e-10)
- simulink_metrics: rmse=4.778e-11, max=1.110e-10
### nonlinear_affine_polynomial
- overall_pass: True
- latex: `\dot{x}=ax^2+bx+c`
- state_count: 1
- graph_nodes: 10
- simulink_blocks: 7
- ode_simulation_time_sec: 0.0016342499875463545
- state_space_simulation_time_sec: None
- simulink_build_time_sec: 1.246315875032451
- simulink_simulation_time_sec: 0.17822233302285895
- parse: passed
- state_extraction: passed
- solve: passed
- first_order: passed
- state_space: skipped (nonlinear explicit system)
- graph_lowering: passed
- graph_validation: passed
- ode_simulation: passed
- comparison: skipped (state-space comparison not available)
- simulink_build: passed (/Users/chancelavoie/Desktop/simulinkcopilot/generated_models/benchmark_models/nonlinear_affine_polynomial_simulink.slx)
- simulink_compare: passed (rmse=2.032e-11, max=4.169e-11)
- simulink_metrics: rmse=2.032e-11, max=4.169e-11
