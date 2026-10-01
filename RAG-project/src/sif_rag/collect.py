"""Collect a bounded set of keyword searches from the SIF archive API."""

from __future__ import annotations

import argparse
from pathlib import Path

from .sif_openapi import SIFOpenAPI, collect_queries, read_queries


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect SIF archive records by overview keywords")
    parser.add_argument("--queries", type=Path, default=Path("data/sif_seed_terms.txt"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/sif_openapi_cases.jsonl"))
    parser.add_argument("--category", default="1", help="SIF API cateSeCd; default follows the portal example")
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()

    queries = read_queries(args.queries)
    client = SIFOpenAPI(category_code=args.category)
    added = collect_queries(client, queries, args.output, args.rows, args.max_pages)
    print(f"새 사례 {added}건 저장: {args.output}")
    print("키워드 기반 표본 수집입니다. 전체 아카이브 수집을 의미하지 않습니다.")


if __name__ == "__main__":
    main()

