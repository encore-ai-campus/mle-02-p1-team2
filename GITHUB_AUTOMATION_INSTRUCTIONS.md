# Codex GitHub automation instructions

## Target

Repository: `encore-ai-campus/mle-02-p1-team2`
Default branch: `main`

These instructions are specific to this repository. Confirm the active Git root and `origin` before using them. The repository's root `AGENTS.md` is authoritative if instructions conflict.

## Default workflow for a development request

```text
Inspect Git root, origin, branch, and working tree
→ Fetch the latest origin/main
→ Create a short task branch from origin/main
→ Implement the requested change
→ Run relevant checks for code changes
→ Review the diff and screen for secrets/private data
→ Create a Conventional Commit
→ Push the task branch
→ Open a PR targeting main
→ Leave the PR open for team review
→ Report results and the PR link
```

The user has authorized the routine branch, commit, push, and PR steps above for this repository. Do not ask for each of those routine steps again. This standing authorization does not include merging, closing a PR, releasing, force pushing, or deleting user work.

## Branch names

Choose a concise name based on the task:

```text
feature/<task>   new functionality
fix/<task>       bug fix
docs/<task>      documentation
refactor/<task>  code structure
chore/<task>     configuration or maintenance
```

Use a fresh branch from the latest `origin/main` for each independent task. Do not reuse an unrelated or stale branch without checking its commits and working tree.

## Commits and pull requests

Use Conventional Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`. PRs should summarize the goal, important changes, checks run and results, and known risks. Keep PRs open for team review. Merge only after an explicit user instruction.

## Verification and stop conditions

- Run the smallest relevant project checks after code changes. Documentation-only changes do not require code tests.
- If checks fail, diagnose and repair only when the fix is clear and within scope. Otherwise report the failure; do not claim success.
- Never guess through risky conflicts or discard another person's work.
- Stop before any action that risks secret exposure, unauthorized data publication, data loss, or history rewriting.
- Never commit `.env`, API keys, secrets, tokens, passwords, or data that is not approved for publication.

## Final report

```text
Task:
Branch:
Commit:
Checks:
Push:
PR:
Merge: Not performed; explicit instruction required.
Risks/follow-up:
```
