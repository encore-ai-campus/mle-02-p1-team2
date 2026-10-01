"""Load preprocessed dashboard metrics and glossary pairs into PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
MIGRATION = ROOT / "sql" / "002_analytics_and_glossary.sql"

INDUSTRY_FILES = (
    "15084672_industry_size_accident_injured_2025_tidy.csv",
    "15084674_industry_size_fatalities_2025_tidy.csv",
    "15064487_industry_size_workplaces_2025_tidy.csv",
    "15064491_industry_size_fatality_rate_2025_tidy.csv",
)
TREND_FILE = "15084663_accident_fatalities_by_size_2004_2025_tidy.csv"
GLOSSARY_FILE = "15161288_safety_glossary_pairs.csv"


def optional_text(value: Any) -> str | None:
    return None if pd.isna(value) else str(value)


def load_industry_file(conn: psycopg.Connection, path: Path) -> int:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    required = {
        "reference_date", "industry_major", "industry_mid", "business_size",
        "metric", "value", "source_row",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: 필수 컬럼 누락 {sorted(missing)}")
    dataset_id = path.name.split("_", 1)[0]
    source_url = f"https://www.data.go.kr/data/{dataset_id}/fileData.do"
    rows = []
    for row in frame.to_dict(orient="records"):
        rows.append((
            dataset_id,
            row["reference_date"],
            row["industry_major"],
            row["industry_mid"],
            row["business_size"],
            row["metric"],
            None if pd.isna(row["value"]) else row["value"],
            optional_text(row.get("industry_major_raw")),
            optional_text(row.get("industry_mid_raw")),
            optional_text(row.get("source_size_column")),
            int(row["source_row"]),
            path.name,
            source_url,
        ))
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO industry_statistics
               (dataset_id, reference_date, industry_major, industry_mid, business_size,
                metric, value, industry_major_raw, industry_mid_raw, source_size_column,
                source_row, source_file, source_url)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (dataset_id, source_row, business_size) DO UPDATE SET
                 reference_date = EXCLUDED.reference_date,
                 industry_major = EXCLUDED.industry_major,
                 industry_mid = EXCLUDED.industry_mid,
                 metric = EXCLUDED.metric,
                 value = EXCLUDED.value,
                 industry_major_raw = EXCLUDED.industry_major_raw,
                 industry_mid_raw = EXCLUDED.industry_mid_raw,
                 source_size_column = EXCLUDED.source_size_column,
                 source_file = EXCLUDED.source_file,
                 source_url = EXCLUDED.source_url""",
            rows,
        )
    return len(rows)


def load_trend_file(conn: psycopg.Connection, path: Path) -> int:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    required = {"year", "business_size", "metric", "value", "source_year_column", "source_row"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: 필수 컬럼 누락 {sorted(missing)}")
    dataset_id = path.name.split("_", 1)[0]
    source_url = f"https://www.data.go.kr/data/{dataset_id}/fileData.do"
    rows = [(
        dataset_id,
        int(row["year"]),
        row["business_size"],
        row["metric"],
        None if pd.isna(row["value"]) else row["value"],
        optional_text(row.get("구분")),
        optional_text(row.get("source_year_column")),
        int(row["source_row"]),
        path.name,
        source_url,
    ) for row in frame.to_dict(orient="records")]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO fatality_trends
               (dataset_id, year, business_size, metric, value, source_category,
                source_year_column, source_row, source_file, source_url)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (dataset_id, year, business_size) DO UPDATE SET
                 metric = EXCLUDED.metric,
                 value = EXCLUDED.value,
                 source_category = EXCLUDED.source_category,
                 source_year_column = EXCLUDED.source_year_column,
                 source_row = EXCLUDED.source_row,
                 source_file = EXCLUDED.source_file,
                 source_url = EXCLUDED.source_url""",
            rows,
        )
    return len(rows)


def load_glossary_file(conn: psycopg.Connection, path: Path) -> int:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    required = {"dictionary_type", "canonical_term", "variant", "variant_position", "source_member"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: 필수 컬럼 누락 {sorted(missing)}")
    rows = [(
        row["dictionary_type"], row["canonical_term"], row["variant"],
        None if pd.isna(row["variant_position"]) else int(row["variant_position"]),
        row["source_member"],
    ) for row in frame.to_dict(orient="records")]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO safety_glossary_pairs
               (dictionary_type, canonical_term, variant, variant_position, source_member)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (dictionary_type, canonical_term, variant, source_member)
               DO UPDATE SET variant_position = EXCLUDED.variant_position""",
            rows,
        )
    return len(rows)


def main() -> None:
    load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise EnvironmentError(f"{ROOT / '.env'}에 DATABASE_URL이 필요합니다.")
    paths = [PROCESSED / name for name in (*INDUSTRY_FILES, TREND_FILE, GLOSSARY_FILE)]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"전처리 파일이 없습니다: {missing}")

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        conn.execute(MIGRATION.read_text(encoding="utf-8"), prepare=False)
        counts: dict[str, int] = {}
        for name in INDUSTRY_FILES:
            path = PROCESSED / name
            counts[path.stem] = load_industry_file(conn, path)
        counts[TREND_FILE.removesuffix(".csv")] = load_trend_file(conn, PROCESSED / TREND_FILE)
        counts[GLOSSARY_FILE.removesuffix(".csv")] = load_glossary_file(conn, PROCESSED / GLOSSARY_FILE)
        conn.commit()

        stored = {
            "industry_statistics": conn.execute("SELECT count(*) FROM industry_statistics").fetchone()[0],
            "fatality_trends": conn.execute("SELECT count(*) FROM fatality_trends").fetchone()[0],
            "safety_glossary_pairs": conn.execute("SELECT count(*) FROM safety_glossary_pairs").fetchone()[0],
        }
    print("이번 실행 입력 행:")
    for name, count in counts.items():
        print(f"- {name}: {count:,}")
    print("DB 전체 행:")
    for name, count in stored.items():
        print(f"- {name}: {count:,}")


if __name__ == "__main__":
    main()
