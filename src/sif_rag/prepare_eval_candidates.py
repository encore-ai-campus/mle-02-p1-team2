"""Create a human-review pool for relevance labels from the BM25 baseline."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from .evaluate import load_questions
from .search import DEFAULT_CORPUS, bm25, load_corpus


FIELDS = (
    ("industry_category", "cateSeNm"),
    ("industry_major", "sifLclsfNm"),
    ("industry_mid", "sifMclsfNm"),
    ("industry_small", "sifSclsfNm"),
    ("disaster_type", "disasterType"),
    ("incident_overview", "disasterOverview"),
    ("object_text", "orgtNm"),
    ("high_risk_work", "situation"),
    ("precursor", "disasterFactor"),
    ("control_measure", "dcrsCntrplnCn"),
)


def build_review_rows(
    questions: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    k: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for question in questions:
        results = bm25(
            question["question"],
            documents,
            k=k,
            industry=question.get("industry_filter"),
        )
        for rank, (score, document) in enumerate(results, start=1):
            fields = document.get("fields", {})
            row = {
                "question_id": question["id"],
                "question": question["question"],
                "industry_filter": question.get("industry_filter") or "",
                "candidate_rank": rank,
                "bm25_score": round(score, 6),
                "case_id": document["case_id"],
                "retrieved_query": document.get("retrieved_query", ""),
                "source_url": document.get("source_url", ""),
                "relevance_label": "",
                "reviewer": "",
                "review_status": "candidate",
                "evidence_reference": document.get("source_url", ""),
                "review_notes": "",
            }
            row.update({output: fields.get(source, "") for output, source in FIELDS})
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export BM25 candidates for manual relevance review; does not assign labels."
    )
    parser.add_argument("--questions", type=Path, default=Path("data/evaluation/questions/rag_questions.jsonl"))
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/labels/rag_candidate_review.csv"))
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()
    if args.k < 1:
        parser.error("-k must be at least 1")

    questions = load_questions(args.questions)
    documents = load_corpus(args.corpus)
    rows = build_review_rows(questions, documents, args.k)
    columns = [
        "question_id", "question", "industry_filter", "candidate_rank", "bm25_score",
        "case_id", "retrieved_query", "industry_category", "industry_major", "industry_mid",
        "industry_small", "disaster_type", "incident_overview", "object_text", "high_risk_work",
        "precursor", "control_measure", "source_url", "relevance_label", "reviewer",
        "review_status", "evidence_reference", "review_notes",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"questions={len(questions)} candidates={len(rows)} output={args.output}")
    print("relevance_label is intentionally blank; review each candidate before evaluation.")


if __name__ == "__main__":
    main()
