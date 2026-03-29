# Contributing

## Default Workflow

From the repo root:

```bash
uv sync --extra dev
uv run python -m scripts.run_lint
uv run python -m scripts.run_tests
```

If you prefer the console-script aliases:

```bash
eqn2sim-lint
eqn2sim-tests
```

## Repo Expectations

- keep implementation code in package directories, not under `workspace/`
- keep generated artifacts in `workspace/`
- prefer seam-based refactors over giant rewrites
- preserve deterministic behavior in the compiler and Simulink-lowering path
- if you touch MATLAB-backed flows, say so explicitly in your validation notes

## Before Opening a PR

1. run lint
2. run the fast test suite
3. update docs if commands, structure, or entrypoints changed
4. keep generated benchmark/debug output out of the diff unless it is an intentional tracked artifact

See:

- [docs/repo_best_practices_review.md](docs/repo_best_practices_review.md)
- [docs/repo_target_architecture.md](docs/repo_target_architecture.md)
- [docs/repo_governance_and_workflow.md](docs/repo_governance_and_workflow.md)
- [CODING_STANDARDS.md](CODING_STANDARDS.md)
