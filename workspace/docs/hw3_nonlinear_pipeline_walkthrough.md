# HW3 Nonlinear Pipeline Walkthrough

This document traces one real nonlinear system through the exact pipeline in this repo:

```text
LaTeX -> normalize -> tokenize -> parse -> canonical dict IR -> solve derivatives
-> first-order system -> graph -> Simulink model -> simulation -> validation
```

The example is the coupled cart-pendulum / spring system used in the professor demo bundle at `reports/professor_demo/cart_pendulum_hw3_named/`.

## 1. The Starting Equations

These are the exact equations given to the pipeline:

```latex
(m_1 + m_2)\ddot{x} + \frac{m_2 l}{2}\cos(\theta)\ddot{\theta} - \frac{m_2 l}{2}\sin(\theta)\dot{\theta}^2 + kx = 0
\frac{m_2 l}{2}\cos(\theta)\ddot{x} + \frac{1}{4}(m_2 l^2 + 4I)\ddot{\theta} + \frac{m_2 g l}{2}\sin(\theta) = 0
```

The top-level orchestrator that consumes the input file is:

- `pipeline/run_pipeline.py`
- `run_pipeline(source_path, ...)`

The frontend entrypoint is:

- `latex_frontend/translator.py`
- `translate_file(path)`

## 2. Normalization

The first real transformation is text normalization in:

- `latex_frontend/normalize.py`
- `normalize_latex(text)`

Normalization does not solve or parse anything. It rewrites supported LaTeX variants into a narrower deterministic grammar.

For this example, the exact normalized equations are:

```latex
(m_1 + m_2)\ddot{x} + \frac{m_2 l}{2}\cos(q)\ddot{q} - \frac{m_2 l}{2}\sin(q)\dot{q}^2 + kx = 0
\frac{m_2 l}{2}\cos(q)\ddot{x} + \frac{1}{4}(m_2 l^2 + 4I)\ddot{q} + \frac{m_2 g l}{2}\sin(q) = 0
```

What changed:

- `\theta` became `q`
- everything else stayed structurally the same

## 3. Tokenization

Tokenization happens in:

- `latex_frontend/tokenizer.py`
- `tokenize(text)`

The tokenizer turns the normalized string into a flat stream of tokens. It does not know algebra yet. It only recognizes commands, identifiers, numbers, operators, and grouping characters.

### Equation 1 Tokens

```python
Token(kind='LPAREN', value='(', position=0)
Token(kind='IDENT', value='m_1', position=1)
Token(kind='PLUS', value='+', position=5)
Token(kind='IDENT', value='m_2', position=7)
Token(kind='RPAREN', value=')', position=10)
Token(kind='COMMAND', value='ddot', position=11)
Token(kind='LBRACE', value='{', position=16)
Token(kind='IDENT', value='x', position=17)
Token(kind='RBRACE', value='}', position=18)
Token(kind='PLUS', value='+', position=20)
Token(kind='COMMAND', value='frac', position=22)
Token(kind='LBRACE', value='{', position=27)
Token(kind='IDENT', value='m_2', position=28)
Token(kind='IDENT', value='l', position=32)
Token(kind='RBRACE', value='}', position=33)
Token(kind='LBRACE', value='{', position=34)
Token(kind='NUMBER', value='2', position=35)
Token(kind='RBRACE', value='}', position=36)
Token(kind='COMMAND', value='cos', position=37)
Token(kind='LPAREN', value='(', position=41)
Token(kind='IDENT', value='q', position=42)
Token(kind='RPAREN', value=')', position=43)
Token(kind='COMMAND', value='ddot', position=44)
Token(kind='LBRACE', value='{', position=49)
Token(kind='IDENT', value='q', position=50)
Token(kind='RBRACE', value='}', position=51)
Token(kind='MINUS', value='-', position=53)
Token(kind='COMMAND', value='frac', position=55)
Token(kind='LBRACE', value='{', position=60)
Token(kind='IDENT', value='m_2', position=61)
Token(kind='IDENT', value='l', position=65)
Token(kind='RBRACE', value='}', position=66)
Token(kind='LBRACE', value='{', position=67)
Token(kind='NUMBER', value='2', position=68)
Token(kind='RBRACE', value='}', position=69)
Token(kind='COMMAND', value='sin', position=70)
Token(kind='LPAREN', value='(', position=74)
Token(kind='IDENT', value='q', position=75)
Token(kind='RPAREN', value=')', position=76)
Token(kind='COMMAND', value='dot', position=77)
Token(kind='LBRACE', value='{', position=81)
Token(kind='IDENT', value='q', position=82)
Token(kind='RBRACE', value='}', position=83)
Token(kind='CARET', value='^', position=84)
Token(kind='NUMBER', value='2', position=85)
Token(kind='PLUS', value='+', position=87)
Token(kind='IDENT', value='k', position=89)
Token(kind='IDENT', value='x', position=90)
Token(kind='EQUALS', value='=', position=92)
Token(kind='NUMBER', value='0', position=94)
Token(kind='EOF', value='', position=95)
```

### Equation 2 Tokens

```python
Token(kind='COMMAND', value='frac', position=0)
Token(kind='LBRACE', value='{', position=5)
Token(kind='IDENT', value='m_2', position=6)
Token(kind='IDENT', value='l', position=10)
Token(kind='RBRACE', value='}', position=11)
Token(kind='LBRACE', value='{', position=12)
Token(kind='NUMBER', value='2', position=13)
Token(kind='RBRACE', value='}', position=14)
Token(kind='COMMAND', value='cos', position=15)
Token(kind='LPAREN', value='(', position=19)
Token(kind='IDENT', value='q', position=20)
Token(kind='RPAREN', value=')', position=21)
Token(kind='COMMAND', value='ddot', position=22)
Token(kind='LBRACE', value='{', position=27)
Token(kind='IDENT', value='x', position=28)
Token(kind='RBRACE', value='}', position=29)
Token(kind='PLUS', value='+', position=31)
Token(kind='COMMAND', value='frac', position=33)
Token(kind='LBRACE', value='{', position=38)
Token(kind='NUMBER', value='1', position=39)
Token(kind='RBRACE', value='}', position=40)
Token(kind='LBRACE', value='{', position=41)
Token(kind='NUMBER', value='4', position=42)
Token(kind='RBRACE', value='}', position=43)
Token(kind='LPAREN', value='(', position=44)
Token(kind='IDENT', value='m_2', position=45)
Token(kind='IDENT', value='l', position=49)
Token(kind='CARET', value='^', position=50)
Token(kind='NUMBER', value='2', position=51)
Token(kind='PLUS', value='+', position=53)
Token(kind='NUMBER', value='4', position=55)
Token(kind='IDENT', value='I', position=56)
Token(kind='RPAREN', value=')', position=57)
Token(kind='COMMAND', value='ddot', position=58)
Token(kind='LBRACE', value='{', position=63)
Token(kind='IDENT', value='q', position=64)
Token(kind='RBRACE', value='}', position=65)
Token(kind='PLUS', value='+', position=67)
Token(kind='COMMAND', value='frac', position=69)
Token(kind='LBRACE', value='{', position=74)
Token(kind='IDENT', value='m_2', position=75)
Token(kind='IDENT', value='g', position=79)
Token(kind='IDENT', value='l', position=81)
Token(kind='RBRACE', value='}', position=82)
Token(kind='LBRACE', value='{', position=83)
Token(kind='NUMBER', value='2', position=84)
Token(kind='RBRACE', value='}', position=85)
Token(kind='COMMAND', value='sin', position=86)
Token(kind='LPAREN', value='(', position=90)
Token(kind='IDENT', value='q', position=91)
Token(kind='RPAREN', value=')', position=92)
Token(kind='EQUALS', value='=', position=94)
Token(kind='NUMBER', value='0', position=96)
Token(kind='EOF', value='', position=97)
```

## 4. Parsing Into Equation Nodes

Parsing happens in:

- `latex_frontend/parser.py`
- `Parser.parse_document()`
- `Parser.parse_equation()`
- `Parser.parse_expression()`
- `Parser.parse_term()`
- `Parser.parse_primary()`

The parser uses the token stream to build nested `EquationNode`, `AddNode`, `MulNode`, `DerivativeNode`, `FunctionNode`, `PowNode`, and `SymbolNode` objects.

The easiest exact representation to inspect is the deterministic SymPy-style rendering written by:

- `ir/equation_dict.py`
- `equation_to_string(node)`

For this example, the exact parsed equations are:

```text
-D1_q**2*l*m_2*sin(q)/2 + D2_q*l*m_2*cos(q)/2 + D2_x*(m_1 + m_2) + k*x = 0
D2_q*(4*I + l**2*m_2)/4 + D2_x*l*m_2*cos(q)/2 + g*l*m_2*sin(q)/2 = 0
```

Important notation:

- `D1_q` means `dq/dt`
- `D2_q` means `d^2q/dt^2`
- `D2_x` means `d^2x/dt^2`

## 5. Canonical Dictionary IR

Serialization happens in:

- `ir/equation_dict.py`
- `equation_to_dict(node)`

This is where the parsed tree becomes a deterministic plain-Python dict.

### Exact Canonical Dicts

```json
[
  {
    "op": "equation",
    "lhs": {
      "op": "add",
      "args": [
        {
          "op": "mul",
          "args": [
            {
              "op": "add",
              "args": [
                {
                  "op": "symbol",
                  "name": "m_1"
                },
                {
                  "op": "symbol",
                  "name": "m_2"
                }
              ]
            },
            {
              "op": "derivative",
              "base": "x",
              "order": 2
            }
          ]
        },
        {
          "op": "mul",
          "args": [
            {
              "op": "div",
              "args": [
                {
                  "op": "mul",
                  "args": [
                    {
                      "op": "symbol",
                      "name": "m_2"
                    },
                    {
                      "op": "symbol",
                      "name": "l"
                    }
                  ]
                },
                {
                  "op": "const",
                  "value": 2
                }
              ]
            },
            {
              "op": "cos",
              "args": [
                {
                  "op": "symbol",
                  "name": "q"
                }
              ]
            },
            {
              "op": "derivative",
              "base": "q",
              "order": 2
            }
          ]
        },
        {
          "op": "neg",
          "args": [
            {
              "op": "mul",
              "args": [
                {
                  "op": "div",
                  "args": [
                    {
                      "op": "mul",
                      "args": [
                        {
                          "op": "symbol",
                          "name": "m_2"
                        },
                        {
                          "op": "symbol",
                          "name": "l"
                        }
                      ]
                    },
                    {
                      "op": "const",
                      "value": 2
                    }
                  ]
                },
                {
                  "op": "sin",
                  "args": [
                    {
                      "op": "symbol",
                      "name": "q"
                    }
                  ]
                },
                {
                  "op": "pow",
                  "args": [
                    {
                      "op": "derivative",
                      "base": "q",
                      "order": 1
                    },
                    {
                      "op": "const",
                      "value": 2
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          "op": "mul",
          "args": [
            {
              "op": "symbol",
              "name": "k"
            },
            {
              "op": "symbol",
              "name": "x"
            }
          ]
        }
      ]
    },
    "rhs": {
      "op": "const",
      "value": 0
    }
  },
  {
    "op": "equation",
    "lhs": {
      "op": "add",
      "args": [
        {
          "op": "mul",
          "args": [
            {
              "op": "div",
              "args": [
                {
                  "op": "mul",
                  "args": [
                    {
                      "op": "symbol",
                      "name": "m_2"
                    },
                    {
                      "op": "symbol",
                      "name": "l"
                    }
                  ]
                },
                {
                  "op": "const",
                  "value": 2
                }
              ]
            },
            {
              "op": "cos",
              "args": [
                {
                  "op": "symbol",
                  "name": "q"
                }
              ]
            },
            {
              "op": "derivative",
              "base": "x",
              "order": 2
            }
          ]
        },
        {
          "op": "mul",
          "args": [
            {
              "op": "div",
              "args": [
                {
                  "op": "const",
                  "value": 1
                },
                {
                  "op": "const",
                  "value": 4
                }
              ]
            },
            {
              "op": "add",
              "args": [
                {
                  "op": "mul",
                  "args": [
                    {
                      "op": "symbol",
                      "name": "m_2"
                    },
                    {
                      "op": "pow",
                      "args": [
                        {
                          "op": "symbol",
                          "name": "l"
                        },
                        {
                          "op": "const",
                          "value": 2
                        }
                      ]
                    }
                  ]
                },
                {
                  "op": "mul",
                  "args": [
                    {
                      "op": "const",
                      "value": 4
                    },
                    {
                      "op": "symbol",
                      "name": "I"
                    }
                  ]
                }
              ]
            },
            {
              "op": "derivative",
              "base": "q",
              "order": 2
            }
          ]
        },
        {
          "op": "mul",
          "args": [
            {
              "op": "div",
              "args": [
                {
                  "op": "mul",
                  "args": [
                    {
                      "op": "symbol",
                      "name": "m_2"
                    },
                    {
                      "op": "symbol",
                      "name": "g"
                    },
                    {
                      "op": "symbol",
                      "name": "l"
                    }
                  ]
                },
                {
                  "op": "const",
                  "value": 2
                }
              ]
            },
            {
              "op": "sin",
              "args": [
                {
                  "op": "symbol",
                  "name": "q"
                }
              ]
            }
          ]
        }
      ]
    },
    "rhs": {
      "op": "const",
      "value": 0
    }
  }
]
```

## 6. Target Derivative Detection

Target selection happens in:

- `states/rules.py`
- `collect_derivative_orders(equations)`

This stage scans all parsed equations and asks:

- which base variables appear with derivatives
- what is the highest derivative order for each base variable

For this example, the exact result is:

```text
q -> order 2
x -> order 2
```

So the exact highest-derivative solve targets are:

```text
D2_q
D2_x
```

This is why the solver isolates the two accelerations simultaneously.

## 7. Residual Equations Used by the Algebra Solver

Residual conversion happens in:

- `ir/equation_dict.py`
- `equation_to_residual(node)`

Each equation is rewritten as:

```text
lhs - rhs = 0
```

For this example, the exact residuals are:

```text
-D1_q**2*l*m_2*sin(q)/2 + D2_q*l*m_2*cos(q)/2 + D2_x*(m_1 + m_2) + k*x
D2_q*(4*I + l**2*m_2)/4 + D2_x*l*m_2*cos(q)/2 + g*l*m_2*sin(q)/2
```

## 8. Solving the Coupled Highest Derivatives

Derivative isolation happens in:

- `canonicalize/solve_for_derivatives.py`
- `solve_for_highest_derivatives(equations)`

The solver is SymPy. It treats `D2_q` and `D2_x` as algebraic unknowns and solves the coupled nonlinear system for them.

The exact solved derivatives are:

```text
D2_q = l*m_2*(-D1_q**2*l*m_2*sin(2*q) - 4*g*m_1*sin(q) - 4*g*m_2*sin(q) + 4*k*x*cos(q))/(8*I*m_1 + 8*I*m_2 + 2*l**2*m_1*m_2 + 2*l**2*m_2**2*sin(q)**2)

D2_x = (4*D1_q**2*I*l*m_2*sin(q) + D1_q**2*l**3*m_2**2*sin(q) - 8*I*k*x + g*l**2*m_2**2*sin(2*q) - 2*k*l**2*m_2*x)/(8*I*m_1 + 8*I*m_2 + 2*l**2*m_1*m_2 + 2*l**2*m_2**2*sin(q)**2)
```

Conceptually:

- the two original second-order equations are consumed together
- the output is one explicit acceleration equation for `q` and one for `x`

## 9. State Extraction

State extraction happens in:

- `states/extract_states.py`
- `extract_states(equations)`

For this system, the exact extraction result is:

```json
{
  "states": ["q", "q_dot", "x", "x_dot"],
  "inputs": [],
  "parameters": ["I", "g", "k", "l", "m_1", "m_2"],
  "derivative_orders": {
    "q": 2,
    "x": 2
  }
}
```

That means:

- `q` and `x` are the base states
- `q_dot` and `x_dot` are derived first-order states
- there are no external inputs in this run
- `I, g, k, l, m_1, m_2` are treated as parameters

## 10. First-Order Conversion

First-order conversion happens in:

- `canonicalize/first_order.py`
- `build_first_order_system(equations, extraction, solved_derivatives)`

The exact first-order system is:

```text
d/dt q = q_dot

d/dt q_dot = l*m_2*(-4*g*m_1*sin(q) - 4*g*m_2*sin(q) + 4*k*x*cos(q) - l*m_2*q_dot**2*sin(2*q))/(8*I*m_1 + 8*I*m_2 + 2*l**2*m_1*m_2 + 2*l**2*m_2**2*sin(q)**2)

d/dt x = x_dot

d/dt x_dot = (-8*I*k*x + 4*I*l*m_2*q_dot**2*sin(q) + g*l**2*m_2**2*sin(2*q) - 2*k*l**2*m_2*x + l**3*m_2**2*q_dot**2*sin(q))/(8*I*m_1 + 8*I*m_2 + 2*l**2*m_1*m_2 + 2*l**2*m_2**2*sin(q)**2)
```

This is the point where the nonlinear physics becomes an explicit state-space-like evolution law, but still nonlinear.

## 11. Explicit-Form Summary

The pipeline stores the explicit first-order form as:

```json
{
  "form": "explicit_first_order",
  "rhs": {
    "q": "q_dot",
    "q_dot": "l*m_2*(-4*g*m_1*sin(q) - 4*g*m_2*sin(q) + 4*k*x*cos(q) - l*m_2*q_dot**2*sin(2*q))/(8*I*m_1 + 8*I*m_2 + 2*l**2*m_1*m_2 + 2*l**2*m_2**2*sin(q)**2)",
    "x": "x_dot",
    "x_dot": "(-8*I*k*x + 4*I*l*m_2*q_dot**2*sin(q) + g*l**2*m_2**2*sin(2*q) - 2*k*l**2*m_2*x + l**3*m_2**2*q_dot**2*sin(q))/(8*I*m_1 + 8*I*m_2 + 2*l**2*m_1*m_2 + 2*l**2*m_2**2*sin(q)**2)"
  }
}
```

Because this system is nonlinear, the linear state-space branch is skipped. The exact state-space artifact says:

```text
unavailable: nonlinear explicit system
```

The linearity analysis is produced by:

- `canonicalize/linearity_check.py`
- `analyze_first_order_linearity(first_order_system)`

and correctly marks this example as nonlinear.

## 12. Graph Lowering

Graph lowering happens in:

- `ir/graph_lowering.py`
- `lower_first_order_system_graph(first_order_system, name=...)`

This stage converts the first-order system into a reusable signal-flow graph. It creates nodes for:

- constants
- symbol inputs / parameters
- state signals
- sums
- products / gains
- divides
- powers
- trig functions
- integrators

For this exact example, the graph summary is:

```json
{
  "name": "cart_pendulum_hw3",
  "node_count": 47,
  "edge_count": 101,
  "ops": [
    "constant",
    "cos",
    "div",
    "gain",
    "integrator",
    "mul",
    "pow",
    "sin",
    "state_signal",
    "sum",
    "symbol_input"
  ]
}
```

The exact state chains are:

```json
[
  {
    "state": "q",
    "signal": "state_q",
    "integrator": "integrator_q",
    "rhs": "state_q_dot"
  },
  {
    "state": "q_dot",
    "signal": "state_q_dot",
    "integrator": "integrator_q_dot",
    "rhs": "expr_0020"
  },
  {
    "state": "x",
    "signal": "state_x",
    "integrator": "integrator_x",
    "rhs": "state_x_dot"
  },
  {
    "state": "x_dot",
    "signal": "state_x_dot",
    "integrator": "integrator_x_dot",
    "rhs": "expr_0028"
  }
]
```

Conceptually this says:

- `q_dot` integrates to `q`
- `expr_0020` computes `q_ddot` and feeds the `q_dot` integrator
- `x_dot` integrates to `x`
- `expr_0028` computes `x_ddot` and feeds the `x_dot` integrator

## 13. Lowering the Graph to a Simulink Model Dictionary

Simulink lowering happens in:

- `backend/graph_to_simulink.py`
- `graph_to_simulink_model(graph, ...)`

This stage maps graph ops to actual block choices:

- `integrator` -> Integrator
- `sum` -> Sum
- `mul` -> Product or Gain
- `div` -> Divide or Gain
- `sin` / `cos` -> Trigonometric Function
- constants / parameters -> Constant

It also:

- groups blocks by state subsystem
- assigns deterministic positions
- creates trace labels for wires

The resulting backend model dictionary is then validated by:

- `backend/simulink_dict.py`
- `validate_simulink_model_dict(model_dict)`

## 14. Building the Real `.slx`

Actual model construction happens in:

- `backend/builder.py`
- `build_simulink_model(eng, model_dict, ...)`

This function:

- starts from the hierarchical backend model dict
- creates the model in MATLAB
- adds blocks in deterministic order
- sets positions and block parameters
- adds lines
- updates the model
- saves the `.slx`

For this run, the exact generated model was:

```text
/Users/chancelavoie/Desktop/simulinkcopilot/workspace/generated_models/professor_demo_models/cart_pendulum_hw3_simulink.slx
```

## 15. Simulation Runtime Used for This Example

The exact runtime parameters were:

```json
{
  "parameter_values": {
    "I": 0.17,
    "g": 9.81,
    "k": 100.0,
    "l": 1.0,
    "m_1": 10.0,
    "m_2": 2.0
  },
  "initial_conditions": {
    "q": 0.7853981633974483,
    "q_dot": 0.0,
    "x": 1.0,
    "x_dot": 0.0
  },
  "expected_linear": false
}
```

That corresponds to:

- `q(0) = pi/4`
- `q_dot(0) = 0`
- `x(0) = 1`
- `x_dot(0) = 0`

## 16. Python and Simulink Simulation

Python ODE simulation happens in:

- `simulate/ode_sim.py`
- `simulate_ode_system(first_order_system, ...)`

Simulink build + simulation happens in:

- `backend/simulate_simulink.py`
- `simulate_simulink_model(eng, model_dict, ...)`

Signal extraction happens in:

- `backend/extract_signals.py`
- `extract_simulink_signals(eng, sim_output, ...)`

## 17. Final Numerical Validation

Simulink-vs-ODE comparison happens in:

- `backend/validate_simulink.py`
- `compare_simulink_results(simulink_result, ode_result, ...)`

For this exact run, the validation result was:

```json
{
  "vs_ode": {
    "rmse": 1.2302390546687176e-09,
    "max_abs_error": 2.1170118102986635e-08,
    "per_state_rmse": {
      "q": 4.306220930540789e-10,
      "q_dot": 2.298887170763235e-09,
      "x": 1.2796335007798429e-10,
      "x_dot": 7.53166845154162e-10
    },
    "per_state_max_abs_error": {
      "q": 1.0789408255718058e-09,
      "q_dot": 2.1170118102986635e-08,
      "x": 3.3170177715646787e-10,
      "x_dot": 6.907467930972189e-09
    },
    "tolerance": 1e-06,
    "passes": true
  },
  "vs_state_space": null,
  "passes": true
}
```

This is the final proof that the generated nonlinear Simulink model matches the Python ODE reference for this system.

## 18. What To Open If You Want To Follow This In Code

Open these files in this order:

1. `pipeline/run_pipeline.py`
2. `latex_frontend/normalize.py`
3. `latex_frontend/tokenizer.py`
4. `latex_frontend/parser.py`
5. `ir/equation_dict.py`
6. `states/extract_states.py`
7. `canonicalize/solve_for_derivatives.py`
8. `canonicalize/first_order.py`
9. `canonicalize/linearity_check.py`
10. `ir/graph_lowering.py`
11. `ir/graph_validate.py`
12. `backend/graph_to_simulink.py`
13. `backend/builder.py`
14. `backend/simulate_simulink.py`
15. `backend/extract_signals.py`
16. `backend/validate_simulink.py`

## 19. Short Summary

For this nonlinear example, the pipeline did exactly this:

1. read the raw LaTeX equations
2. normalized `\theta -> q`
3. tokenized both equations
4. parsed them into equation trees
5. serialized those trees into canonical dict IR
6. detected the highest derivative targets `D2_q` and `D2_x`
7. converted both equations to residual form
8. solved the coupled nonlinear algebraic system for `D2_q` and `D2_x`
9. expanded the model into the first-order states `q`, `q_dot`, `x`, `x_dot`
10. lowered that first-order system into a signal-flow graph
11. lowered the graph into a grouped, readable Simulink model
12. simulated both Python and Simulink versions
13. verified that they matched within tolerance

This is the full nonlinear path. The only thing intentionally skipped was linear state-space generation, because the system is nonlinear.
