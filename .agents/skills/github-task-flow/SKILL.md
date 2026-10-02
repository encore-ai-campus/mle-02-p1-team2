---
name: github-task-flow
description: Use for development or documentation changes in encore-ai-campus/mle-02-p1-team2 that should follow the repository's branch, commit, push, and pull-request workflow. Do not use for another repository or Git advice without file changes.
---

# GitHub task workflow

Follow the repository root `AGENTS.md` and `GITHUB_AUTOMATION_INSTRUCTIONS.md`. This skill provides the repeatable steps for a requested change; it does not expand the user's requested scope.

## Workflow

1. Confirm the current Git root, `origin`, branch, and working tree. Stop if `origin` is not `encore-ai-campus/mle-02-p1-team2`.
2. Preserve existing changes. If the working tree is not clean, isolate the task in a worktree when possible; otherwise ask before mixing changes.
3. Fetch `origin/main` and create a short task branch from its latest commit. Never develop directly on `main`.
4. Read the relevant project instructions and files, then make only the requested changes.
5. Run the smallest relevant checks for code changes. For documentation-only changes, inspect the diff and check formatting instead of running code tests.
6. Review the final diff for unrelated changes, credentials, secrets, and data that is not approved for publication.
7. Use a concise Conventional Commit message, push the task branch, and open a PR targeting `main`. The repository's `AGENTS.md` provides standing authorization for these routine steps.
8. Leave the PR open for review. Merge, close, release, force-push, rewrite history, or delete user work only when the user explicitly asks.
9. Report the branch, commit, checks and results, push status, PR link, and any remaining risks.

## Stop conditions

Stop before a risky conflict, unexpected remote, failed check that cannot be safely corrected within scope, possible secret/data exposure, or any action that could discard user work. Report what happened and the next safe step.
