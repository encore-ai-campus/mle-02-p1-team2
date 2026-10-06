# Codex instructions

## Scope

These instructions apply only to `encore-ai-campus/mle-02-p1-team2`. Read this file, `README.md`, and `PROJECT_BRIEF.md` before substantial project work. Never apply this repository's Git identity, branch, or permissions to another checkout.

## Development workflow

- Check the Git root, `origin`, current branch, and working tree before editing. Preserve existing user changes.
- For each user-requested development task, start from the latest `origin/main` on a short task branch. Never develop directly on `main`.
- Use `feature/`, `fix/`, `docs/`, `refactor/`, or `chore/` with a concise task name.
- Implement only the requested scope. Run the relevant project checks when code changes; report unavailable checks and their reason. Do not claim tests passed if they were not run.
- Use a concise Conventional Commit message: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`.
- Use the repo-local `$github-task-flow` skill for its detailed branch, verification, commit, push, and PR workflow.

## Standing GitHub authorization for this repository

For ordinary user-requested development tasks in this repository, the user authorizes Codex to create a task branch, commit the requested changes, push that branch to `origin`, and open a pull request without asking again. This authorization is limited to this repository and does not authorize merging or releasing.

- Open PRs against `main` and leave them open for review.
- Do not merge, close, or publish a release unless the user explicitly asks for that action.
- If tests fail, a risky conflict appears, the active remote is unexpected, or a change could expose secrets/data or lose user work, stop the risky step and report the issue.
- Never use force push, `git reset --hard`, history rewriting, or destructive cleanup.
- Never commit `.env`, credentials, API keys, tokens, passwords, or raw/derived data unless publication is explicitly approved.

## Completion report

Report the task, branch, commit, checks and results, push state, PR link/state, and remaining risks.

## Personal M0–M8 notebooks

- Keep personal learning notebooks under `notebooks/personal/` and name them by milestone, not date.
- End each notebook with a concise Markdown note covering what was verified, useful findings, caveats, and the next check.
- Keep raw and processed datasets, API credentials, and private evaluation artifacts out of Git. Do not publish SIF-derived outputs unless the applicable reuse scope is confirmed.
- Use root `uv add` for dependencies and commit both `pyproject.toml` and `uv.lock`. Run the affected notebook/app tests before opening a PR.

## Personal M0–M8 notebooks

- Keep personal learning notebooks under `notebooks/personal/` and name them by milestone, not date.
- End each notebook with concise Markdown notes on verified results, useful findings, caveats, and the next check.
- Keep raw and processed datasets, API credentials, local vector databases, and private evaluation artifacts out of Git. Clear saved notebook outputs before publishing when they could expose source data.
- Use root `uv add` for dependencies and commit both `pyproject.toml` and `uv.lock`. Run affected app and notebook tests before opening a PR.
