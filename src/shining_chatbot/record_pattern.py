"""Descriptive accident-record counts without exposure-based risk claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO

import pandas as pd

MAX_PATTERN_CSV_BYTES = 5 * 1024 * 1024
SEASONS = ("봄", "여름", "가을", "겨울")
SEASON_BY_MONTH = (3, 3, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3)


def season_index(month: int) -> int:
    """Return calendar season index (spring, summer, autumn, winter)."""
    return SEASON_BY_MONTH[month - 1]


@dataclass(frozen=True)
class RecordPattern:
    total: int
    first_day: date
    last_day: date
    weekdays: tuple[int, ...]
    months: tuple[int, ...]
    accident_types: tuple[tuple[str, int], ...]
    seasons: tuple[int, ...] = ()


def context_signals(pattern: RecordPattern, day: date) -> tuple[str, ...]:
    """Point to concentrated raw counts only when the record span is usable."""
    span = (pattern.last_day - pattern.first_day).days
    messages = []
    weekday_count = pattern.weekdays[day.weekday()]
    if (
        pattern.total >= 50 and span >= 180 and weekday_count >= 10
        and weekday_count == max(pattern.weekdays)
        and pattern.weekdays.count(weekday_count) == 1
        and weekday_count >= pattern.total / 7 * 1.5
    ):
        messages.append("같은 요일의 사고 기록 건수가 연결 자료에서 가장 많습니다. 작업 빈도와 인원 차이를 함께 확인하세요.")
    month_count = pattern.months[day.month - 1]
    if (
        pattern.total >= 100 and span >= 730 and month_count >= 10
        and month_count == max(pattern.months)
        and pattern.months.count(month_count) == 1
        and month_count >= pattern.total / 12 * 1.8
    ):
        messages.append("같은 달의 사고 기록 건수가 연결 자료에서 가장 많습니다. 달력상 시기만으로 원인을 단정하지 말고 작업량·공종 차이를 확인하세요.")
    season_counts = pattern.seasons
    season = season_index(day.month)
    if (
        len(season_counts) == 4 and pattern.total >= 100 and span >= 730
        and season_counts[season] >= 20 and season_counts[season] == max(season_counts)
        and season_counts.count(season_counts[season]) == 1
        and season_counts[season] >= pattern.total / 4 * 1.4
    ):
        messages.append(
            f"{SEASONS[season]}에 해당하는 달의 기록 건수가 연결 자료에서 가장 많습니다. "
            "기록 수집 기간과 계절별 작업량·공종 차이를 함께 확인하세요."
        )
    return tuple(messages)


def read_pattern_csv(content: bytes) -> pd.DataFrame:
    """Accept a small field log with date and accident type; ignore unrelated columns."""
    if len(content) > MAX_PATTERN_CSV_BYTES:
        raise ValueError("사고 기록 CSV는 5MB 이하여야 합니다.")
    try:
        try:
            frame = pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(BytesIO(content), encoding="cp949")
    except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError("CSV를 읽지 못했습니다. 인코딩과 표 형식을 확인하세요.") from exc
    aliases = {"사고일": "발생일", "사고일자": "발생일", "재해일": "발생일", "재해일자": "발생일", "재해유형": "사고유형"}
    frame.columns = [str(column).strip() for column in frame.columns]
    rename = {}
    targets = set(frame.columns)
    for column in frame.columns:
        canonical = aliases.get(column)
        if canonical and canonical not in targets:
            rename[column] = canonical
            targets.add(canonical)
    frame = frame.rename(columns=rename)
    if not {"발생일", "사고유형"}.issubset(frame.columns):
        raise ValueError("발생일과 사고유형 열이 필요합니다. 사고일·재해일자·재해유형도 사용할 수 있습니다.")
    result = frame.loc[:, ["발생일", "사고유형"]].copy()
    if result.empty:
        raise ValueError("CSV에 사고 기록이 없습니다.")
    if len(result) > 100_000:
        raise ValueError("분석할 사고 기록은 100,000건 이하여야 합니다.")
    result["발생일"] = pd.to_datetime(result["발생일"], errors="coerce", format="mixed")
    result["사고유형"] = result["사고유형"].astype("string").str.strip()
    if result["발생일"].isna().any() or result["사고유형"].isna().any() or result["사고유형"].eq("").any():
        raise ValueError("빈 값이나 잘못된 날짜·사고유형이 있습니다. 원본 행을 확인하세요.")
    if result["사고유형"].str.len().gt(200).any():
        raise ValueError("사고유형은 200자 이내로 입력하세요.")
    return result


def summarize_records(frame: pd.DataFrame) -> RecordPattern:
    if frame.empty or "발생일" not in frame or "사고유형" not in frame:
        raise ValueError("발생일과 사고유형이 포함된 사고 기록이 필요합니다.")
    dates = pd.to_datetime(frame["발생일"], errors="coerce")
    if dates.isna().any():
        raise ValueError("사고 기록의 발생일을 확인하세요.")
    weekdays = dates.dt.weekday.value_counts().reindex(range(7), fill_value=0)
    months = dates.dt.month.value_counts().reindex(range(1, 13), fill_value=0)
    seasons = tuple(
        int(dates.dt.month.map(season_index).eq(index).sum())
        for index in range(4)
    )
    types = frame["사고유형"].astype(str).value_counts().head(6)
    return RecordPattern(
        total=len(frame), first_day=dates.min().date(), last_day=dates.max().date(),
        weekdays=tuple(int(value) for value in weekdays),
        months=tuple(int(value) for value in months),
        accident_types=tuple((str(name), int(value)) for name, value in types.items()),
        seasons=seasons,
    )
