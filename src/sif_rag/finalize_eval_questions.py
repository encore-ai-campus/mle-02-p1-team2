"""Build a human-gold question set from a complete manual candidate review."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .audit_eval_readiness import audit_candidate_reviews, load_questions


def finalize_question_labels(
    questions_path: Path, candidate_review_path: Path, output_path: Path
) -> int:
    if output_path.resolve() in {questions_path.resolve(), candidate_review_path.resolve()}:
        raise ValueError("Output path must be different from both input paths.")
    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")

    questions = load_questions(questions_path)
    question_by_id: dict[str, dict[str, Any]] = {}
    for index, question in enumerate(questions, start=1):
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Question {index} has no valid question ID.")
        key = question_id.strip()
        if key in question_by_id:
            raise ValueError("Question set contains duplicate question IDs.")
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError(f"Question {key} has no query text.")
        if question.get("status") == "human_gold" or question.get("expected_case_ids"):
            raise ValueError("Question set already contains gold labels; refusing to replace them.")
        question_by_id[key] = question
    if not question_by_id:
        raise ValueError("Question set is empty.")

    with candidate_review_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        candidate_report = audit_candidate_reviews(rows, reader.fieldnames, set(question_by_id))
    if not rows or candidate_report["not_ready"]:
        raise ValueError("Candidate review is incomplete or fails human provenance checks.")

    reviewed: dict[str, list[dict[str, str]]] = {question_id: [] for question_id in question_by_id}
    for row in rows:
        question_id = (row.get("question_id") or "").strip()
        reviewed[question_id].append(row)

    finalized: list[dict[str, Any]] = []
    for question_id, question in question_by_id.items():
        question_rows = reviewed[question_id]
        if not question_rows:
            raise ValueError("At least one reviewed candidate is required for every question.")
        reviewers = {(row.get("reviewer") or "").strip() for row in question_rows}
        if len(reviewers) != 1:
            raise ValueError("Each question must have one consistent human reviewer before finalization.")
        relevant = sorted({
            (row.get("case_id") or "").strip()
            for row in question_rows
            if (row.get("human_relevance_label") or "").strip().casefold() == "relevant"
        })
        if not relevant:
            raise ValueError("Each question needs at least one relevant candidate to create human_gold labels.")
        result = dict(question)
        result["expected_case_ids"] = relevant
        result["status"] = "human_gold"
        result["reviewer"] = next(iter(reviewers))
        finalized.append(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="") as target:
        for question in finalized:
            target.write(json.dumps(question, ensure_ascii=False) + "\n")
    return len(finalized)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a new human_gold JSONL from completed, human-reviewed candidate labels."
    )
    parser.add_argument("--questions", type=Path, required=True, help="Unlabeled question JSONL")
    parser.add_argument("--candidate-review", type=Path, required=True, help="Completed human-review CSV")
    parser.add_argument("--output", type=Path, required=True, help="New human_gold JSONL; existing files are not overwritten")
    args = parser.parse_args()
    try:
        count = finalize_question_labels(args.questions, args.candidate_review, args.output)
    except (OSError, csv.Error, ValueError) as exc:
        parser.error(str(exc))
    print(f"human_gold_questions={count} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
