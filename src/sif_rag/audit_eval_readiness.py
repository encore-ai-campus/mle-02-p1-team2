"""Audit retrieval-label readiness without printing question or case content."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "1"
GOLD_STATUS = "human_gold"
VALID_LABELS = {"relevant", "not_relevant", "uncertain"}
REVIEW_COLUMNS = {"question_id", "case_id", "human_relevance_label", "human_rationale", "reviewer", "source_url"}


def load_questions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object on line {line_number}")
            rows.append(value)
    return rows


def _is_assistant_reviewer(value: str) -> bool:
    tokens = set(re.split(r"[^a-z0-9]+", value.casefold()))
    return any(token in {"assistant", "ai", "model", "bot", "automated", "auto"} for token in tokens)


def _valid_reviewer(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not _is_assistant_reviewer(value)


def _valid_source_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").casefold()
    return parsed.scheme in {"http", "https"} and (host == "data.go.kr" or host.endswith(".data.go.kr"))


def _file_identity(path: Path) -> dict[str, str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"file_name": path.name, "sha256": digest}


def audit_questions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    ready = 0
    for row in rows:
        question_id = str(row.get("id") or "").strip()
        status = str(row.get("status") or "").strip()
        statuses[status or "missing"] += 1
        duplicate_id = bool(question_id and question_id in seen_ids)
        if not question_id:
            issues["missing_question_id"] += 1
        elif duplicate_id:
            duplicate_ids.add(question_id)
        seen_ids.add(question_id)
        row_ready = bool(question_id) and not duplicate_id
        if not str(row.get("question") or "").strip():
            issues["missing_question_text"] += 1
            row_ready = False
        if status != GOLD_STATUS:
            issues["not_human_gold_status"] += 1
            row_ready = False
        expected = row.get("expected_case_ids")
        if not isinstance(expected, list) or not expected:
            issues["missing_expected_case_ids"] += 1
            row_ready = False
        elif any(not isinstance(case_id, str) or not case_id.strip() for case_id in expected):
            issues["invalid_expected_case_id"] += 1
            row_ready = False
        elif len({str(case_id).strip() for case_id in expected}) != len(expected):
            issues["duplicate_expected_case_id"] += 1
            row_ready = False
        if not _valid_reviewer(row.get("reviewer")):
            issues["missing_or_nonhuman_reviewer"] += 1
            row_ready = False
        ready += int(row_ready)
    issues["duplicate_question_id"] += len(duplicate_ids)
    return {
        "total": len(rows), "gold_ready": ready, "not_ready": len(rows) - ready,
        "status_counts": dict(sorted(statuses.items())), "issue_counts": dict(sorted(issues.items())),
    }


def audit_candidate_reviews(
    rows: list[dict[str, str]], fieldnames: list[str] | None, question_ids: set[str]
) -> dict[str, Any]:
    missing_columns = sorted(REVIEW_COLUMNS - set(fieldnames or []))
    labels: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    duplicate_pairs: set[tuple[str, str]] = set()
    seen_pairs: set[tuple[str, str]] = set()
    assistant_rows = 0
    ready = 0
    for row in rows:
        question_id = (row.get("question_id") or "").strip()
        case_id = (row.get("case_id") or "").strip()
        label = (row.get("human_relevance_label") or "").strip().casefold()
        reviewer = (row.get("reviewer") or "").strip()
        pair = (question_id, case_id)
        row_ready = not missing_columns
        if not question_id or not case_id:
            issues["missing_pair_id"] += 1
            row_ready = False
        elif pair in seen_pairs:
            duplicate_pairs.add(pair)
            row_ready = False
        seen_pairs.add(pair)
        if question_id and question_id not in question_ids:
            issues["question_id_not_in_question_set"] += 1
            row_ready = False
        if label not in VALID_LABELS:
            issues["missing_or_invalid_human_label"] += 1
            row_ready = False
        else:
            labels[label] += 1
        if not reviewer:
            issues["missing_reviewer"] += 1
            row_ready = False
        elif _is_assistant_reviewer(reviewer):
            assistant_rows += 1
            issues["assistant_or_automated_label"] += 1
            row_ready = False
        if not (row.get("human_rationale") or "").strip():
            issues["missing_rationale"] += 1
            row_ready = False
        source_url = (row.get("source_url") or "").strip()
        if not _valid_source_url(source_url):
            issues["missing_or_nonofficial_source_url"] += 1
            row_ready = False
        ready += int(row_ready)
    issues["duplicate_question_case_pair"] += len(duplicate_pairs)
    if missing_columns:
        issues["missing_required_columns"] += len(missing_columns)
    return {
        "total": len(rows), "review_ready": ready, "not_ready": len(rows) - ready,
        "label_counts": dict(sorted(labels.items())), "uncertain_count": labels["uncertain"],
        "assistant_or_automated_rows": assistant_rows, "missing_columns": missing_columns,
        "issue_counts": dict(sorted(issues.items())),
    }


def audit_files(questions_path: Path, candidate_review_path: Path | None = None) -> dict[str, Any]:
    questions = load_questions(questions_path)
    question_report = audit_questions(questions)
    reasons: list[str] = []
    if not questions:
        reasons.append("empty_question_set")
    if question_report["not_ready"]:
        reasons.append("question_set_not_human_gold_ready")
    candidate_report = None
    if candidate_review_path is not None:
        with candidate_review_path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            candidate_rows = list(reader)
            candidate_report = audit_candidate_reviews(
                candidate_rows, reader.fieldnames,
                {str(row.get("id") or "").strip() for row in questions},
            )
        if not candidate_rows:
            reasons.append("empty_candidate_review")
        if candidate_report["not_ready"]:
            reasons.append("candidate_review_not_human_ready")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not reasons else "HOLD",
        "evaluation_policy": "human_gold_only",
        "question_set": question_report,
        "candidate_review": candidate_report,
        "source_files": {
            "questions": _file_identity(questions_path),
            "candidate_review": _file_identity(candidate_review_path) if candidate_review_path else None,
        },
        "reasons": reasons,
        "privacy_note": "Report contains aggregate counts only; question and case content is omitted.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether retrieval evaluation inputs are human-review ready.")
    parser.add_argument("--questions", type=Path, required=True, help="Question JSONL")
    parser.add_argument("--candidate-review", type=Path, help="Optional candidate-review CSV")
    args = parser.parse_args()
    try:
        report = audit_files(args.questions, args.candidate_review)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
