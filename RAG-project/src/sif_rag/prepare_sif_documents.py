"""Normalize SIF API cases into one traceable RAG document per case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


TEXT_FIELDS = (
    ("재해개요", "disasterOverview"),
    ("기인물", "orgtNm"),
    ("고위험작업·상황", "situation"),
    ("재해유발요인", "disasterFactor"),
    ("위험성 감소대책", "dcrsCntrplnCn"),
)
INDUSTRY_FIELDS = (
    ("산재업종 대분류", "sifLclsfNm"),
    ("산재업종 중분류", "sifMclsfNm"),
    ("산재업종 소분류", "sifSclsfNm"),
)


def clean(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def make_document(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields") or {}
    industry = [(label, clean(fields.get(name))) for label, name in INDUSTRY_FIELDS]
    industry_values = [value for _, value in industry if value]

    sections: list[str] = []
    if industry_values:
        sections.append("업종: " + " > ".join(industry_values))
    disaster_type = clean(fields.get("disasterType"))
    if disaster_type:
        sections.append(f"재해종류: {disaster_type}")
    for label, key in TEXT_FIELDS:
        value = clean(fields.get(key))
        if value:
            sections.append(f"{label}: {value}")

    page_content = "\n".join(sections)
    if not page_content:
        raise ValueError(f"검색 본문이 없는 사례입니다: {record.get('case_id', '(case_id 없음)')}")
    if not record.get("case_id"):
        raise ValueError("case_id가 없는 API 사례가 있습니다.")

    metadata = {
        "case_id": record["case_id"],
        "source_dataset_id": "15161362",
        "source_url": record.get("source_url", ""),
        "retrieved_by_seed": record.get("retrieved_query", ""),
        "industry_category_raw": clean(fields.get("cateSeNm")),
        "industry_major": clean(fields.get("sifLclsfNm")),
        "industry_mid": clean(fields.get("sifMclsfNm")),
        "industry_small": clean(fields.get("sifSclsfNm")),
        "disaster_type": disaster_type,
        "object_text": clean(fields.get("orgtNm")),
        "high_risk_work": clean(fields.get("situation")),
        "precursor": clean(fields.get("disasterFactor")),
        "control_measure": clean(fields.get("dcrsCntrplnCn")),
    }
    # Keep original API fields for source traceability and backward-compatible filtering.
    return {
        "case_id": record["case_id"],
        "source_url": record.get("source_url", ""),
        "retrieved_query": record.get("retrieved_query", ""),
        "fields": fields,
        "metadata": metadata,
        "page_content": page_content,
    }


def prepare(input_path: Path, output_path: Path) -> tuple[int, int, int]:
    if not input_path.exists():
        raise FileNotFoundError(f"API 코퍼스가 없습니다: {input_path}")
    frame = pd.read_json(input_path, lines=True, encoding="utf-8")
    if frame.empty:
        raise ValueError(f"API 코퍼스가 비어 있습니다: {input_path}")

    records = frame.to_dict(orient="records")
    documents = [make_document(record) for record in records]
    ids = [document["case_id"] for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("중복 case_id가 있어 문서 출력을 중단했습니다.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as target:
        for document in documents:
            target.write(json.dumps(document, ensure_ascii=False) + "\n")

    lengths = [len(document["page_content"]) for document in documents]
    return len(documents), min(lengths), max(lengths)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one traceable retrieval document per SIF API case")
    parser.add_argument("--input", type=Path, default=Path("data/raw/sif_openapi_cases.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/sif_rag_documents.jsonl"))
    args = parser.parse_args()
    count, min_chars, max_chars = prepare(args.input, args.output)
    print(f"documents={count} chars_min={min_chars} chars_max={max_chars} output={args.output}")
    print("Chunking: one API case per document; no automatic labels or embeddings generated.")


if __name__ == "__main__":
    main()
