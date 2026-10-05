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

## GitHub PR triage and GPT handoff

- If a GitHub integration can read PRs but a write returns `403 Resource not accessible by integration`, treat that as missing write access. Do not repeat the same mutation through that connection. Finish any useful read-only review, record which writes failed, and give the user a concise, copy-ready handoff for a GPT session with working GitHub write access.
- In the handoff, name the repository, list the exact PR actions in the user's approved order, preserve explicit holds, and distinguish completed checks from uncompleted changes. Do not imply a close, merge, edit, or push succeeded unless a fresh read confirms it.
- For PRs containing `.env` or credentials, do not print, test, or reuse the value. Tell the user which service must revoke/replace it directly, and do not merge while the exposed credential remains active. Removing `.env` from the current diff does not undo prior exposure.
- When a cleanup request includes notebooks and evaluation files, prefer preserving notebook source and the evaluation CSV while clearing notebook outputs and resetting execution counts, if those files are approved for publication. If approval or data provenance is unclear, inspect only what is needed to assess it and ask whether to retain or exclude the files before removing them. Never publish raw or unapproved data as part of cleanup.
- For the current PR cleanup handoff, preserve this user-approved order: #20 verification/description, #17 and #21 closure, #13 merge, #8 credential and notebook follow-up, #14/#16/#18 evaluation-material cleanup, then small documentation PRs. Keep #19 on hold. Report #8's exposed `.env` and the user's required credential rotation; for #14, recommend retaining notebook code and `golden_set_100.csv` while removing execution outputs, subject to data-publication review.

## Stop conditions

Stop before a risky conflict, unexpected remote, failed check that cannot be safely corrected within scope, possible secret/data exposure, or any action that could discard user work. Report what happened and the next safe step.
