# Repo Target Architecture

This document describes the target repo shape after the current cleanup campaign. It is intentionally incremental: the goal is a cleaner, more legible application repo, not a rewrite.

## Architectural Goal

The repo should read as five clear layers:

1. compiler core
2. lowering and layout
3. MATLAB/Simulink bridge
4. human-facing workflows
5. benchmarks, reports, and generated artifacts

Those layers can live in one repo, but they should not blur together in the same giant modules.

## Current Pressure Points

- `backend/graph_to_simulink.py` remains over 1000 lines
- `backend/layout.py` remains over 800 lines
- `pipeline/run_pipeline.py` remains oversized, though reporting has now been extracted
- `eqn2sim_gui/app.py` remains a large Flask app-and-services file

## Top-Level Target Shape

### Product code

- `backend/`
  Deterministic Simulink lowering, layout, builders, validation, and MATLAB-backed execution helpers.
- `pipeline/`
  End-to-end compile/runtime orchestration, normalized problem entrypoints, reporting, GUI export, and bridge-facing helpers.
- `eqn2sim_gui/`
  Flask app, templates, route registration, request handling, and GUI services.
- `canonicalize/`, `ir/`, `latex_frontend/`, `states/`
  Core symbolic and IR layers.
- `simulate/`, `simulink/`
  Simulation, comparison, and MATLAB-facing integration helpers.

### Tooling and automation

- `scripts/`
  Supported CLI implementation modules only.
- `.github/`
  CI and governance automation.
- `pyproject.toml`, `pytest.ini`, `.pre-commit-config.yaml`
  Shared contributor tooling configuration.

### Docs

- `docs/`
  Architecture, workflow, interface, and policy docs only.

### Non-code assets

- `workspace/`
  Generated models, reports, benchmarks, examples, and other non-code project artifacts.

## Public Boundaries

The repo should expose a small number of stable public entrypoints:

- `eqn2sim-pipeline`
- `eqn2sim-gui`
- `eqn2sim-tests`
- `eqn2sim-lint`
- supported benchmark scripts as explicit console commands

Everything else should increasingly look like internal implementation detail behind those entrypoints.

## Target Module Boundaries

### `pipeline/`

Target shape:

- `run_pipeline.py`
  compile/runtime orchestration and CLI argument handling only
- `reporting.py`
  summary serialization and human-readable CLI printing
- `gui_export.py`
  GUI artifact export
- `matlab_bridge.py`
  JSON request/response bridge

Status:

- reporting extraction is now implemented in `pipeline/reporting.py`

### `backend/`

Target shape for graph lowering:

- graph planning
- block lowering
- subsystem planning
- output materialization
- top-level lowering API

Target shape for layout:

- layout primitives and geometry helpers
- deterministic rules
- metrics
- visual repair
- renderers
- orchestration

Status:

- `backend/layout_workflow.py`, `backend/layout_metrics.py`, `backend/layout_renderer.py`, and `backend/layout_visual_corrector.py` already exist

### `eqn2sim_gui/`

Target shape:

- app factory and config
- route registration
- run loading/saving
- request normalization
- drafting / preview helpers
- debug trace helpers

This should be the next major decomposition target once the pipeline/reporting split has settled.

## Repo-Structure Policies

### Keep one repo for now

Why:

- compiler, MATLAB bridge, GUI, and benchmarks still share code and contract surfaces
- the repo's current problem is internal structure, not cross-repo ownership

### Do not migrate to `src/` yet

Why:

- the repo is already heavily wired around editable installs, direct scripts, and multiple top-level packages
- the official guidance frames `src/` as a tradeoff, not a universal mandate
- boundary cleanup inside the current layout has a much better payoff-to-risk ratio right now

## Phase Map

### Phase 1: Remove repeated orchestration

Implemented:

- `backend/layout_workflow.py` centralizes layout mode application and optional visual repair

### Phase 2: Split pipeline reporting from orchestration

Implemented:

- `pipeline/reporting.py` now owns summary serialization and CLI printing

### Phase 3: Split oversized lowerers

Next target:

- `backend/graph_to_simulink.py`
- `backend/layout.py`

### Phase 4: Decompose the GUI

Next target after pipeline/backend seam work stabilizes:

- `eqn2sim_gui/app.py`

### Phase 5: Reduce visible repo noise

Ongoing:

- keep generated outputs in `workspace/`
- ignore transient local workspace output trees
- make the default contributor path obvious in docs

## Definition of "Cleaner"

This repo is cleaner when:

- contributors can infer the main code path quickly
- top-level directories have obvious roles
- generated assets stop polluting the default developer view
- large modules lose mixed responsibilities
- supported commands and governance are documented once and match reality
