# Contributing

## Branches

- Start each task from the latest `origin/main`; do not commit directly to `main`.
- Use one branch per task: `feature/<task>`, `fix/<task>`, `docs/<task>`, `refactor/<task>`, or `chore/<task>`. Include an issue number when available.
- Keep branches focused so each pull request can be reviewed and merged independently.

## Pull requests

- Open pull requests against `main`.
- Describe the goal, key changes, checks and results, and any known risks.
- Keep the PR open for team review. Merge only after required checks and review are complete.
- If `main` advances, update the task branch without rewriting shared or published history. Ask for help when a conflict could change another contributor's work.
- Remove a branch only after its PR is merged and the branch is no longer shared. Never delete an unmerged team branch to tidy the list.

## Finding active work

- Check GitHub's open pull requests and branch list for current work and review status.
- Do not keep a separate Markdown inventory of active branches; it can become stale. Use PR labels or GitHub Projects for task tracking.

## Protecting project files

- Do not commit `.env`, credentials, tokens, passwords, or unapproved raw or derived data.
- Before committing, review the staged file list and diff to confirm they contain only the intended task.

See [`GIT_WORKFLOW.md`](GIT_WORKFLOW.md) for the detailed Codex automation procedure.
