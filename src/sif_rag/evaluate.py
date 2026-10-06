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
    allow_ai_provisional: bool = False,
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

    has_ai_provisional = any(question.get("status") == "ai_provisional" for question in questions)
    if has_ai_provisional and not allow_ai_provisional:
        raise ValueError("Refusing evaluation: AI provisional labels require --allow-ai-provisional and are not human_gold.")
    if allow_ai_provisional and not all(question.get("status") == "ai_provisional" for question in questions):
        raise ValueError("Provisional mode requires every question to be marked ai_provisional; mixed label sets are refused.")

    expected_by_id: dict[str, set[str]] = {}
    uncertain_by_id: dict[str, set[str]] = {}
    labeled: list[dict[str, Any]] = []
    judged_pair_count = 0
    uncertain_pair_count = 0
    excluded_no_positive_label_questions = 0
    if allow_ai_provisional:
        valid_labels = {"relevant", "not_relevant", "uncertain"}
        for question in questions:
            question_id = question["id"].strip()
            judgments = question.get("judgments")
            if not isinstance(judgments, list) or not judgments:
                raise ValueError(f"Question {question_id} has no AI provisional judgments.")
            labels_by_case: dict[str, str] = {}
            for judgment in judgments:
                if not isinstance(judgment, dict):
                    raise ValueError(f"Question {question_id} has an invalid judgment.")
                case_id = judgment.get("case_id")
                label = judgment.get("label")
                if not isinstance(case_id, str) or not case_id.strip() or label not in valid_labels:
                    raise ValueError(f"Question {question_id} has an invalid case ID or provisional label.")
                case_id = case_id.strip()
                if case_id in labels_by_case:
                    raise ValueError(f"Question {question_id} has duplicate judgment case IDs.")
                labels_by_case[case_id] = label
                for field in ("annotator", "model_version", "evidence_ref", "rationale", "confidence"):
                    value = judgment.get(field)
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f"Question {question_id} judgment is missing {field}.")
                annotator_tokens = set(re.split(r"[^a-z0-9]+", judgment["annotator"].casefold()))
                if not annotator_tokens & {"ai", "assistant", "model", "automated", "auto", "bot"}:
                    raise ValueError(f"Question {question_id} judgment is not identified as AI provisional.")
                if judgment["confidence"].casefold() not in {"low", "medium", "high"}:
                    raise ValueError(f"Question {question_id} judgment has invalid confidence.")
            judged_pair_count += len(labels_by_case)
            relevant = {case_id for case_id, label in labels_by_case.items() if label == "relevant"}
            uncertain = {case_id for case_id, label in labels_by_case.items() if label == "uncertain"}
            uncertain_pair_count += len(uncertain)
            supplied_expected = question.get("expected_case_ids")
            if supplied_expected is not None:
                if not isinstance(supplied_expected, list) or any(not isinstance(case_id, str) or not case_id.strip() for case_id in supplied_expected):
                    raise ValueError(f"Question {question_id} has invalid expected_case_ids.")
                if {case_id.strip() for case_id in supplied_expected} != relevant:
                    raise ValueError(f"Question {question_id} expected_case_ids do not match relevant AI judgments.")
            expected_by_id[question_id] = relevant
            uncertain_by_id[question_id] = uncertain
            if relevant or uncertain:
                labeled.append(question)
            else:
                excluded_no_positive_label_questions += 1
        if not labeled:
            raise ValueError("No questions have relevant or uncertain AI judgments.")
    else:
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
            question_id = question["id"].strip()
            expected_by_id[question_id] = set(normalized_expected)
            uncertain_by_id[question_id] = set()
            if question.get("status") == "human_gold":
                reviewer = question.get("reviewer")
                tokens = set(re.split(r"[^a-z0-9]+", reviewer.casefold())) if isinstance(reviewer, str) else set()
                automated = tokens & {"assistant", "ai", "model", "bot", "automated", "auto"}
                if not isinstance(reviewer, str) or not reviewer.strip() or automated:
                    raise ValueError(f"Question {question['id']} is marked human_gold without a valid human reviewer.")
        labeled = questions

    hits = 0
    optimistic_hits = 0
    reciprocal_ranks: list[float] = []
    optimistic_reciprocal_ranks: list[float] = []
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
        possible = expected | uncertain_by_id[question_id]
        ranked_ids = [document["case_id"] for _, document in results]
        rank = next((position for position, case_id in enumerate(ranked_ids, 1) if case_id in expected), None)
        optimistic_rank = next((position for position, case_id in enumerate(ranked_ids, 1) if case_id in possible), None)
        hits += rank is not None
        optimistic_hits += optimistic_rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        optimistic_reciprocal_ranks.append(1 / optimistic_rank if optimistic_rank else 0.0)
        detail = {"id": question_id, "rank": rank, "optimistic_rank": optimistic_rank, "retrieved": ranked_ids}
        if expansion:
            detail["matched_terms"] = expansion["matched_terms"]
            detail["added_terms"] = expansion["added_terms"]
        details.append(detail)

    return {
        "evaluation_status": "PROVISIONAL" if allow_ai_provisional else "REVIEWED_OR_LEGACY",
        "evaluation_policy": "ai_provisional_candidate_pool" if allow_ai_provisional else "human_gold_or_legacy",
        "labeled_questions": len(labeled),
        "excluded_no_positive_label_questions": excluded_no_positive_label_questions,
        "judged_candidate_pairs": judged_pair_count,
        "uncertain_candidate_pairs": uncertain_pair_count,
        f"hit_rate_at_{k}": hits / len(labeled),
        f"optimistic_hit_rate_at_{k}": optimistic_hits / len(labeled),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "optimistic_mrr": sum(optimistic_reciprocal_ranks) / len(optimistic_reciprocal_ranks),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate BM25 retrieval using reviewed labels or explicit AI provisional labels")
    parser.add_argument("--questions", type=Path, default=Path("data/evaluation/rag_questions.jsonl"))
    parser.add_argument("--corpus", type=Path, default=Path("data/raw/sif_openapi_cases.jsonl"))
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--compare-expansion", action="store_true", help="기본 검색과 용어 확장 검색을 같은 질문으로 비교")
    parser.add_argument("--allow-ai-provisional", action="store_true", help="AI provisional judgments만 이용한 탐색 지표를 출력; human_gold 또는 최종 PASS가 아님")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    args = parser.parse_args()
    questions, documents = load_questions(args.questions), load_corpus(args.corpus)
    try:
        if args.compare_expansion:
            expander = GlossaryExpander.from_csv(args.glossary)
            result = {
                "baseline": evaluate(questions, documents, args.k, allow_ai_provisional=args.allow_ai_provisional),
                "query_expansion": evaluate(questions, documents, args.k, expander, allow_ai_provisional=args.allow_ai_provisional),
            }
        else:
            result = evaluate(questions, documents, args.k, allow_ai_provisional=args.allow_ai_provisional)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

