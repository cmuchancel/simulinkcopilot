# Architecture Refactor Plan

This repo has strong deterministic compiler logic, but it has also accumulated the shape of a busy research codebase. The biggest issue is not one broken subsystem. It is that too many concerns live too close together:

- compiler lowering and layout logic in large backend modules
- GUI request handling and LLM drafting in one Flask app
- benchmarking, demos, papers, generated artifacts, and meeting material in the main repo tree
- repeated orchestration logic across entrypoints

## Current Structural Pressure Points

- `backend/graph_to_simulink.py` is over 1100 lines
- `pipeline/run_pipeline.py` is over 1100 lines
- `eqn2sim_gui/app.py` is over 1000 lines
- `backend/layout.py` is over 800 lines

These files are still understandable, but they are too large to be good long-term boundaries.

## Target Shape

The intended shape is:

1. compiler core
2. Simulink lowering and layout
3. MATLAB bridge
4. GUI and human-facing workflows
5. benchmarks, reports, and workspace artifacts

Each layer should have one clear responsibility and a small number of public entrypoints.

## Refactor Order

### Phase 1: Remove repeated orchestration

- Extract shared layout-mode orchestration out of graph and descriptor lowering.
- Keep layout application, visual repair, and metric attachment in one backend module.
- This is implemented in `backend/layout_workflow.py`.

### Phase 2: Split oversized lowerers

- Break `backend/graph_to_simulink.py` into:
  - graph block lowering
  - subsystem planning and wiring
  - output materialization
  - top-level lowering entrypoint
- Break `backend/descriptor_to_simulink.py` into:
  - descriptor validation
  - algebraic assignment and matching
  - block construction
  - top-level lowering entrypoint

### Phase 3: Split pipeline orchestration from reporting

- Move report generation, artifact writing, and benchmark-facing result formatting out of `pipeline/run_pipeline.py`.
- Keep one compile pipeline entrypoint plus separate reporting and export helpers.
- This is now started via `pipeline/reporting.py`, which owns summary serialization and CLI printing.

### Phase 4: Decompose the GUI

- Break `eqn2sim_gui/app.py` into:
  - route registration
  - request parsing and validation
  - run loading and saving
  - debug trace handling
  - draft generation and preview helpers

### Phase 5: Reduce repo visual noise

- Keep `workspace/` for generated artifacts only.
- Move meeting-specific and paper-specific material further away from day-to-day developer paths where possible.
- Keep the product path obvious for a new contributor:
  - install
  - lint
  - test
  - run pipeline
  - run GUI

## Guardrails

- Preserve deterministic behavior.
- Avoid changing MATLAB-facing semantics during structural refactors.
- Add or update tests for every extracted seam.
- Prefer moving logic into small modules over adding more mode flags to existing large files.
