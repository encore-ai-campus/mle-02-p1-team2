"""Day 7·8 노트북의 CSV 로딩과 통계 조회 로직."""

from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
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


def source_files(data_dir: Path = DATA_DIR) -> dict[tuple[str, int], Path]:
    """Day 8의 파일 매핑 방식대로 기존 2025 원본과 history 파일을 연결한다."""
    files = {
        (metric, year): data_dir / "history" / f"{stem}_{year}.csv"
        for metric, stem in METRIC_FILES.items()
        for year in YEARS[:-1]
    }
    files.update({(metric, 2025): data_dir / name for metric, name in SOURCE_2025.items()})
    return {key: path for key, path in files.items() if path.is_file()}


def load_stat_csv(metric: str, year: int, path: Path) -> pd.DataFrame:
    """Day 7·8처럼 크기가 가로열인 CSV를 공통 long 형식으로 변환한다."""
    wide = pd.read_csv(path, encoding="utf-8-sig")
    if wide.shape[1] != 12 or wide.columns[:2].tolist() != ["대업종", "구분"]:
        raise ValueError(f"예상과 다른 산업중분류×규모 CSV 구조: {path}")
    wide.columns = ["대업종", "산업중분류", *SIZE_ORDER]
    wide["산업중분류"] = wide["산업중분류"].astype(str).str.strip()
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


def load_statistics(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Day 8 통합 데이터와 Day 7의 2025 사업장수를 한 번에 읽는다."""
    frames = [load_stat_csv(metric, year, path) for (metric, year), path in source_files(data_dir).items()]
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
