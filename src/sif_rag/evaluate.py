"""Evaluate retrieval against manually reviewed relevant SIF case IDs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .search import DEFAULT_CORPUS, bm25, load_corpus
from .query_expansion import DEFAULT_GLOSSARY, GlossaryExpander


def load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def evaluate_candidate_pool(rows: list[dict[str, str]], depth: int) -> dict[str, Any]:
    """Compare query variants on one completely human-reviewed pooled set."""
    if depth < 1:
        raise ValueError("Evaluation depth must be at least 1.")
    systems = {"raw": "raw_rank", "focused": "focused_rank", "glossary": "glossary_rank"}
    allowed = {"relevant", "not_relevant", "uncertain"}
    grouped: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str]] = set()
    required_columns = {"question_id", "case_id", "pool_depth", "relevance_label", "review_status", "reviewer", "evidence_reference", "review_notes", *systems.values()}
    for row in rows:
        missing_columns = required_columns - set(row)
        if missing_columns:
            raise ValueError(f"Review pool is missing columns: {sorted(missing_columns)}")
        question_id, case_id = row.get("question_id", "").strip(), row.get("case_id", "").strip()
        if not question_id or not case_id:
            raise ValueError("Every judgment row must include question_id and case_id.")
        key = (question_id, case_id)
        if key in seen:
            raise ValueError(f"Duplicate judgment row: question_id={question_id}, case_id={case_id}")
        seen.add(key)
        label = row.get("relevance_label", "").strip().casefold()
        if label not in allowed:
            raise ValueError(f"Missing or invalid relevance label: {key} ({label or 'blank'})")
        if row.get("review_status", "").strip().casefold() != "human_reviewed":
            raise ValueError(f"Judgment is not marked human_reviewed: {key}")
        if not row.get("reviewer", "").strip() or not row.get("review_notes", "").strip() or not row.get("evidence_reference", "").strip():
            raise ValueError(f"Reviewer, evidence reference, and rationale are required: {key}")
        row["relevance_label"] = label
        grouped.setdefault(question_id, []).append(row)
    if not grouped:
        raise ValueError("The review pool has no judgments.")
    declared_depths = {int(row["pool_depth"]) for row in rows if row.get("pool_depth", "").strip()}
    if len(declared_depths) != 1:
        raise ValueError("All rows must declare the same pool_depth.")
    pool_depth = declared_depths.pop()
    if depth > pool_depth:
        raise ValueError(f"Requested depth {depth} exceeds judged candidate depth {pool_depth}.")

    def metrics(
        group: list[dict[str, str]], rank_column: str, include_uncertain: bool
    ) -> tuple[float, float, float]:
        ranked: list[tuple[int, dict[str, str]]] = []
        ranks: set[int] = set()
        for row in group:
            value = row.get(rank_column, "").strip()
            if not value:
                continue
            try:
                rank = int(value)
            except ValueError as exc:
                raise ValueError(f"Invalid rank: {rank_column}={value}") from exc
            if rank < 1:
                raise ValueError(f"Ranks must be at least 1: {rank_column}={rank}")
            if rank in ranks:
                raise ValueError(f"Duplicate rank in {rank_column}: {rank}")
            ranks.add(rank)
            if rank <= depth:
                ranked.append((rank, row))
        if ranks and ranks != set(range(1, max(ranks) + 1)):
            raise ValueError(f"Ranks in {rank_column} must be contiguous from 1.")
        relevant_labels = {"relevant", "uncertain"} if include_uncertain else {"relevant"}
        relevant_total = sum(row["relevance_label"] in relevant_labels for row in group)
        hit_rank = next((rank for rank, row in sorted(ranked) if row["relevance_label"] in relevant_labels), None)
        hits = sum(row["relevance_label"] in relevant_labels for _, row in ranked)
        return (
            float(hit_rank is not None),
            1 / hit_rank if hit_rank else 0.0,
            hits / relevant_total if relevant_total else 0.0,
        )

    output: dict[str, Any] = {"depth": depth, "judged_questions": len(grouped), "systems": {}}
    for system, rank_column in systems.items():
        variants: dict[str, dict[str, float]] = {}
        for name, include_uncertain in (("primary_uncertain_excluded", False), ("sensitivity_uncertain_included", True)):
            values = [metrics(group, rank_column, include_uncertain) for group in grouped.values()]
            variants[name] = {
                "hit_rate": sum(value[0] for value in values) / len(values),
                "mrr": sum(value[1] for value in values) / len(values),
                "pooled_recall": sum(value[2] for value in values) / len(values),
            }
        per_question: dict[str, Any] = {}
        for question_id, group in grouped.items():
            primary_values = metrics(group, rank_column, False)
            sensitivity_values = metrics(group, rank_column, True)
            per_question[question_id] = {
                "primary_uncertain_excluded": {
                    "hit_at_depth": bool(primary_values[0]),
                    "reciprocal_rank_at_depth": primary_values[1],
                    "pooled_recall_at_depth": primary_values[2],
                },
                "sensitivity_uncertain_included": {
                    "hit_at_depth": bool(sensitivity_values[0]),
                    "reciprocal_rank_at_depth": sensitivity_values[1],
                    "pooled_recall_at_depth": sensitivity_values[2],
                },
            }
        output["systems"][system] = {**variants, "per_question": per_question}
    return output


def evaluate(
    questions: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    k: int = 5,
    expander: GlossaryExpander | None = None,
) -> dict[str, Any]:
    labeled = [question for question in questions if question.get("expected_case_ids")]
    if not labeled:
        raise ValueError("평가할 라벨이 없습니다. 질문별 expected_case_ids에 관련 사례 ID를 기록하세요.")

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
    parser.add_argument("--questions", type=Path, default=Path("data/evaluation/questions/rag_questions.jsonl"))
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--review-pool", type=Path, help="human-reviewed query-ablation candidate pool CSV")
    parser.add_argument("--compare-expansion", action="store_true", help="기본 검색과 용어 확장 검색을 같은 질문으로 비교")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    args = parser.parse_args()
    if args.review_pool:
        with args.review_pool.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        print(json.dumps(evaluate_candidate_pool(rows, args.k), ensure_ascii=False, indent=2))
        return
    questions, documents = load_questions(args.questions), load_corpus(args.corpus)
    if args.compare_expansion:
        expander = GlossaryExpander.from_csv(args.glossary)
        result = {
            "baseline": evaluate(questions, documents, args.k),
            "query_expansion": evaluate(questions, documents, args.k, expander),
        }
    else:
        result = evaluate(questions, documents, args.k)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

