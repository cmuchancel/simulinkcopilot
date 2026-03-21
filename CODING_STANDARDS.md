# Coding Standards

This document defines the repo conventions for implementation, review, and refactoring.

## Architectural Rules

1. Keep code in implementation modules, not in asset folders.
2. Keep executable entrypoints in `scripts/`, and run them as modules with `python3 -m scripts.<name>`.
3. Keep generated artifacts, demos, benchmark data, reports, papers, and examples under `workspace/`.
4. Keep deterministic compiler logic free of LLM dependencies and hidden runtime mutation.
5. Centralize filesystem defaults in [repo_paths.py](/Users/chancelavoie/Desktop/simulinkcopilot/repo_paths.py). Do not scatter hard-coded repo-relative paths across modules.

## Code Quality Rules

1. Prefer explicit data flow over implicit global state.
2. Keep functions small enough that their invariants are obvious from one read.
3. Use type hints on public functions and core transformation boundaries.
4. Use dataclasses or well-documented mappings for structured payloads instead of ad hoc nested dictionaries when the shape is stable.
5. Delete duplicate logic instead of maintaining parallel copies.
6. Do not mutate `sys.path` in production code or CLI entrypoints.
7. Do not add compatibility shims unless they clearly reduce migration risk and have an explicit removal path.
8. Prefer deterministic behavior over convenience in parser, canonicalization, and lowering stages.

## Filesystem and Artifact Rules

1. Root-level directories should be code, infrastructure, or repo metadata only.
2. New example `.tex` files belong in `workspace/examples/`.
3. New reports and benchmark outputs belong in `workspace/reports/`.
4. New generated `.slx` models belong in `workspace/generated_models/` or `workspace/bedillion_demo/` when demo-specific.
5. Temporary caches should not remain at repo root after a workflow finishes.

## Testing Rules

1. Every path-default change must be covered by at least one test.
2. Deterministic compiler changes should add or update unit coverage near the touched subsystem.
3. MATLAB-dependent tests should stay focused and opt for reuse over redundant end-to-end coverage.
4. Refactors are not complete until imports, docs, and CLI usage examples all match the new structure.
5. The default local test command is `python3 -m scripts.run_tests`; MATLAB-backed tests must be explicitly opted into.

## Documentation Rules

1. README examples must match the supported invocation style exactly.
2. If a folder exists for a clear purpose, document that purpose close to the folder or in the root README.
3. Keep terminology consistent:
   `workspace` for non-code assets, `scripts` for CLIs, and package directories for implementation.

## Review Checklist

Before considering a change complete, verify:

1. The code path is readable without guessing hidden assumptions.
2. There is no duplicated implementation that should have been consolidated.
3. There are no new hard-coded root-relative paths outside [repo_paths.py](/Users/chancelavoie/Desktop/simulinkcopilot/repo_paths.py).
4. The change does not leave generated clutter at repo root.
5. Tests and documentation still reflect the real entrypoints and file layout.
