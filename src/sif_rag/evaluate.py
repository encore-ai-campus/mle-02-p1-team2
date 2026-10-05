"""Evaluate retrieval against manually reviewed relevant SIF case IDs."""

from __future__ import annotations

import argparse
import json
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
        expected = set(question["expected_case_ids"])
        ranked_ids = [document["case_id"] for _, document in results]
        rank = next((position for position, case_id in enumerate(ranked_ids, 1) if case_id in expected), None)
        hits += rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        detail = {"id": question["id"], "rank": rank, "retrieved": ranked_ids}
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

