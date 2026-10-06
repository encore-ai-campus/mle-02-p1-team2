"""BM25 baseline over the frozen multi-source evaluation set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

K1 = 1.5
B = 0.75
TOP_K = 5


def _bm25_scores(query: str, vectorizer: CountVectorizer, matrix,
                idf: np.ndarray, lengths: np.ndarray, average_length: float,
                *, k1: float = K1, b: float = B) -> np.ndarray:
    """Okapi BM25 scores over character n-gram terms for one query."""
    query_vector = vectorizer.transform([query]).tocoo()
    scores = np.zeros(matrix.shape[0], dtype=np.float32)
    if not len(query_vector.data):
        return scores

    length_norm = k1 * (1.0 - b + b * lengths / max(average_length, 1.0))
    for term_id, query_frequency in zip(query_vector.col, query_vector.data):
        term_frequency = np.asarray(matrix[:, term_id].toarray()).ravel()
        scores += idf[term_id] * (
            term_frequency * (k1 + 1.0) / (term_frequency + length_norm)
        ) * query_frequency
    return scores


def _rank_unique_documents(scores: np.ndarray, doc_ids: np.ndarray,
                           chunk_ids: np.ndarray, *, source_types: np.ndarray,
                           source_filter: str | None, limit: int = TOP_K) -> list[str]:
    candidate_scores = scores.copy()
    if source_filter is not None:
        candidate_scores[source_types != source_filter] = -np.inf
    order = np.lexsort((chunk_ids, doc_ids, -candidate_scores))
    ranked: list[str] = []
    seen: set[str] = set()
    for position in order:
        if not np.isfinite(candidate_scores[position]):
            break
        doc_id = str(doc_ids[position])
        if doc_id in seen:
            continue
        ranked.append(doc_id)
        seen.add(doc_id)
        if len(ranked) == limit:
            break
    return ranked


def _measure(gold_ids: set[str], ranked: list[str]) -> dict[str, float | int]:
    ranks = [rank for rank, doc_id in enumerate(ranked[:TOP_K], start=1)
             if doc_id in gold_ids]
    return {
        "hit1": int(bool(ranks and ranks[0] == 1)),
        "hit5": int(bool(ranks)),
        "precision5": len(ranks) / TOP_K,
        "mrr5": 1.0 / ranks[0] if ranks else 0.0,
    }


def evaluate_bm25(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate BM25 for each frozen question with filtered and full-corpus search."""
    corpus_dir = root / "data/personal/corpus"
    evaluation_dir = root / "data/personal/evaluation"
    question_path = evaluation_dir / "questions_multisource.csv"
    chunk_path = corpus_dir / "chunks.jsonl"
    questions = pd.read_csv(question_path, dtype=str, keep_default_na=False)
    question_sha256 = hashlib.sha256(question_path.read_bytes()).hexdigest()
    expected_question_sha256 = "a3c203f222c24c7dfed74ba5486cde3faa181558e28eb4e7433a4509035872a0"
    if len(questions) != 21 or not questions["qid"].is_unique:
        raise ValueError("Expected the frozen 21-question evaluation set")
    if question_sha256 != expected_question_sha256:
        raise ValueError("Evaluation questions changed; review labels before rerunning BM25")

    chunks: list[dict] = []
    with chunk_path.open(encoding="utf-8") as source:
        for line in source:
            chunks.append(json.loads(line))
    if not chunks:
        raise ValueError("The chunk corpus is empty")

    texts = [str(chunk.get("text", "")) for chunk in chunks]
    doc_ids = np.asarray([str(chunk["doc_id"]) for chunk in chunks], dtype=object)
    chunk_ids = np.asarray([str(chunk["chunk_id"]) for chunk in chunks], dtype=object)
    source_types = np.asarray([str(chunk["source_type"]) for chunk in chunks], dtype=object)
    document_source_types = dict(zip(doc_ids.tolist(), source_types.tolist()))
    for question in questions.itertuples(index=False):
        for gold_id in question.gold_doc_ids.split("|"):
            if document_source_types.get(gold_id) != question.source_type:
                raise ValueError(f"Invalid gold document/source label: {question.qid} -> {gold_id}")

    # Korean morphology tools are not installed in this project. Character n-grams
    # keep BM25 usable without network access and are less sensitive to spacing/endings.
    vectorizer = CountVectorizer(
        analyzer="char_wb", ngram_range=(2, 4), lowercase=False, dtype=np.float32
    )
    matrix = vectorizer.fit_transform(texts).tocsr()
    document_frequency = np.asarray((matrix > 0).sum(axis=0)).ravel().astype(np.float32)
    chunk_count = matrix.shape[0]
    idf = np.log1p((chunk_count - document_frequency + 0.5) /
                   (document_frequency + 0.5)).astype(np.float32)
    lengths = np.asarray(matrix.sum(axis=1)).ravel().astype(np.float32)
    average_length = float(lengths.mean())

    rows: list[dict] = []
    for question in questions.itertuples(index=False):
        scores = _bm25_scores(question.query, vectorizer, matrix, idf,
                              lengths, average_length)
        gold_ids = set(question.gold_doc_ids.split("|"))
        for scope, source_filter in (
            ("source_filtered", question.source_type),
            ("all_sources", None),
        ):
            ranked = _rank_unique_documents(
                scores, doc_ids, chunk_ids, source_types=source_types,
                source_filter=source_filter,
            )
            rows.append({
                "qid": question.qid,
                "query": question.query,
                "gold_doc_ids": question.gold_doc_ids,
                "source_type": question.source_type,
                "scope": scope,
                "retrieved_doc_ids": "|".join(ranked),
                **_measure(gold_ids, ranked),
            })

    details = pd.DataFrame(rows)
    summary = (
        details.groupby(["scope", "source_type"], as_index=False)
        .agg(questions=("qid", "count"), hit1=("hit1", "mean"),
             hit5=("hit5", "mean"), precision5=("precision5", "mean"),
             mrr5=("mrr5", "mean"))
    )
    totals = (
        details.groupby("scope", as_index=False)
        .agg(questions=("qid", "count"), hit1=("hit1", "mean"),
             hit5=("hit5", "mean"), precision5=("precision5", "mean"),
             mrr5=("mrr5", "mean"))
    )
    totals["source_type"] = "ALL"
    summary = pd.concat([summary, totals], ignore_index=True)
    summary = summary[["scope", "source_type", "questions", "hit1", "hit5",
                       "precision5", "mrr5"]]

    evaluation_dir.mkdir(parents=True, exist_ok=True)
    details.to_csv(evaluation_dir / "bm25_details.csv", index=False,
                   encoding="utf-8-sig")
    summary.to_csv(evaluation_dir / "bm25_summary.csv", index=False,
                   encoding="utf-8-sig")
    metadata = {
        "questions_sha256": question_sha256,
        "chunks_sha256": hashlib.sha256(chunk_path.read_bytes()).hexdigest(),
        "questions": len(questions),
        "chunks": chunk_count,
        "unique_documents": int(len(set(doc_ids))),
        "top_k_unique_documents": TOP_K,
        "algorithm": "Okapi BM25 over chunk-level character n-grams",
        "tokenizer": "CountVectorizer char_wb, ngram_range=(2, 4)",
        "document_aggregation": "maximum chunk score per doc_id; unique doc_id ranking",
        "k1": K1,
        "b": B,
        "query_filter_scopes": ["source_filtered", "all_sources"],
        "embedding_or_llm_api_calls": 0,
    }
    (evaluation_dir / "bm25_meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return details, summary


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    _, scores = evaluate_bm25(project_root)
    print(scores.to_string(index=False))