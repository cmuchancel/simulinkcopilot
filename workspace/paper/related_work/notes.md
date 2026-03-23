# Literature Notes

## Why these papers and guides were collected

The paper's related-work framing has to distinguish Eqn2Sim from three different baselines:

1. equation-based modeling languages and symbolic compiler stacks
2. native MATLAB/Simulink workflows
3. symbolic analysis of already-existing Simulink models

## Comparison framing used in the manuscript

### Modelica / OpenModelica
- Strong baseline for declarative physical-system modeling.
- Much broader than Eqn2Sim in language scope and acausal modeling power.
- Different target artifact: simulator-ready code and integrated modeling environments, not compilation of restricted engineering equation notation into a readable Simulink block diagram.

### ModelingToolkit / Modia
- Represent current symbolic, graph-transformation-oriented state of the art for equation-based numerical model generation.
- Strong on transformations, solver-facing code, and symbolic optimizations.
- Not primarily aimed at emitting inspectable Simulink diagrams from equation notes.

### Simscape
- Closest industrial baseline inside the MATLAB ecosystem.
- Still requires writing models in Simscape's own component language and workflow.
- Eqn2Sim is positioned as an automation layer for engineers who already have equations and want a generated Simulink artifact without rewriting into a different modeling language first.

### SimCheck
- Relevant because it operates on Simulink models using symbolic/type-oriented reasoning.
- Useful contrast: SimCheck starts after the model exists, while Eqn2Sim automates equation-to-model construction.

### Manual Simulink
- Important status quo baseline.
- High flexibility, but the translation from equations to blocks is manual and difficult to validate rigorously.

## Claims the paper can support cleanly

- Deterministic equation-to-Simulink compilation on a restricted language.
- Real `.slx` generation and MATLAB-backed validation.
- Readable model output as a first-class result.
- Benchmark-defined capability boundary and explicit unsupported cases.

## Claims the paper should avoid

- General equation understanding.
- Broad DAE/PDE support.
- Replacement of full equation-based modeling languages.
- State-of-the-art symbolic modeling in the broadest sense.
