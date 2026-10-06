"""OpenAI embedding and PostgreSQL + pgvector retrieval for SIF API cases."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import dotenv_values
from pgvector import Vector
from pgvector.psycopg import register_vector


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "data" / "processed" / "sif_rag_documents.jsonl"
DEFAULT_MODEL = "text-embedding-3-small"
VECTOR_DIMENSIONS = {"text-embedding-3-small": 1536}
SOURCE_NAME = "한국산업안전보건공단 SIF 조회 API (15161362)"


def load_config() -> dict[str, str]:
    """Load non-empty project settings first, then shared OpenAI credentials."""
    config = dict(os.environ)
    for env_path in (
        ROOT / ".env",
        Path("/mnt/c/study-with-ai/.env"),
        Path(r"C:\study-with-ai\.env"),
    ):
        if env_path.exists():
            for key, value in dotenv_values(env_path).items():
                if value and not config.get(key):
                    config[key] = value
    return config


def validate_embedding_model(model: str) -> None:
    if model not in VECTOR_DIMENSIONS:
        raise ValueError(
            f"Unsupported embedding model for the current vector(1536) schema: {model}. "
            "Only text-embedding-3-small with 1536 dimensions is supported."
        )


def embed_texts(texts: list[str], model: str) -> list[list[float]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK가 없습니다. requirements.txt를 설치하세요.") from exc
    config = load_config()
    if not config.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY를 프로젝트 .env 또는 C:\\study-with-ai\\.env에 설정하세요.")
    if not texts:
        return []
    response = OpenAI(api_key=config["OPENAI_API_KEY"]).embeddings.create(
        model=model,
        input=[text.replace("\n", " ") for text in texts],
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    vectors = [item.embedding for item in ordered]
    expected_dimensions = VECTOR_DIMENSIONS.get(model)
    if expected_dimensions is not None and any(len(vector) != expected_dimensions for vector in vectors):
        raise RuntimeError(
            f"Embedding response dimension does not match the PostgreSQL vector({expected_dimensions}) schema."
        )
    return vectors


def get_embedding_model() -> str:
    return load_config().get("EMBEDDING_MODEL") or DEFAULT_MODEL


def connect_database() -> psycopg.Connection:
    config = load_config()
    database_url = config.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("프로젝트 .env에 DATABASE_URL이 없습니다.")
    conn = psycopg.connect(database_url, connect_timeout=5)
    register_vector(conn)
    return conn


def load_documents(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"사례 문서가 없습니다: {path}")
    with path.open(encoding="utf-8") as source:
        documents = [json.loads(line) for line in source if line.strip()]
    if limit is not None:
        documents = documents[:limit]
    return documents


def _db_row(document: dict[str, Any], embedding: list[float], model: str) -> tuple[Any, ...]:
    fields = document.get("fields", {})
    return (
        document["case_id"],
        SOURCE_NAME,
        None,  # API record, not an XLSX sheet
        None,  # source row is not supplied by the API
        None,  # source serial is not supplied by the API
        fields.get("sifLclsfNm") or None,
        fields.get("sifMclsfNm") or None,
        fields.get("sifSclsfNm") or None,
        None,
        None,
        None,
        fields.get("disasterType") or None,
        fields.get("orgtNm") or None,
        fields.get("situation") or None,
        fields.get("disasterOverview") or None,
        fields.get("disasterFactor") or None,
        fields.get("dcrsCntrplnCn") or None,
        document.get("page_content", ""),
        model,
        Vector(embedding),
        document.get("source_url") or "https://www.data.go.kr/data/15161362/openapi.do",
    )


def ingest_documents(
    path: Path = DEFAULT_CORPUS,
    *,
    limit: int | None = None,
    batch_size: int = 100,
    model: str = DEFAULT_MODEL,
    force: bool = False,
) -> tuple[int, int]:
    validate_embedding_model(model)
    if batch_size < 1 or batch_size > 100:
        raise ValueError("batch_size는 1~100이어야 합니다.")
    documents = load_documents(path, limit)
    if not documents:
        return 0, 0

    with connect_database() as conn:
        with conn.transaction():
            conn.execute("ALTER TABLE sif_cases ALTER COLUMN source_sheet DROP NOT NULL")
            conn.execute("ALTER TABLE sif_cases ALTER COLUMN source_row DROP NOT NULL")
            conn.execute("ALTER TABLE sif_cases ALTER COLUMN source_serial DROP NOT NULL")
            if force:
                pending = documents
            else:
                ids = [doc["case_id"] for doc in documents]
                rows = conn.execute(
                    "SELECT case_id FROM sif_cases WHERE case_id = ANY(%s) AND embedding_model = %s",
                    (ids, model),
                ).fetchall()
                existing = {row[0] for row in rows}
                pending = [doc for doc in documents if doc["case_id"] not in existing]

        inserted = 0
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            print(f"임베딩 처리: {min(start + len(batch), len(pending))}/{len(pending)}", flush=True)
            vectors = embed_texts([str(doc.get("page_content", "")) for doc in batch], model)
            values = [_db_row(doc, vector, model) for doc, vector in zip(batch, vectors)]
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO sif_cases (
                               case_id, source_file, source_sheet, source_row, source_serial,
                               industry_major, industry_mid, industry_small,
                               construction_work, construction_task, unit_task, disaster_type,
                               object_text, high_risk_work, incident_overview, precursor,
                               control_measure, page_content, embedding_model, embedding, source_url
                           ) VALUES (
                               %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                           )
                           ON CONFLICT (case_id) DO UPDATE SET
                               source_file = EXCLUDED.source_file,
                               source_sheet = EXCLUDED.source_sheet,
                               source_row = EXCLUDED.source_row,
                               source_serial = EXCLUDED.source_serial,
                               industry_major = EXCLUDED.industry_major,
                               industry_mid = EXCLUDED.industry_mid,
                               industry_small = EXCLUDED.industry_small,
                               disaster_type = EXCLUDED.disaster_type,
                               object_text = EXCLUDED.object_text,
                               high_risk_work = EXCLUDED.high_risk_work,
                               incident_overview = EXCLUDED.incident_overview,
                               precursor = EXCLUDED.precursor,
                               control_measure = EXCLUDED.control_measure,
                               page_content = EXCLUDED.page_content,
                               embedding_model = EXCLUDED.embedding_model,
                               embedding = EXCLUDED.embedding,
                               source_url = EXCLUDED.source_url""",
                        values,
                    )
            inserted += len(batch)

    return len(documents), inserted


def vector_search(
    query: str,
    *,
    k: int = 3,
    industry: str | None = None,
    model: str | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    model = model or get_embedding_model()
    validate_embedding_model(model)
    with connect_database() as conn:
        has_vectors = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM sif_cases WHERE embedding_model = %s)", (model,)
        ).fetchone()[0]
        if not has_vectors:
            raise RuntimeError("pgvector에 임베딩 사례가 없습니다. 먼저 `python -m src.sif_rag.vector_store --limit 5`를 실행하세요.")
        query_vector = Vector(embed_texts([query], model)[0])
        rows = conn.execute(
            """SELECT case_id, industry_major, industry_mid, industry_small,
                      disaster_type, object_text, high_risk_work, incident_overview,
                      precursor, control_measure, page_content, source_url,
                      1 - (embedding <=> %s) AS similarity
               FROM sif_cases
               WHERE embedding_model = %s
                 AND (%s::text IS NULL OR industry_major ILIKE %s OR industry_mid ILIKE %s OR industry_small ILIKE %s)
               ORDER BY embedding <=> %s
               LIMIT %s""",
            (
                query_vector,
                model,
                industry,
                f"%{industry}%" if industry else None,
                f"%{industry}%" if industry else None,
                f"%{industry}%" if industry else None,
                query_vector,
                k,
            ),
        ).fetchall()

    results: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        (
            case_id, industry_major, industry_mid, industry_small, disaster_type,
            object_text, high_risk_work, overview, precursor, control, page_content,
            source_url, similarity,
        ) = row
        fields = {
            "sifLclsfNm": industry_major,
            "sifMclsfNm": industry_mid,
            "sifSclsfNm": industry_small,
            "disasterType": disaster_type,
            "orgtNm": object_text,
            "situation": high_risk_work,
            "disasterOverview": overview,
            "disasterFactor": precursor,
            "dcrsCntrplnCn": control,
        }
        results.append(
            (
                float(similarity),
                {
                    "case_id": case_id,
                    "fields": fields,
                    "page_content": page_content,
                    "source_url": source_url,
                },
            )
        )
    return results


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Embed SIF API cases and upsert them into PostgreSQL + pgvector")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--limit", type=int, help="개발·비용 확인용 앞부분 표본 수")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--model", default=get_embedding_model())
    parser.add_argument("--force", action="store_true", help="현재 모델의 기존 벡터도 다시 생성")
    args = parser.parse_args()
    total, inserted = ingest_documents(
        args.corpus, limit=args.limit, batch_size=args.batch_size, model=args.model, force=args.force
    )
    print(f"대상 사례: {total} | 신규/갱신 임베딩 적재: {inserted} | 모델: {args.model}")


if __name__ == "__main__":
    main()
