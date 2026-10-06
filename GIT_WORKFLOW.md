# Git automation workflow

## Scope

- Repository: `encore-ai-campus/mle-02-p1-team2`
- Remote: `origin`
- Base branch: `main`
- `AGENTS.md` is authoritative if instructions conflict. Use `CONTRIBUTING.md` for the team-facing summary.

## Before changing files

1. Confirm the Git root and `origin` identify this repository.
2. Inspect the current branch, working tree, and linked worktrees.
3. Preserve all existing edits and untracked files. Do not stage everything with `git add -A` when unrelated files are present.
4. Fetch `origin/main` and create a fresh task branch from it. Never work directly on `main` or reuse an unrelated branch without checking its state.
5. If the checkout has unrelated changes, isolate the task in a worktree when possible. Do not mix, overwrite, or discard another task's files.

## Branch and pull request

- Use a short task branch: `feature/<task>`, `fix/<task>`, `docs/<task>`, `refactor/<task>`, or `chore/<task>`. Add an issue number when one exists.
- Make one focused change per branch and use a Conventional Commit prefix: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`.
- Run the smallest relevant checks for code changes. For documentation-only changes, inspect the diff and check formatting instead of running code tests.
- Review the exact staged diff before committing. Check for unrelated files, credentials, `.env` files, secrets, and data that is not approved for publication.
- The repository's `AGENTS.md` grants standing authorization to commit, push the task branch, and open a PR against `main` for ordinary requested development work. Keep the PR open for review.
- Never merge or close a PR, publish a release, force-push, rewrite history, or delete user work unless the user explicitly instructs it.
- If a conflict could affect another person's work, stop and report it rather than guessing.

## Branch status

- Treat GitHub branches and pull requests as the source of truth for current work and review status.
- Do not copy active branch lists into repository Markdown files. Use PR labels or GitHub Projects if the team needs a separate task board.
- Do not delete unmerged or shared branches as part of routine automation.

## Completion report

```text
Task:
Branch:
Commit:
Checks:
Push:
PR:
Merge: Not performed
Risks/follow-up:
```
