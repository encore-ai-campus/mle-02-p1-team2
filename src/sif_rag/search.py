"""Small dependency-free BM25 baseline over collected SIF cases."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[가-힣]+|[A-Za-z]+|\d+")
DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "processed" / "sif_rag_documents.jsonl"


def tokenize(text: str) -> list[str]:
    words = TOKEN_RE.findall(text.lower())
    # Adjacent Hangul bigrams soften exact-spacing differences without an external tokenizer.
    tokens = list(words)
    for word in words:
        if len(word) > 2 and all("가" <= char <= "힣" for char in word):
            tokens.extend(word[index : index + 2] for index in range(len(word) - 1))
    return tokens


def load_corpus(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"코퍼스가 없습니다: {path}. 먼저 sif_rag.collect로 사례를 수집하세요.")
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def bm25(
    query: str,
    documents: list[dict[str, Any]],
    k: int = 5,
    industry: str | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    if industry:
        needle = industry.casefold()
        documents = [
            doc
            for doc in documents
            if any(
                needle in str(doc.get("fields", {}).get(field, "")).casefold()
                for field in ("cateSeNm", "sifLclsfNm", "sifMclsfNm", "sifSclsfNm")
            )
        ]
    if not documents:
        return []
    query_tokens = set(tokenize(query))
    tokenized = [tokenize(str(doc.get("page_content", ""))) for doc in documents]
    lengths = [len(tokens) for tokens in tokenized]
    average_length = sum(lengths) / len(lengths) or 1.0
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))

    k1, b = 1.5, 0.75
    scored: list[tuple[float, dict[str, Any]]] = []
    for doc, tokens, length in zip(documents, tokenized, lengths):
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_tokens:
            frequency = frequencies[term]
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_frequency = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * length / average_length)
            score += inverse_frequency * frequency * (k1 + 1) / denominator
        if score:
            scored.append((score, doc))
    return sorted(scored, key=lambda item: item[0], reverse=True)[:k]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collected SIF case lexical retrieval baseline")
    parser.add_argument("question", help="검색 질문")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--industry", help="업종 또는 작업 분류 필터(부분 일치)")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    for score, document in bm25(args.question, load_corpus(args.corpus), args.k, args.industry):
        print(f"\n[{score:.3f}] case={document['case_id']} | source={document['source_url']}")
        print(document["page_content"])


if __name__ == "__main__":
    main()

