"""Export a pooled candidate set for a small lexical query ablation."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from .query_expansion import DEFAULT_GLOSSARY, GlossaryExpander
from .search import DEFAULT_CORPUS, TOKEN_RE, bm25, load_corpus


STOPWORDS = {
    "사례", "재해", "사고", "위험성", "감소대책", "대책", "예방", "조치", "주요", "원인",
    "유발요인", "위험요인", "요인", "방법", "상황", "작업", "또는", "중", "때", "하나",
}
PARTICLES = ("하려면", "해야", "하는", "한", "할", "으로", "에서", "에게", "까지", "부터", "처럼", "보다", "이라", "라고", "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "나", "로")
GENERIC_PREFIXES = ("찾아", "알려", "보여", "발생", "위험성", "감소대책", "예방", "조치", "필요", "무엇", "어떤", "확인", "일으키", "유발", "막", "안전대책")


def is_generic(token: str) -> bool:
    stem = token
    for particle in PARTICLES:
        if stem.endswith(particle) and len(stem) > len(particle) + 1:
            stem = stem[: -len(particle)]
            break
    if stem.endswith("사고") and len(stem) > 2:
        stem = stem[:-2]
    return stem in STOPWORDS or any(stem.startswith(prefix) for prefix in GENERIC_PREFIXES)


def focused_query(question: str) -> str:
    terms = []
    for word in TOKEN_RE.findall(question.lower()):
        stem = word
        for particle in PARTICLES:
            if stem.endswith(particle) and len(stem) > len(particle) + 1:
                stem = stem[: -len(particle)]
                break
        if stem.endswith("사고") and len(stem) > 2:
            stem = stem[:-2]
        if not is_generic(word):
            terms.append(stem)
    return " ".join(terms) or question

def load_questions(path: Path, limit: int) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        questions = [json.loads(line) for line in source if line.strip()]
    return questions[:limit]


def build_pool(questions: list[dict[str, Any]], corpus: list[dict[str, Any]], glossary: GlossaryExpander, k: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pooled: dict[tuple[str, str], dict[str, Any]] = {}
    counts = {"raw": 0, "focused": 0, "glossary": 0}
    for question in questions:
        qid = question["id"]
        variants = {
            "raw": question["question"],
            "focused": focused_query(question["question"]),
            "glossary": str(glossary.expand(question["question"])["expanded_query"]),
        }
        for variant, query in variants.items():
            results = bm25(query, corpus, k=k, industry=question.get("industry_filter"))
            counts[variant] += len(results)
            for rank, (score, document) in enumerate(results, start=1):
                key = (qid, document["case_id"])
                row = pooled.setdefault(key, {
                    "question_id": qid,
                    "question": question["question"],
                    "focused_query": variants["focused"],
                    "industry_filter": question.get("industry_filter") or "",
                    "case_id": document["case_id"],
                    "pool_depth": k,
                    "relevance_label": "",
                    "reviewer": "",
                    "review_status": "candidate",
                    "evidence_reference": document.get("source_url", ""),
                    "review_notes": "",
                })
                row[f"{variant}_rank"] = rank
                row[f"{variant}_score"] = round(score, 6)
                fields = document.get("fields", {})
                for out, field in (("incident_overview", "disasterOverview"), ("object_text", "orgtNm"), ("high_risk_work", "situation"), ("precursor", "disasterFactor"), ("control_measure", "dcrsCntrplnCn")):
                    row[out] = fields.get(field, "")
                row["source_url"] = document.get("source_url", "")
    order = {question["id"]: index for index, question in enumerate(questions)}
    rows = sorted(pooled.values(), key=lambda row: (order[row["question_id"]], min(row.get("raw_rank", 999), row.get("focused_rank", 999), row.get("glossary_rank", 999))))
    return rows, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a pooled candidate set for raw, focused, and glossary BM25 queries")
    parser.add_argument("--questions", type=Path, default=Path("data/evaluation/questions/rag_questions_100.jsonl"))
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/labels/rag_query_ablation_pilot_10q.csv"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("-k", type=int, default=3)
    args = parser.parse_args()
    questions = load_questions(args.questions, args.limit)
    corpus = load_corpus(args.corpus)
    glossary = GlossaryExpander.from_csv(args.glossary)
    rows, counts = build_pool(questions, corpus, glossary, args.k)
    columns = ["question_id", "question", "focused_query", "industry_filter", "case_id", "pool_depth", "raw_rank", "raw_score", "focused_rank", "focused_score", "glossary_rank", "glossary_score", "relevance_label", "reviewer", "review_status", "evidence_reference", "review_notes", "incident_overview", "object_text", "high_risk_work", "precursor", "control_measure", "source_url"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"questions={len(questions)} pooled_candidates={len(rows)} raw_rows={counts['raw']} focused_rows={counts['focused']} glossary_rows={counts['glossary']} output={args.output}")
    for question in questions:
        qid = question["id"]
        print(f"{qid}: focused_query={focused_query(question['question'])}")


if __name__ == "__main__":
    main()