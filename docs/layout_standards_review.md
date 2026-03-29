# Layout Standards Review

## Scope

This review was produced for the readable Simulink backend in this repo. The goal is not to invent a generic diagram-style guide; it is to identify which parts of block-diagram appearance are actually governed by formal standards, which parts are governed by official MathWorks guidance, and which parts must be treated as source-backed house rules.

## Evidence hierarchy

1. Normative standards and standards-body publications
2. Official MathWorks guidance and MAB/JMAAB material
3. Primary literature on graph readability and layered / orthogonal layout
4. Tool documentation used only as implementation reference

## What formal standards actually cover

### ISO 14617 and IEC 60617

- ISO 14617-1:2025 covers general rules and guidance for preparing and presenting graphical symbols for diagrams.
- ISO 14617-2:2025 is the symbol library for industrial components and processing.
- ISO 14617-2 explicitly excludes electrotechnical objects and points users to the IEC 60617 database for those symbols.
- IEC 60617 is the authoritative symbol database for electrotechnical diagrams.

Practical conclusion:

- These sources matter for symbol semantics and notation discipline.
- They do not provide a Simulink-specific algorithm for where to place integrators, how wide a column gap should be, or how to route a feedback loop in a generated model.
- They are relevant to "what the symbols mean" and to presentation discipline, not to end-to-end Simulink auto-layout policy.

### IEC 61082-1

- IEC 61082-1:2014 establishes general rules and guidelines for the presentation of information in documents, and specific rules for diagrams, drawings, and tables used in electrotechnology.
- This is the closest formal standards-body source for diagram-document preparation.

Practical conclusion:

- IEC 61082-1 supports the idea that diagrams are documents that should be readable and presented systematically.
- It still does not give a direct Simulink block-placement policy.
- We use it as a formal backdrop for document-quality expectations, not as a source for pixel-level layout rules.

## What official MathWorks guidance covers

This is the strongest source category for actual Simulink-style layout behavior.

### MAB / JMAAB guidance

- MathWorks describes the MAB Guidelines as a set of modeling guidelines developed by an independent industry working group for MATLAB, Simulink, Stateflow, and Embedded Coder.
- MathWorks states that Simulink Check provides industry-recognized checks and metrics and supports MAB-style guidelines.

The key layout-relevant MAB rules used here are:

- `db_0032` Signal line connections
  - vertical and horizontal signal lines should not cross
  - overlapping signal lines should be avoided
  - lines should not cross blocks
  - unnecessary branching complexity should be avoided
  - consistent line sizing improves readability
- `db_0141` Signal flow in Simulink models
  - signals should flow left to right
  - feedback loops may flow right to left
  - parallel blocks / subsystems should be arranged top to bottom
  - signal lines should not bend multiple times unnecessarily
- `jc_0110` Direction of block
  - blocks should be arranged so outputs are on the right
  - delay blocks in feedback loops are the explicit exception
- `db_0042` Usage of Inport and Outport blocks
  - Inport blocks should be on the left side of the diagram
  - Outport blocks belong on the right side
- `db_0144` Use of subsystems
  - subsystems should be used to alleviate readability issues
  - blocks should be grouped by functional unit
  - subsystems should not be introduced primarily to save space
- `jc_0653` Delay block layout in feedback loops
  - delay blocks in feedback loops should reside in the hierarchy that describes the loop

Practical conclusion:

- These are the clearest "industry-standard-for-Simulink" style rules available to us.
- They justify left-to-right flow, explicit feedback exceptions, left/right port conventions, top-to-bottom parallel ordering, bend minimization, and function-based subsystem structure.
- They do not fully define higher-order chain presentation. For that, we still need derived rules.

### Model quality guidance

- MathWorks Model Quality Objectives (`MQR-01`) states that model diagrams should be completely visible on A4 paper size and notes that zoom ratios under roughly 80% hurt readability and reviewability.

Practical conclusion:

- This is the best official source for a page-fit / reviewability objective.
- We use it as justification for a page-count proxy and canvas-size penalties in the benchmark metrics.

## What the literature covers

### Human readability findings

- Helen Purchase's 1997 empirical study reports that reducing edge crossings has by far the strongest effect on human understanding; minimizing bends and maximizing symmetry matter less.

Practical conclusion:

- Crossing minimization is the strongest literature-backed readability heuristic available.
- Bend minimization matters, but it is secondary to crossings.

### Layered / orthogonal layout

- The ELK layered-layout reference states that the layered method arranges as many edges as possible in one direction, organizes nodes into layers, then reorders them to minimize crossings.
- ELK also explicitly notes that orthogonal routing with port constraints enables block-diagram and circuit-schematic style layout.

Practical conclusion:

- This is a strong implementation reference for deterministic block-diagram layout strategy.
- We use layered placement and orthogonal route proxies as implementation choices, not as formal standards.

## Source-backed deterministic rules adopted in this repo

### Directly sourced from MathWorks guidance

- Main feedforward flow is left to right.
- Reverse flow is reserved for feedback paths.
- Inputs stay on the left; outputs stay on the right.
- Parallel elements are ordered top to bottom.
- Extra bends are penalized.
- Signal-line crossings and line-over-block conditions are penalized.
- Subsystems are used to express functional grouping, not just compression.
- Page-fit / reviewability is measured.

### Derived house rules

- Integrator chains are made explicit in a dedicated integrator column and kept vertically ordered by derivative order.
- The deterministic layout engine uses refinement sweeps to reorder blocks within columns based on connection barycenters, because the MAB rules specify the readability goal but not the exact auto-layout algorithm.
- A visual-repair agent is allowed to adjust positions only after deterministic layout, because the standards and official guidance are silent on final sub-column polish.

## What remains outside formal standards

- exact inter-column spacing
- exact row spacing
- exact text wrapping policy
- the specific scoring function used by the validator
- the exact motion limits for the visual repair stage
- the vertical visual convention used for higher-order integrator chains

These are intentionally labeled as source-backed house rules rather than misrepresented as ISO / IEC requirements.

## Sources

- ISO 14617-1:2025: https://www.iso.org/standard/85641.html
- ISO 14617-2:2025: https://www.iso.org/standard/83364.html
- IEC 60617 database: https://webstore.iec.ch/en/publication/2723
- IEC 61082-1:2014: https://webstore.iec.ch/en/publication/4469
- MathWorks MAB Guidelines overview: https://www.mathworks.com/solutions/mab-guidelines.html
- MAB guideline PDF v5: https://www.mathworks.com/content/dam/mathworks/mathworks-dot-com/solutions/mab/mab-control-algorithm-modeling-guidelines-using-matlab-simulink-and-stateflow-v5.pdf
- Simulink Check overview: https://www.mathworks.com/products/simulink-check.html
- Check Model Compliance: https://www.mathworks.com/help/slcheck/check-model-compliance.html
- Model Quality Objectives v1.0: https://www.mathworks.com/content/dam/mathworks/white-paper/mqo-paper-v1-0.pdf
- Purchase 1997 abstract: https://eprints.gla.ac.uk/35804/
- ELK layered layout reference: https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html
