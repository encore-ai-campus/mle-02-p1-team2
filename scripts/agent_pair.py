#!/usr/bin/env python3
"""Run a serial GPT-patch -> Codex-implementation -> GPT-review workflow."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

TEXT_SUFFIXES = {".cfg", ".gitignore", ".ini", ".json", ".md", ".py", ".rst", ".sql", ".toml", ".txt", ".yaml", ".yml"}
DENIED_PARTS = {".aws", ".codex", ".git", ".ssh", ".venv", "__pycache__", "data", "node_modules", "secrets", "credentials"}
MAX_FILE_CHARS = 20_000
MAX_CONTEXT_CHARS = 60_000
MAX_REVIEW_CHARS = 80_000


class WorkflowError(RuntimeError):
    pass


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=False,
    )
    if check and result.returncode:
        raise WorkflowError(result.stderr.strip() or f"git exited {result.returncode}")
    return result.stdout


def is_shareable_text(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    name = path.name.lower()
    if any(part in DENIED_PARTS for part in lowered):
        return False
    if name.startswith(".env") or any(marker in name for marker in ("secret", "credential", "token", "private_key")):
        return False
    if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        return False
    return path.name == ".gitignore" or path.suffix.lower() in TEXT_SUFFIXES


def read_text_file(root: Path, relative: str) -> str | None:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not is_shareable_text(path):
        return None
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        return None
    try:
        content = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if len(content) > MAX_FILE_CHARS or "\x00" in content:
        return None
    return content


def load_context(root: Path, requested: list[str]) -> tuple[str, int]:
    paths = requested or ["AGENTS.md", "README.md", "PROJECT_BRIEF.md", "pyproject.toml"]
    sections: list[str] = []
    omitted = 0
    total = 0
    for relative in paths:
        content = read_text_file(root, relative)
        if content is None:
            omitted += 1
            continue
        section = f"\n--- {relative} ---\n{content}"
        if total + len(section) > MAX_CONTEXT_CHARS:
            omitted += 1
            continue
        sections.append(section)
        total += len(section)
    return "".join(sections), omitted


def call_gpt(client, model: str, instructions: str, prompt: str, output_tokens: int) -> str:
    try:
        response = client.responses.create(
            model=model, instructions=instructions, input=prompt,
            max_output_tokens=output_tokens,
        )
    except Exception as exc:
        raise WorkflowError(f"GPT API request failed ({type(exc).__name__}).") from exc
    return (response.output_text or "").strip()


def strip_patch_fence(value: str) -> str:
    value = value.strip()
    fence = chr(96) * 3
    pattern = re.escape(fence) + r"(?:diff|patch)?\s*\n(.*?)\n" + re.escape(fence)
    match = re.fullmatch(pattern, value, flags=re.DOTALL)
    return match.group(1).strip() if match else value


def collect_review_diff(repo: Path, base_ref: str) -> tuple[str, int]:
    chunks: list[str] = []
    omitted = 0
    tracked = run_git(repo, "diff", "--name-only", "-z", base_ref).split("\x00")
    for relative in filter(None, tracked):
        if not is_shareable_text(Path(relative)):
            omitted += 1
            continue
        diff = run_git(repo, "diff", "--no-ext-diff", "--unified=3", base_ref, "--", relative)
        if "GIT binary patch" in diff or "Binary files " in diff:
            omitted += 1
            continue
        chunks.append(diff)

    untracked = run_git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\x00")
    for relative in filter(None, untracked):
        content = read_text_file(repo, relative)
        if content is None:
            omitted += 1
            continue
        lines = content.splitlines()
        body = "".join(f"+{line}\n" for line in lines)
        chunks.append(
            f"diff --git a/{relative} b/{relative}\nnew file mode 100644\n"
            f"--- /dev/null\n+++ b/{relative}\n@@ -0,0 +1,{len(lines)} @@\n{body}"
        )
    return "\n".join(chunks), omitted


def review_decision(review: str) -> str:
    first_line = review.splitlines()[0].strip().upper() if review else ""
    for decision in ("APPROVE", "REQUEST_CHANGES", "HOLD"):
        if first_line.startswith(decision):
            return decision
    return "HOLD"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPT authors a patch, Codex implements, GPT reviews.")
    parser.add_argument("--repo", required=True, help="Git repository to work on.")
    task = parser.add_mutually_exclusive_group(required=True)
    task.add_argument("--task", help="Task description.")
    task.add_argument("--task-file", help="UTF-8 file containing the task description.")
    parser.add_argument("--base-ref", default="origin/main", help="Starting Git ref.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL"))
    parser.add_argument("--context", action="append", default=[], help="Extra text file relative to repo; repeatable.")
    parser.add_argument("--worktree-root", help="Optional directory for generated worktrees.")
    parser.add_argument("--codex-command", default=os.environ.get("CODEX_CLI", "codex"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_arg = Path(args.repo).expanduser().resolve()
    repo = Path(run_git(repo_arg, "rev-parse", "--show-toplevel").strip()).resolve()
    base_sha = run_git(repo, "rev-parse", "--verify", f"{args.base_ref}^{{commit}}").strip()
    task_text = Path(args.task_file).expanduser().read_text(encoding="utf-8") if args.task_file else args.task
    if not task_text.strip():
        raise WorkflowError("The task description is empty.")
    if len(task_text) > 20_000:
        raise WorkflowError("Task descriptions are limited to 20,000 characters.")
    if not args.model:
        raise WorkflowError("Set OPENAI_MODEL or pass --model.")
    if not os.environ.get("OPENAI_API_KEY"):
        raise WorkflowError("Set OPENAI_API_KEY in the WSL environment; do not put it in the repo.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise WorkflowError("Install project dependencies, including openai, before running.") from exc

    if run_git(repo, "status", "--porcelain"):
        print(
            f"Note: source checkout has local changes. Worktree starts from {args.base_ref} "
            f"at {base_sha[:12]}; local changes are not included.", file=sys.stderr,
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
    branch = f"feature/agent-pair-{run_id}"
    cache_root = Path.home() / ".cache" / "codex-gpt-pair"
    worktree_parent = Path(args.worktree_root).expanduser().resolve() if args.worktree_root else cache_root / "worktrees" / repo.name
    worktree_parent.mkdir(parents=True, exist_ok=True)
    worktree = worktree_parent / run_id
    artifacts = cache_root / "runs" / run_id
    artifacts.mkdir(parents=True, exist_ok=True)
    run_git(repo, "worktree", "add", "-b", branch, str(worktree), base_sha)
    print(f"Branch: {branch}\nWorktree: {worktree}\nRun artifacts: {artifacts}")

    context, omitted_context = load_context(worktree, args.context)
    client = OpenAI()
    patch = strip_patch_fence(call_gpt(
        client, args.model,
        "You are the GPT editing stage in a guarded coding workflow. Return either a minimal unified diff "
        "that applies with git apply, or exactly NO_CHANGE. Use only the supplied task and context. "
        "Do not include explanations, secrets, or out-of-scope changes.",
        f"TASK\n{task_text}\n\nCONTEXT ({omitted_context} files omitted by safety filters)\n"
        f"{context or '(no context files supplied)'}", 8_000,
    ))
    patch_path = artifacts / "gpt.patch"
    patch_path.write_text(patch + "\n", encoding="utf-8")
    if patch and patch != "NO_CHANGE":
        run_git(worktree, "apply", "--check", "--whitespace=error", str(patch_path))
        run_git(worktree, "apply", "--whitespace=error", str(patch_path))

    codex_command = shlex.split(args.codex_command)
    if not codex_command:
        raise WorkflowError("CODEX_CLI resolved to an empty command.")
    implementation_prompt = (
        f"Implement this task in the current worktree:\n\n{task_text}\n\n"
        "A GPT-authored patch may already be present. Review it and continue from it. Keep changes focused. "
        "Do not commit, push, merge, deploy, or edit outside this worktree. Run checks only when the task asks."
    )
    codex_run = subprocess.run(
        [*codex_command, "exec", "--sandbox", "workspace-write", "--ask-for-approval", "never", "--json", implementation_prompt],
        cwd=worktree, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
    )
    (artifacts / "codex.stdout.log").write_text(codex_run.stdout, encoding="utf-8")
    (artifacts / "codex.stderr.log").write_text(codex_run.stderr, encoding="utf-8")
    if codex_run.returncode:
        raise WorkflowError(f"Codex exited {codex_run.returncode}; inspect {artifacts / 'codex.stderr.log'}.")
    current_head = run_git(worktree, "rev-parse", "HEAD").strip()
    if current_head != base_sha:
        raise WorkflowError("Codex created a commit despite the instruction. The commit was not changed; inspect the isolated branch.")

    diff, omitted_diff = collect_review_diff(worktree, base_sha)
    if not diff.strip():
        message = f"HOLD: no reviewable text diff; {omitted_diff} files were excluded."
        (artifacts / "gpt-review.md").write_text(message + "\n", encoding="utf-8")
        print(message)
        return 0
    review_instructions = (
        "You are the independent GPT review stage. Inspect correctness, scope, data safety, and obvious regressions. "
        "Do not edit files. Start with exactly one line: APPROVE, REQUEST_CHANGES, or HOLD. "
        "If the diff is incomplete or truncated, choose HOLD."
    )

    def request_review(current_diff: str, omitted: int) -> str:
        truncated = len(current_diff) > MAX_REVIEW_CHARS
        if truncated or omitted:
            return f"HOLD\nDiff incomplete: truncated={truncated}, excluded_files={omitted}."
        return call_gpt(
            client, args.model, review_instructions,
            f"TASK\n{task_text}\n\nDIFF (truncated={truncated}; {omitted} files omitted by safety filters)\n"
            f"{current_diff[:MAX_REVIEW_CHARS]}", 4_000,
        )

    review = request_review(diff, omitted_diff)
    (artifacts / "gpt-review.md").write_text(review + "\n", encoding="utf-8")
    if review_decision(review) == "REQUEST_CHANGES":
        fix_prompt = (
            f"Address the actionable findings below in the current worktree, within the original task scope. "
            f"Do not commit, push, merge, or deploy.\n\nORIGINAL TASK\n{task_text}\n\nGPT REVIEW\n{review}"
        )
        fix_run = subprocess.run(
            [*codex_command, "exec", "--sandbox", "workspace-write", "--ask-for-approval", "never", "--json", fix_prompt],
            cwd=worktree, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
        )
        (artifacts / "codex-fix.stdout.log").write_text(fix_run.stdout, encoding="utf-8")
        (artifacts / "codex-fix.stderr.log").write_text(fix_run.stderr, encoding="utf-8")
        if fix_run.returncode:
            raise WorkflowError(f"Codex correction exited {fix_run.returncode}; inspect {artifacts / 'codex-fix.stderr.log'}.")
        fix_head = run_git(worktree, "rev-parse", "HEAD").strip()
        if fix_head != base_sha:
            raise WorkflowError("Codex created a commit during correction; inspect the isolated branch.")
        diff, omitted_diff = collect_review_diff(worktree, base_sha)
        review = request_review(diff, omitted_diff)
        (artifacts / "gpt-review.md").write_text(review + "\n", encoding="utf-8")

    print(f"GPT review: {review_decision(review)}")
    print(f"Review: {artifacts / 'gpt-review.md'}")
    print(f"Changes remain uncommitted in: {worktree}")
    print("No commit, push, merge, or deployment was performed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WorkflowError as exc:
        print(f"agent_pair: {exc}", file=sys.stderr)
        raise SystemExit(2)
