# Layout Rule Ledger

This ledger records the layout rules considered for the readable Simulink backend, the authority behind each rule, the deterministic mapping used in code, and the current verification status.

## Adopted rules

### LAYOUT-001

- Short name: main_signal_flow_left_to_right
- Source type: vendor_guidance
- Source title: MathWorks MAB guideline `db_0141: Signal flow in Simulink models`
- Source version or date: Version 6.0, accessed 2026-03-26
- Source URL: https://www.mathworks.com/help/slcheck/ref/check-signal-flow-in-model.html
- Clause / guideline / section: `db_0141_a`, `db_0141_b`
- Scope: Simulink model and subsystem signal-flow direction
- Finding: Sequential signal flow should run left to right; feedback is the explicit exception; parallel groups should be arranged top to bottom.
- Deterministic mapping: Root and subsystem blocks are assigned to stable role columns; reverse-flow edges are allowed but tracked as feedback-like exceptions; column refinement reorders non-port columns by connection barycenter while keeping overall left-to-right layering stable.
- Exceptions: Right-to-left routing is tolerated for feedback-like edges.
- Confidence: high
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_deterministic_layout_preserves_or_improves_metric_score_vs_legacy`
  - `backend/tests/test_layout.py::test_measure_layout_reports_reverse_flow_for_feedback_connection`
  - `workspace/layout_bench/coupled_system/summary.json`
  - `workspace/layout_bench/two_mass_coupled/summary.json`

### LAYOUT-002

- Short name: inports_left_outports_right
- Source type: vendor_guidance
- Source title: MathWorks MAB guideline `db_0042: Usage of Inport and Outport blocks`
- Source version or date: Version 6.0, accessed 2026-03-26
- Source URL: https://www.mathworks.com/help/simulink/mdl_gd/maab/db_0042usageofinportandoutportblocks.html
- Clause / guideline / section: `db_0042_a`, `db_0042_b`
- Scope: Positioning of Inport and Outport blocks
- Finding: Inports belong on the left side of the diagram and Outports belong on the right, with crossing-avoidance as the stated exception.
- Deterministic mapping: Fixed root and subsystem port columns (`ROOT_SOURCE_X`, `ROOT_OUTPORT_X`, `SUBSYSTEM_INPORT_X`, `SUBSYSTEM_OUTPORT_X`) anchor port placement.
- Exceptions: A future visual-corrector move may slightly offset ports only if semantics remain unchanged and readability improves without violating hard constraints.
- Confidence: high
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_root_column_spacing_grows_with_long_connection_labels`
  - `backend/tests/test_layout.py::test_root_row_spacing_grows_with_multiline_trace_budget`
  - `workspace/layout_bench/simple_gain_chain/summary.json`

### LAYOUT-003

- Short name: block_outputs_face_right
- Source type: vendor_guidance
- Source title: MathWorks MAB guideline `jc_0110: Direction of block`
- Source version or date: Version 6.0, accessed 2026-03-26
- Source URL: https://www.mathworks.com/help/simulink/mdl_gd/maab/jc_0110directionofblock.html
- Clause / guideline / section: `jc_0110_a`
- Scope: Block orientation and diagram reading direction
- Finding: Blocks should be arranged so the output is to the right; delay blocks in feedback loops are the explicit exception.
- Deterministic mapping: The layout engine keeps feedforward blocks in left-to-right column order and treats reverse-flow edges as exceptional paths rather than normal ordering cues.
- Exceptions: Delay-like feedback exceptions are recorded in the ledger but not yet specially placed by the deterministic engine.
- Confidence: high
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_measure_layout_reports_reverse_flow_for_feedback_connection`
  - `workspace/layout_bench/driven_oscillator/summary.json`

### LAYOUT-004

- Short name: signal_line_crossings_and_block_overdraw_minimized
- Source type: vendor_guidance
- Source title: MathWorks MAB guideline `db_0032: Signal line connections`
- Source version or date: Version 6.0, accessed 2026-03-26
- Source URL: https://www.mathworks.com/help/simulink/mdl_gd/maab/db_0032signallineconnections.html
- Clause / guideline / section: `db_0032_b`, `db_0032_c`
- Scope: Signal-line readability
- Finding: Signal lines should be resized for layout and should not bend multiple times unnecessarily; crossings and line clutter impair readability.
- Deterministic mapping: `backend/layout_metrics.py` computes connection crossings, block-line crossings, and bend counts; the visual validator rejects candidate patches that worsen block-line crossings.
- Exceptions: The backend uses deterministic orthogonal route proxies for scoring because the model dictionary does not store final Simulink autoroute geometry.
- Confidence: high
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_deterministic_layout_preserves_or_improves_metric_score_vs_legacy`
  - `backend/tests/test_layout_visual_corrector.py::test_visual_patch_validator_rejects_resizing_moves`
  - `workspace/layout_bench/summary.json`

### LAYOUT-005

- Short name: subsystems_express_functional_units
- Source type: vendor_guidance
- Source title: MathWorks MAB guideline `db_0144: Use of subsystems`
- Source version or date: Version 6.0, accessed 2026-03-26
- Source URL: https://www.mathworks.com/help/simulink/mdl_gd/maab/db_0144useofsubsystems.html
- Clause / guideline / section: `db_0144_a`
- Scope: Subsystem usage and readability
- Finding: Blocks should be grouped into subsystems based on functional decomposition rather than merely to save space.
- Deterministic mapping: Existing subsystem ownership is preserved; subsystem blocks receive dedicated root columns; subsystem balance is measured as a readability metric; the visual-corrector is forbidden from changing subsystem membership.
- Exceptions: None in the current implementation.
- Confidence: high
- Adopted: yes
- Tests:
  - `backend/tests/test_layout_visual_corrector.py::test_apply_visual_repair_noops_when_patch_has_no_moves`
  - `workspace/layout_bench/three_mass_coupled/summary.json`

### LAYOUT-006

- Short name: page_fit_reviewability
- Source type: vendor_guidance
- Source title: MathWorks Model Quality Objectives `MQR-01`
- Source version or date: Version 1.0 white paper, accessed 2026-03-26
- Source URL: https://in.mathworks.com/content/dam/mathworks/white-paper/mqo-paper-v1-0.pdf
- Clause / guideline / section: `3.2.1 Model layout`, `MQR-01`
- Scope: Model-review readability on screen and paper
- Finding: Model diagrams should be completely visible on A4 paper size; zoom ratios below roughly 80% are harder to review.
- Deterministic mapping: `measure_layout()` computes root-canvas width, height, and an estimated page-count proxy; the visual validator rejects patches that increase estimated page count.
- Exceptions: The backend uses a coarse page proxy, not a literal Simulink zoom measurement.
- Confidence: medium
- Adopted: yes
- Tests:
  - `backend/tests/test_layout_visual_corrector.py::test_apply_visual_repair_accepts_improving_patch_and_records_metadata`
  - `workspace/layout_bench/coupled_system/summary.json`
  - `workspace/layout_bench/three_mass_coupled/summary.json`

### LAYOUT-007

- Short name: crossings_have_priority_over_bends
- Source type: empirical_literature
- Source title: Helen Purchase, "Which Aesthetic Has the Greatest Effect on Human Understanding?"
- Source version or date: 1997
- Source URL: https://eprints.gla.ac.uk/35804/
- Clause / guideline / section: abstract / empirical result summary
- Scope: Graph readability heuristics
- Finding: Edge crossings have the strongest effect on human understanding; bends matter, but less.
- Deterministic mapping: Composite scoring weights crossing penalties substantially more heavily than bend penalties in `backend/layout_metrics.py`.
- Exceptions: This is a readability heuristic, not a formal standard.
- Confidence: high
- Adopted: yes
- Tests:
  - `workspace/layout_bench/summary.md`
  - `workspace/layout_bench/coupled_system/summary.json`
  - `workspace/layout_bench/two_mass_coupled/summary.json`

### LAYOUT-008

- Short name: layered_orthogonal_column_layout
- Source type: house_rule
- Source title: Derived implementation rule informed by ELK layered-layout documentation and MathWorks signal-flow guidance
- Source version or date: accessed 2026-03-26
- Source URL: https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html
- Clause / guideline / section: layered direction and orthogonal-routing description
- Scope: Deterministic auto-layout algorithm selection
- Finding: A layered strategy that keeps most edges in one direction and uses orthogonal routing is a strong implementation fit for engineering block diagrams.
- Deterministic mapping: The engine uses stable role-based columns, layer hints, orthogonal route proxies, and iterative spacing repair rather than unconstrained force layout.
- Exceptions: This is an implementation choice, not a formal requirement.
- Confidence: medium
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_root_column_spacing_grows_with_long_connection_labels`
  - `backend/tests/test_layout.py::test_subsystem_column_spacing_grows_with_long_internal_trace_labels`

### LAYOUT-009

- Short name: explicit_integrator_chain_ordering
- Source type: house_rule
- Source title: Derived readability rule from state-order metadata, MAB signal-flow goals, and repo traceability data
- Source version or date: adopted 2026-03-26
- Source URL: https://www.mathworks.com/help/slcheck/ref/check-signal-flow-in-model.html
- Clause / guideline / section: derived from `db_0141` readability goal plus repo state-order metadata
- Scope: Higher-order state-chain presentation
- Finding: Formal standards do not specify how to present chained integrators, but explicitly ordered state chains are materially easier to read than mixed or hidden state placement.
- Deterministic mapping: `annotate_integrator_orders()` adds `state_order`; subsystem layouts use a dedicated integrator column; integrators are vertically ordered by derivative order; the visual-corrector includes `align_integrator_chain` as an allowed reason code.
- Exceptions: The exact vertical convention is a project rule, not a MathWorks or ISO requirement.
- Confidence: medium
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_integrator_chain_layout_orders_higher_derivatives_above_lower_state_blocks`
  - `backend/tests/test_layout.py::test_subsystem_column_spacing_grows_with_long_internal_trace_labels`

### LAYOUT-010

- Short name: column_barycenter_refinement
- Source type: house_rule
- Source title: Derived deterministic post-pass for readability scaling
- Source version or date: adopted 2026-03-26
- Source URL: https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html
- Clause / guideline / section: derived from layered crossing-minimization practice
- Scope: Intra-column ordering for dense models
- Finding: The MAB rules define readability goals but not a specific auto-layout algorithm, so a deterministic column-refinement sweep is required to improve ordering inside shared columns.
- Deterministic mapping: `_refine_system_layout()` repeatedly sorts non-port, non-integrator column members by weighted neighbor barycenter and restacks them with deterministic tie-breakers.
- Exceptions: Ports and integrator columns are excluded from refinement to preserve stronger invariants.
- Confidence: medium
- Adopted: yes
- Tests:
  - `backend/tests/test_layout.py::test_deterministic_layout_preserves_or_improves_metric_score_vs_legacy`
  - `workspace/layout_bench/summary.md`

### LAYOUT-011

- Short name: image_feedback_patch_only_visual_repair
- Source type: house_rule
- Source title: Project guardrail for post-layout visual correction
- Source version or date: adopted 2026-03-26
- Source URL: https://platform.openai.com/docs/guides/images-vision
- Clause / guideline / section: project policy, not external layout standard
- Scope: Optional post-layout visual polish
- Finding: The standards and official Simulink guidance do not define a final pixel-level repair stage, so the repo uses a constrained image-feedback loop that can move blocks but cannot change semantics.
- Deterministic mapping: `backend/layout_visual_corrector.py` renders the current system to PNG, obtains a structured critique and patch, validates schema and bounded motion, and applies only score-improving block-position moves.
- Exceptions: None; fail-closed no-op is mandatory when the patch is invalid or non-improving.
- Confidence: high
- Adopted: yes
- Tests:
  - `backend/tests/test_layout_visual_corrector.py::test_apply_visual_repair_accepts_improving_patch_and_records_metadata`
  - `backend/tests/test_layout_visual_corrector.py::test_apply_visual_repair_noops_when_patch_has_no_moves`
  - `backend/tests/test_layout_visual_corrector.py::test_visual_patch_validator_rejects_resizing_moves`

## Rejected or deferred rules

### LAYOUT-012

- Short name: delay_block_hierarchy_for_feedback_loops
- Source type: vendor_guidance
- Source title: MathWorks MAB guideline `jc_0653: Delay block layout in feedback loops`
- Source version or date: Version 6.0, accessed 2026-03-26
- Source URL: https://www.mathworks.com/help/simulink/mdl_gd/maab/jc_0653delayblocklayoutinfeedbackloops.html
- Clause / guideline / section: `jc_0653_a`
- Scope: Delay placement across subsystem boundaries in feedback loops
- Finding: Delay blocks in feedback loops across subsystems should reside in the hierarchy that describes the feedback loop.
- Deterministic mapping: Not yet implemented.
- Exceptions: None
- Confidence: high
- Adopted: no
- Rejection reason: The current repo layout engine does not yet build special-case hierarchy placement for Delay or Memory blocks in cross-subsystem feedback loops. The rule is recorded for a future pass rather than misrepresented as implemented.
- Tests: none yet

### LAYOUT-013

- Short name: iso_iec_symbol_standards_as_direct_auto_layout_rules
- Source type: normative_standard
- Source title: ISO 14617 / IEC 61082-1 / IEC 60617
- Source version or date: ISO 14617-1:2025, ISO 14617-2:2025, IEC 61082-1:2014, accessed 2026-03-26
- Source URL: https://www.iso.org/standard/85641.html
- Clause / guideline / section: standards scope statements and catalog definitions
- Scope: Diagram symbols, notation, and documentation preparation
- Finding: These standards govern symbol semantics and document preparation discipline, but they do not provide a direct Simulink-specific auto-layout policy for integrator columns, feedback routing, or pixel spacing.
- Deterministic mapping: None
- Exceptions: None
- Confidence: high
- Adopted: no
- Rejection reason: Using ISO / IEC symbol standards as if they defined Simulink block-placement policy would overstate the evidence.
- Tests: none
