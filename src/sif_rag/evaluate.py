"""Evaluate retrieval against manually reviewed relevant SIF case IDs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .search import bm25, load_corpus
from .query_expansion import DEFAULT_GLOSSARY, GlossaryExpander


def load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def evaluate(
    questions: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    k: int = 5,
    expander: GlossaryExpander | None = None,
) -> dict[str, Any]:
    if not questions:
        raise ValueError("No evaluation questions were provided.")
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer.")

    seen_ids: set[str] = set()
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError(f"Question {index} must be an object.")
        raw_question_id = question.get("id")
        question_id = raw_question_id.strip() if isinstance(raw_question_id, str) else ""
        if not question_id:
            raise ValueError(f"Question {index} has no question ID.")
        if question_id in seen_ids:
            raise ValueError("Duplicate question IDs are not allowed.")
        seen_ids.add(question_id)
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError(f"Question {question_id} has no query text.")

    unlabeled_count = sum(not question.get("expected_case_ids") for question in questions)
    if unlabeled_count:
        raise ValueError(
            f"Refusing partial evaluation: {unlabeled_count} of {len(questions)} questions have no expected_case_ids."
        )
    non_gold_count = sum(
        "status" in question and question.get("status") != "human_gold"
        for question in questions
    )
    if non_gold_count:
        raise ValueError(
            f"Refusing evaluation: {non_gold_count} questions are not marked human_gold."
        )
    expected_by_id: dict[str, set[str]] = {}
    for question in questions:
        expected = question["expected_case_ids"]
        invalid_expected = not isinstance(expected, list) or any(
            not isinstance(case_id, str) or not case_id.strip() for case_id in expected
        )
        if invalid_expected:
            raise ValueError(f"Question {question['id']} has invalid expected_case_ids.")
        normalized_expected = [case_id.strip() for case_id in expected]
        if len(set(normalized_expected)) != len(normalized_expected):
            raise ValueError(f"Question {question['id']} has duplicate expected_case_ids.")
        expected_by_id[question["id"].strip()] = set(normalized_expected)
        if question.get("status") == "human_gold":
            reviewer = question.get("reviewer")
            tokens = set(re.split(r"[^a-z0-9]+", reviewer.casefold())) if isinstance(reviewer, str) else set()
            automated = tokens & {"assistant", "ai", "model", "bot", "automated", "auto"}
            if not isinstance(reviewer, str) or not reviewer.strip() or automated:
                raise ValueError(f"Question {question['id']} is marked human_gold without a valid human reviewer.")
    labeled = questions

    hits = 0
    reciprocal_ranks: list[float] = []
    details = []
    for question in labeled:
        query = question["question"]
        expansion = expander.expand(query) if expander else None
        if expansion:
            query = str(expansion["expanded_query"])
        results = bm25(
            query,
            documents,
            k=k,
            industry=question.get("industry_filter"),
        )
        question_id = question["id"].strip()
        expected = expected_by_id[question_id]
        ranked_ids = [document["case_id"] for _, document in results]
        rank = next((position for position, case_id in enumerate(ranked_ids, 1) if case_id in expected), None)
        hits += rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        detail = {"id": question_id, "rank": rank, "retrieved": ranked_ids}
        if expansion:
            detail["matched_terms"] = expansion["matched_terms"]
            detail["added_terms"] = expansion["added_terms"]
        details.append(detail)

    return {
        "labeled_questions": len(labeled),
        f"hit_rate_at_{k}": hits / len(labeled),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate BM25 retrieval against reviewed relevant case IDs")
    parser.add_argument("--questions", type=Path, default=Path("data/evaluation/rag_questions.jsonl"))
    parser.add_argument("--corpus", type=Path, default=Path("data/raw/sif_openapi_cases.jsonl"))
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--compare-expansion", action="store_true", help="기본 검색과 용어 확장 검색을 같은 질문으로 비교")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    args = parser.parse_args()
    questions, documents = load_questions(args.questions), load_corpus(args.corpus)
    try:
        if args.compare_expansion:
            expander = GlossaryExpander.from_csv(args.glossary)
            result = {
                "baseline": evaluate(questions, documents, args.k),
                "query_expansion": evaluate(questions, documents, args.k, expander),
            }
        else:
            result = evaluate(questions, documents, args.k)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

