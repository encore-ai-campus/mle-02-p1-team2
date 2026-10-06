"""Day 7·8 노트북의 CSV 로딩과 통계 조회 로직."""

from io import BytesIO
import logging
import os
from pathlib import Path
import re

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

from services.statistics_storage import StatisticsStorageError, download_csvs


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
load_dotenv(Path(__file__).resolve().parents[3] / ".env")
logger = logging.getLogger(__name__)
YEARS = tuple(range(2020, 2026))
SIZE_ORDER = (
    "5인 미만", "5-9인", "10-19인", "20-29인", "30-49인",
    "50-99인", "100-299인", "300-499인", "500-999인", "1000인 이상",
)
METRIC_FILES = {
    "사고재해자수": "accident_injured",
    "사고사망자수": "accident_death",
    "사망만인율": "fatality_rate",
}
METRICS = ("사고재해자수", "사고사망자수", "사업장수", "사망만인율")
COUNT_METRICS = frozenset(("사고재해자수", "사고사망자수", "사업장수"))
SOURCE_2025 = {
    "사고재해자수": "한국산업안전보건공단_산업중분류별 규모별 사고재해자수_20251231.csv",
    "사고사망자수": "한국산업안전보건공단_산업중분류별 규모별 사고사망자수_20251231.csv",
    "사업장수": "한국산업안전보건공단_산업중분류별 규모별 사업장수_20251231.csv",
    "사망만인율": "한국산업안전보건공단_산업중분류별 규모별 사망만인율_20251231.csv",
}
POSTGRES_STAT_METRICS = frozenset(METRICS)
POSTGRES_STAT_YEAR = 2025
POSTGRES_STAT_REFERENCE_DATE = "2025-12-31"
_SIZE_LABELS = {
    "5인미만": "5인 미만",
    "5인9인": "5-9인",
    "10인19인": "10-19인",
    "20인29인": "20-29인",
    "30인49인": "30-49인",
    "50인99인": "50-99인",
    "100인299인": "100-299인",
    "300인499인": "300-499인",
    "500인999인": "500-999인",
    "1000인이상": "1000인 이상",
}


def _database_url() -> str | None:
    """Streamlit Secrets 우선, 로컬에서는 .env의 DB 주소를 사용한다."""
    for name in ("SUPABASE_DB_URL", "DATABASE_URL"):
        try:
            value = st.secrets.get(name)
        except (FileNotFoundError, KeyError):
            value = None
        value = value or os.getenv(name)
        if value:
            return str(value)
    return None


def _size_from_label(label: str) -> str | None:
    normalized = re.sub(r"[\s\-–—]", "", label)
    return next((size for key, size in _SIZE_LABELS.items() if normalized.startswith(key)), None)


def _statistics_from_documents(rows: list[tuple[str, str, dict]]) -> pd.DataFrame:
    """RAG DB의 2025 통계 문서를 대시보드용 long 형식으로 읽는다."""
    records = []
    seen = set()
    industries_by_metric: dict[str, set[str]] = {}

    for source_id, content, metadata in rows:
        metadata = metadata or {}
        metric = metadata.get("metric")
        industry = metadata.get("industry")
        sector = metadata.get("sector")
        if (metric not in POSTGRES_STAT_METRICS
                or metadata.get("reference_date") != POSTGRES_STAT_REFERENCE_DATE
                or not industry or not sector or not isinstance(content, str)):
            raise ValueError(f"통계 문서 metadata 형식을 확인해 주세요: {source_id}")
        document_key = (metric, industry)
        if document_key in seen:
            raise ValueError(f"통계 문서가 중복되었습니다: {source_id}")
        seen.add(document_key)
        industries_by_metric.setdefault(metric, set()).add(industry)

        values = {}
        for line in content.splitlines():
            if ":" not in line:
                continue
            label, raw_value = line.rsplit(":", 1)
            size = _size_from_label(label.strip())
            if size is None:
                continue
            raw_value = raw_value.strip().replace(",", "")
            value = pd.to_numeric(raw_value, errors="coerce")
            if pd.isna(value) and raw_value not in {"자료 없음", "자료없음", "", "-", "—"}:
                raise ValueError(f"통계 값 형식을 확인해 주세요: {source_id}")
            if size in values:
                raise ValueError(f"규모 구간이 중복되었습니다: {source_id}")
            values[size] = value

        if set(values) != set(SIZE_ORDER):
            raise ValueError(f"10개 규모 구간을 모두 찾지 못했습니다: {source_id}")
        for size in SIZE_ORDER:
            records.append({
                "연도": POSTGRES_STAT_YEAR,
                "대업종": sector,
                "산업중분류": industry,
                "규모": size,
                "지표": metric,
                "값": values[size],
            })

    if set(industries_by_metric) != POSTGRES_STAT_METRICS:
        raise ValueError("2025년 통계 4개 지표가 모두 DB에 있는지 확인해 주세요.")
    if len({frozenset(items) for items in industries_by_metric.values()}) != 1:
        raise ValueError("2025년 통계 지표별 산업중분류 구성이 서로 다릅니다.")
    if len(next(iter(industries_by_metric.values()))) != 30:
        raise ValueError("2025년 통계에서 예상한 산업중분류 30개를 확인하지 못했습니다.")

    data = pd.DataFrame.from_records(records)
    data["규모"] = pd.Categorical(data["규모"], categories=SIZE_ORDER, ordered=True)
    return data.sort_values(["연도", "산업중분류", "규모", "지표"]).reset_index(drop=True)


def _load_statistics_from_postgres() -> pd.DataFrame | None:
    """Storage 대체 경로. 기존 임베딩 테이블의 2025 통계만 읽고 수정하지 않는다."""
    database_url = _database_url()
    if not database_url:
        return None
    try:
        with psycopg.connect(database_url, connect_timeout=8) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """SELECT source_id, content, metadata
                   FROM public.rag_day1_documents
                   WHERE kind = %s AND metadata->>'reference_date' = %s
                   ORDER BY source_id""",
                ("industry_stat", POSTGRES_STAT_REFERENCE_DATE),
            ).fetchall()
        if not rows:
            return None
        data = _statistics_from_documents(rows)
        data.attrs["source_warning"] = (
            "통계 Storage 인증에 실패해 DB에 저장된 2025년 통계로 표시 중입니다. "
            "2020~2024년 자료는 이 DB에 없어 장기 추세에서 비어 있습니다."
        )
        data.attrs["data_source"] = "public.rag_day1_documents · industry_stat · 2025-12-31"
        return data
    except (psycopg.Error, ValueError):
        logger.exception("DB에 저장된 2025 통계 대체 경로도 사용할 수 없습니다.")
        return None


def source_files(data_dir: Path = DATA_DIR) -> dict[tuple[str, int], Path]:
    """Day 8의 파일 매핑 방식대로 기존 2025 원본과 history 파일을 연결한다."""
    files = {
        (metric, year): data_dir / "history" / f"{stem}_{year}.csv"
        for metric, stem in METRIC_FILES.items()
        for year in YEARS[:-1]
    }
    files.update({(metric, 2025): data_dir / name for metric, name in SOURCE_2025.items()})
    return {key: path for key, path in files.items() if path.is_file()}


def storage_files() -> dict[tuple[str, int], str]:
    """현재 업로드된 18개 CSV의 영문 Storage 경로."""
    files = {
        (metric, year): f"history/{stem}_{year}.csv"
        for metric, stem in METRIC_FILES.items()
        for year in YEARS[:-1]
        # 제공되지 않은 2021 사망만인율은 기존 추세 함수가 NaN으로 유지한다.
        if (metric, year) != ("사망만인율", 2021)
    }
    stems = {**METRIC_FILES, "사업장수": "business_count"}
    files.update({(metric, 2025): f"{stem}_2025.csv" for metric, stem in stems.items()})
    return files


def load_stat_csv(metric: str, year: int, path: Path | BytesIO) -> pd.DataFrame:
    """Day 7·8처럼 크기가 가로열인 CSV를 공통 long 형식으로 변환한다."""
    try:
        wide = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except UnicodeDecodeError:
        if hasattr(path, "seek"):
            path.seek(0)
        wide = pd.read_csv(path, encoding="cp949", dtype=str, keep_default_na=False)
    if wide.shape[1] != 12 or wide.columns[:2].tolist() != ["대업종", "구분"]:
        raise ValueError(f"예상과 다른 산업중분류×규모 CSV 구조: {path}")
    wide.columns = ["대업종", "산업중분류", *SIZE_ORDER]
    for column in ("대업종", "산업중분류"):
        wide[column] = wide[column].astype(str).str.strip()
        if wide[column].eq("").any():
            raise ValueError(f"산업 구분 값이 비어 있습니다: {path}")
    if len(wide) != 30 or wide["산업중분류"].nunique() != 30:
        raise ValueError(f"산업중분류 30개 행 또는 중복 여부를 확인해 주세요: {path}")

    missing_values = {"", "-", "—", "–", "자료 없음", "자료없음", "N/A", "NA"}
    for column in SIZE_ORDER:
        raw = wide[column].str.strip().str.replace(",", "", regex=False)
        numeric = pd.to_numeric(raw.mask(raw.isin(missing_values)), errors="coerce")
        invalid = raw.ne("") & ~raw.isin(missing_values) & numeric.isna()
        if invalid.any():
            raise ValueError(f"숫자로 변환할 수 없는 통계 값이 있습니다: {path}")
        wide[column] = numeric
    long = wide.melt(
        id_vars=["대업종", "산업중분류"],
        value_vars=SIZE_ORDER,
        var_name="규모",
        value_name="값",
    )
    long["값"] = pd.to_numeric(long["값"], errors="coerce")
    long.insert(0, "연도", year)
    long.insert(4, "지표", metric)
    return long


def load_statistics(data_dir: Path | None = None) -> pd.DataFrame:
    """Private Storage를 우선 사용하고, 실패 시 검증된 2025 DB 통계를 읽는다."""
    if data_dir is None:
        try:
            contents = download_csvs(storage_files())
        except StatisticsStorageError:
            fallback = _load_statistics_from_postgres()
            if fallback is not None:
                return fallback
            raise
        if contents is not None:
            sources = {key: BytesIO(body) for key, body in contents.items()}
        else:
            sources = source_files(DATA_DIR)
            if not sources:
                fallback = _load_statistics_from_postgres()
                if fallback is not None:
                    return fallback
    else:
        contents = None
        sources = source_files(data_dir)
    frames = [load_stat_csv(metric, year, source) for (metric, year), source in sources.items()]
    if not frames:
        return pd.DataFrame(columns=["연도", "대업종", "산업중분류", "규모", "지표", "값"])
    data = pd.concat(frames, ignore_index=True)
    data["규모"] = pd.Categorical(data["규모"], categories=SIZE_ORDER, ordered=True)
    return data.sort_values(["연도", "산업중분류", "규모", "지표"]).reset_index(drop=True)


def filter_statistics(
    data: pd.DataFrame,
    *,
    year: int | None = None,
    industry: str | None = None,
    size: str | None = None,
    metric: str | None = None,
) -> pd.DataFrame:
    """Day 8 query_stats의 공통 조건 조회를 대시보드에도 사용한다."""
    result = data
    for column, selected in (("연도", year), ("산업중분류", industry), ("규모", size), ("지표", metric)):
        if selected is not None:
            result = result.loc[result[column] == selected]
    return result


def available_metrics(data: pd.DataFrame, year: int) -> list[str]:
    """해당 연도에 실제 CSV가 있는 지표만 돌려준다."""
    present = set(filter_statistics(data, year=year)["지표"])
    return [metric for metric in METRICS if metric in present]


def kpi_value(data: pd.DataFrame, year: int, industry: str | None, size: str | None, metric: str) -> float | None:
    """건수는 합산하고, 분모가 없는 사망만인율은 단일 산업·규모에서만 조회한다."""
    if metric == "사망만인율" and (industry is None or size is None):
        return None
    selected = filter_statistics(data, year=year, industry=industry, size=size, metric=metric)
    values = selected["값"].dropna()
    if values.empty:
        return None
    return float(values.sum()) if metric in COUNT_METRICS else float(values.iloc[0])


def six_year_trend(data: pd.DataFrame, industry: str, size: str, metric: str) -> pd.DataFrame:
    """Day 8 six_year_trend처럼 6개 연도를 유지하고 누락 연도는 NaN으로 둔다."""
    selected = filter_statistics(data, industry=industry, size=size, metric=metric)
    trend = selected.groupby("연도", observed=True)["값"].first().reindex(YEARS)
    return trend.rename_axis("연도").reset_index()


def industry_totals(data: pd.DataFrame, year: int, metric: str, size: str | None = None) -> pd.DataFrame:
    """Day 8의 건수 합산을 산업중분류 기준으로 수행한다. 규모는 상세 필터다."""
    if metric not in COUNT_METRICS:
        raise ValueError("건수 지표만 산업별 합산할 수 있습니다.")
    rows = filter_statistics(data, year=year, size=size, metric=metric).dropna(subset=["값"])
    return rows.groupby("산업중분류", as_index=False, observed=True)["값"].sum()


def industry_death_rate_comparison(data: pd.DataFrame, year: int, size: str | None = None) -> pd.DataFrame:
    """사망 건수와 규모별 사망만인율 중앙값을 나란히 조회한다. 중앙값은 업종 전체율이 아니다."""
    deaths = industry_totals(data, year, "사고사망자수", size).rename(columns={"값": "사고사망자수"})
    rates = filter_statistics(data, year=year, size=size, metric="사망만인율").dropna(subset=["값"])
    rates = rates.groupby("산업중분류", as_index=False, observed=True)["값"].median()
    rates = rates.rename(columns={"값": "비교 사망만인율"})
    return deaths.merge(rates, on="산업중분류", how="left")


def industry_trend(data: pd.DataFrame, industry: str, metric: str, size: str | None = None) -> pd.DataFrame:
    """Day 8의 6년 추세를 산업 기준으로 확장한다. 건수는 합계, 비율은 규모별 중앙값이다."""
    rows = filter_statistics(data, industry=industry, size=size, metric=metric).dropna(subset=["값"])
    grouped = rows.groupby("연도", observed=True)["값"]
    values = grouped.sum() if metric in COUNT_METRICS else grouped.median()
    return values.reindex(YEARS).rename_axis("연도").reset_index()
