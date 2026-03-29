# Repo Best Practice Ledger

This ledger records the repo-level choices adopted, deferred, or rejected during the March 27, 2026 architecture cleanup pass.

## `repo_structure`

- `topic_id`: `repo_structure`
- `topic_name`: Repo structure and package boundaries
- `current_state`: Flat multi-package repo with code, tooling, and many workspace artifact trees visible at the top level; contributor path is not obvious enough.
- `recommended_state`: Keep a single repo and current flat layout for now, but reduce top-level noise, keep generated assets under `workspace/`, and defer `src/` migration until package boundaries are cleaner.
- `source_type`: `packaging_guidance`
- `source_title`: PyPA, "src layout vs flat layout"
- `source_url`: <https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/>
- `section_or_page`: `src layout vs flat layout`
- `repo_fit`: Strong. The guidance explicitly distinguishes flat and `src` tradeoffs rather than prescribing one universal structure.
- `adopted`: `yes`
- `rejected_alternatives`: Force `src/` migration now; split the repo immediately into multiple repos.
- `migration_cost`: `medium` for cleanup, `high` for `src/`
- `risk`: Medium if `src/` is forced before package boundaries are cleaned up.
- `implementation_plan`: Keep flat layout, document boundaries, ignore generated artifact trees, and keep reducing oversized modules before reconsidering `src/`.
- `verification`: New docs, `.gitignore` updates, README/contributor workflow updates, and structural extraction work.

## `architectural_layering`

- `topic_id`: `architectural_layering`
- `topic_name`: Architectural layering
- `current_state`: Compiler, layout, MATLAB bridge, GUI, and reporting concerns are partially separated but still leak into large all-in-one modules.
- `recommended_state`: Preserve one repo but make layer boundaries explicit: compiler core, lowering/layout, MATLAB bridge, GUI, and benchmarks/reporting.
- `source_type`: `house_rule`
- `source_title`: Repo-specific architecture policy derived from the official packaging/testing/tooling guidance
- `source_url`: N/A
- `section_or_page`: N/A
- `repo_fit`: Strong. This repo's main problem is boundary blur, not missing tools.
- `adopted`: `yes`
- `rejected_alternatives`: Large rewrite; framework migration; multiple repos now.
- `migration_cost`: `medium`
- `risk`: Low if refactors stay seam-based and tested.
- `implementation_plan`: Continue small-module extractions from `backend/graph_to_simulink.py`, `backend/layout.py`, `pipeline/run_pipeline.py`, and `eqn2sim_gui/app.py`.
- `verification`: `backend/layout_workflow.py`, `pipeline/reporting.py`, and updated architecture docs.

## `task_orchestration`

- `topic_id`: `task_orchestration`
- `topic_name`: Task orchestration
- `current_state`: Canonical commands already exist through `pyproject` scripts and `scripts/` modules, but this was not documented strongly enough.
- `recommended_state`: Keep `scripts/` plus `[project.scripts]` as the one orchestration layer.
- `source_type`: `official_tool_docs`
- `source_title`: Nox tutorial, tox docs, just manual, and PyPA CLI packaging guidance
- `source_url`: <https://packaging.python.org/en/latest/guides/creating-command-line-tools/>
- `section_or_page`: `[project.scripts]` / console scripts
- `repo_fit`: Strong. The repo already has a coherent command surface; adding Nox, tox, or just now would duplicate it.
- `adopted`: `yes`
- `rejected_alternatives`: `nox`, `tox`, `just`
- `migration_cost`: `low`
- `risk`: Low. The main risk is command sprawl if more orchestration layers are added.
- `implementation_plan`: Keep documented defaults as `uv run python -m scripts.run_lint` and `uv run python -m scripts.run_tests`, with stable console-script aliases.
- `verification`: README and workflow docs updated; no additional orchestration layer added.

## `dependency_management`

- `topic_id`: `dependency_management`
- `topic_name`: Dependency and environment management
- `current_state`: `uv` and `uv.lock` are present, but ignore policy and contributor docs were not fully aligned with them.
- `recommended_state`: Treat `uv` as canonical, commit `uv.lock`, use `uv sync --extra dev`, and keep `.venv` and caches out of version control.
- `source_type`: `official_tool_docs`
- `source_title`: uv, "Structure and files" and "Locking and syncing"
- `source_url`: <https://docs.astral.sh/uv/concepts/projects/layout/>
- `section_or_page`: `The virtual environment`, `The lockfile`, `Locking and syncing`
- `repo_fit`: Strong. The repo already uses `uv`.
- `adopted`: `yes`
- `rejected_alternatives`: Return to ad hoc `pip`-only contributor workflow.
- `migration_cost`: `low`
- `risk`: Low. The main risk is contributors mutating environments outside the lockfile.
- `implementation_plan`: Tighten ignore policy, keep `uv.lock` committed, and keep docs pointing to `uv sync --extra dev`.
- `verification`: `.gitignore`, README, contributor docs, existing CI flow.

## `packaging_and_entrypoints`

- `topic_id`: `packaging_and_entrypoints`
- `topic_name`: Packaging and entry points
- `current_state`: `pyproject.toml` already defines metadata and console scripts, but the supported entrypoints are spread across docs and scripts.
- `recommended_state`: Keep `pyproject.toml` as the authoritative entrypoint manifest and use wrapper modules in `scripts/` only as implementation.
- `source_type`: `packaging_guidance`
- `source_title`: PyPA, "Creating and packaging command-line tools"
- `source_url`: <https://packaging.python.org/en/latest/guides/creating-command-line-tools/>
- `section_or_page`: `[project.scripts]`
- `repo_fit`: Strong.
- `adopted`: `yes`
- `rejected_alternatives`: Ad hoc shell scripts as the primary interface; moving to a CLI framework without a demonstrated need.
- `migration_cost`: `low`
- `risk`: Low.
- `implementation_plan`: Keep entry points stable and document them centrally.
- `verification`: `pyproject.toml`, README, and contributor workflow docs.

## `testing_strategy`

- `topic_id`: `testing_strategy`
- `topic_name`: Testing strategy
- `current_state`: Strong pytest coverage and markers already exist, but fast-vs-MATLAB guidance is under-documented and import mode still uses pytest defaults.
- `recommended_state`: Keep pytest and marker layering; document fast vs MATLAB-backed paths clearly; defer `importlib` mode until test assumptions are audited.
- `source_type`: `official_tool_docs`
- `source_title`: pytest, "Good Integration Practices"
- `source_url`: <https://docs.pytest.org/en/stable/explanation/goodpractices.html>
- `section_or_page`: `Good Integration Practices`, `Choosing an import mode`
- `repo_fit`: Strong.
- `adopted`: `partial`
- `rejected_alternatives`: Add tox right now; add property testing everywhere without a targeted need.
- `migration_cost`: `low` now, `medium` for future `importlib` rollout
- `risk`: Medium if import mode is changed before implicit working-tree imports are audited.
- `implementation_plan`: Keep pytest default runner, document test layers, revisit `--import-mode=importlib` after more structural cleanup.
- `verification`: `pytest.ini`, docs, and passing tests.

## `linting_formatting_typing`

- `topic_id`: `linting_formatting_typing`
- `topic_name`: Linting, formatting, and type checking
- `current_state`: Ruff is installed and active; no repo-wide type checker is enforced.
- `recommended_state`: Keep Ruff as the single lint/format toolchain; defer mypy or pyright until the largest dict-heavy boundaries are reduced and a rollout plan exists.
- `source_type`: `official_tool_docs`
- `source_title`: Ruff configuration and formatter docs
- `source_url`: <https://docs.astral.sh/ruff/formatter/>
- `section_or_page`: `The Ruff Formatter`, `Configuring Ruff`
- `repo_fit`: Strong for Ruff, weak for immediate repo-wide typing.
- `adopted`: `partial`
- `rejected_alternatives`: Add Black alongside Ruff; force repo-wide mypy immediately.
- `migration_cost`: `low` for Ruff, `high` for repo-wide typing right now
- `risk`: Medium if strict typing is forced before the data model is cleaned up.
- `implementation_plan`: Keep Ruff; postpone type-check rollout until package seams and stable payload shapes improve.
- `verification`: Existing lint command and config remain canonical.

## `ci_and_automation`

- `topic_id`: `ci_and_automation`
- `topic_name`: CI and repository automation
- `current_state`: GitHub Actions runs lint and tests, but repository automation around dependency updates and PR hygiene was missing.
- `recommended_state`: Keep the current fast CI jobs, add Dependabot for `uv`, GitHub Actions, and pre-commit, and document repository settings outside git.
- `source_type`: `official_platform_docs`
- `source_title`: GitHub Docs, supported ecosystems and protected branches
- `source_url`: <https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories>
- `section_or_page`: `uv`, `pre-commit`, `GitHub Actions`
- `repo_fit`: Strong.
- `adopted`: `yes`
- `rejected_alternatives`: Add more CI matrix jobs before there is a real compatibility requirement.
- `migration_cost`: `low`
- `risk`: Low.
- `implementation_plan`: Add Dependabot config, keep job names stable, and document branch protection expectations.
- `verification`: `.github/dependabot.yml`, governance doc, existing workflow names.

## `version_control_governance`

- `topic_id`: `version_control_governance`
- `topic_name`: Version control and governance
- `current_state`: Repo had CI but no checked-in CODEOWNERS or PR template, and governance lived mostly in convention.
- `recommended_state`: Use topic branches, protect the default branch with required checks, add CODEOWNERS and a PR template, and recommend signed commits for externally shared code.
- `source_type`: `git_docs`
- `source_title`: Git `gitworkflows`, GitHub protected branches, code owners, PR templates, and commit signature verification
- `source_url`: <https://git-scm.com/docs/gitworkflows>
- `section_or_page`: `Topic branches`
- `repo_fit`: Strong.
- `adopted`: `yes`
- `rejected_alternatives`: Direct-push-only workflow as the default.
- `migration_cost`: `low`
- `risk`: Low.
- `implementation_plan`: Add governance files in-repo and document GitHub UI settings that still need manual configuration.
- `verification`: `CODEOWNERS`, PR template, governance docs, and current CI job names.

## `maintenance_and_hygiene`

- `topic_id`: `maintenance_and_hygiene`
- `topic_name`: Maintenance and hygiene
- `current_state`: Generated benchmark outputs, `.venv`, and local caches were not fully reflected in `.gitignore`.
- `recommended_state`: Keep root clean, ignore environment/cache/generated output paths, and keep secrets and transient workspace outputs out of version control.
- `source_type`: `house_rule`
- `source_title`: Repo hygiene policy derived from uv, Ruff, and workspace usage
- `source_url`: N/A
- `section_or_page`: N/A
- `repo_fit`: Strong.
- `adopted`: `yes`
- `rejected_alternatives`: Leave every generated directory visible in git status.
- `migration_cost`: `low`
- `risk`: Low.
- `implementation_plan`: Expand `.gitignore` for local envs, caches, build outputs, and generated workspace benchmark trees.
- `verification`: `.gitignore` updates and cleaner `git status`.

## `documentation`

- `topic_id`: `documentation`
- `topic_name`: Documentation
- `current_state`: Core docs exist, but repo architecture/governance guidance was scattered or missing.
- `recommended_state`: Add explicit repo best-practices review, target architecture, workflow/governance doc, and contributor-facing defaults.
- `source_type`: `house_rule`
- `source_title`: Repo documentation policy derived from packaging and workflow guidance
- `source_url`: N/A
- `section_or_page`: N/A
- `repo_fit`: Strong.
- `adopted`: `yes`
- `rejected_alternatives`: Keep relying on oral tradition and README sprawl.
- `migration_cost`: `low`
- `risk`: Low.
- `implementation_plan`: Add dedicated docs and link them from README and contributor workflow.
- `verification`: New docs committed and referenced from README/CONTRIBUTING.
