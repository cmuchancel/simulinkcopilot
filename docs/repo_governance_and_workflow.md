# Repo Governance and Workflow

This document records the repo workflow and governance policy adopted during the March 27, 2026 cleanup pass.

## Default Contributor Path

From repo root:

```bash
uv sync --extra dev
uv run python -m scripts.run_lint
uv run python -m scripts.run_tests
```

Preferred console-script equivalents:

```bash
eqn2sim-lint
eqn2sim-tests
eqn2sim-pipeline --help
eqn2sim-gui
```

Why this is the default:

- uv documents `uv.lock` as the reproducible project lockfile and recommends keeping it in version control
- `uv sync` and `uv run` keep the project environment aligned with the lockfile
- this repo already uses those commands in CI

Sources:

- <https://docs.astral.sh/uv/concepts/projects/layout/>
- <https://docs.astral.sh/uv/concepts/projects/sync/>

## Branch and PR Policy

Recommended GitHub settings for the default branch:

- block force pushes
- block branch deletion
- require pull requests before merging
- require the `lint` and `unit` status checks
- require branches to be up to date before merge when team size grows
- apply rules to admins if the repo becomes shared beyond a single maintainer

Recommended merge policy:

- use topic branches for each feature/fix/refactor
- prefer squash merges to keep a readable mainline while the repo is still moving quickly
- defer merge queue until the branch becomes genuinely busy

Why:

- GitHub branch protection explicitly supports required status checks and linear-history controls
- Git's own workflow guide recommends topic branches
- GitHub notes merge queue is most useful on busy branches with many PRs per day

Sources:

- <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches>
- <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue>
- <https://git-scm.com/docs/gitworkflows>

## Ownership and Review

- `CODEOWNERS` is checked in to make default ownership explicit.
- PRs should include:
  - what changed
  - how it was validated
  - whether MATLAB-backed behavior was touched
  - any follow-up debt left intentionally

Sources:

- <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners>
- <https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository>

## Dependency and Automation Policy

- `uv` is the canonical dependency manager.
- `uv.lock` stays committed.
- Dependabot is enabled for:
  - `uv`
  - `github-actions`
  - `pre-commit`
- contributors should not mutate the managed environment manually with ad hoc installs when the change belongs in `pyproject.toml`

Why:

- uv's docs state that `uv.lock` should be checked into version control for consistent installs
- GitHub officially supports Dependabot updates for `uv`, `github-actions`, and `pre-commit`

Sources:

- <https://docs.astral.sh/uv/concepts/projects/layout/>
- <https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories>

## Test and Hook Policy

- local hooks are managed through `.pre-commit-config.yaml`
- hooks should call the same canonical lint/test commands used in CI
- fast tests are the default local and CI path
- MATLAB-backed tests remain opt-in and explicitly marked

Why:

- pre-commit documents `.pre-commit-config.yaml` as the project hook manifest and suggests running hooks in CI too
- pytest's guidance favors installed/editable test flows over ad hoc setuptools-based test commands

Sources:

- <https://pre-commit.com/>
- <https://docs.pytest.org/en/stable/explanation/goodpractices.html>

## Artifact and Workspace Policy

- implementation code does not belong under `workspace/`
- `workspace/` is for examples, reports, generated models, benchmark outputs, and other non-code assets
- transient benchmark and local debug output should be ignored by git unless deliberately promoted into a tracked artifact set
- `.venv`, `.ruff_cache`, build outputs, and coverage artifacts stay untracked

This is a house rule informed by the repo's actual shape and the need to keep the developer path readable.

## Secret Handling Policy

- `.env` remains local-only
- no secrets in committed JSON artifacts, reports, or screenshots
- when a feature needs runtime secrets, the docs should say so explicitly and point contributors to `.env` rather than hardcoded config

## Commit Signing Policy

- signed commits are recommended for externally shared or security-sensitive work
- SSH signing is the simplest default for an individual maintainer according to GitHub's current guidance
- do not block local iteration on signing unless repository settings are intentionally tightened

Source:

- <https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification>

## Release and Change Policy

This repo is currently application-first, not a polished public package release stream. Until that changes:

- do not cut a release tag unless lint/tests are green
- update `uv.lock` whenever dependency manifests change
- keep docs in sync with actual commands and entrypoints
- structural refactors are not done until tests and docs match the new seams

## Immediate Governance Files Added In This Pass

- `CODEOWNERS`
- `.github/pull_request_template.md`
- `.github/dependabot.yml`
- `CONTRIBUTING.md`

Some governance controls still require GitHub UI changes and cannot be enforced solely from git-tracked files:

- branch protection rules
- required status checks
- merge method settings
- optional signed-commit enforcement
