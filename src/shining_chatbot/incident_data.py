"""Sample data and CSV validation for the industrial accident dashboard."""

from __future__ import annotations

from io import BytesIO
from random import Random

import pandas as pd


COLUMNS = (
    "발생일",
    "업종",
    "지역",
    "사고유형",
    "재해정도",
    "재해자수",
    "휴업일수",
)
SEVERITIES = ("경상", "중상", "사망")
MAX_CSV_BYTES = 25 * 1024 * 1024


def sample_incidents() -> pd.DataFrame:
    """Make deterministic, fictional records for an immediately usable preview."""
    rng = Random(42)
    industries = ("제조업", "건설업", "운수·창고업", "서비스업", "기타")
    regions = ("서울", "경기", "인천", "부산", "대구", "광주", "대전", "기타")
    accident_types = ("넘어짐", "떨어짐", "끼임", "부딪힘", "절단·베임", "기타")
    records = []

    for month in pd.date_range("2025-01-01", "2026-09-01", freq="MS"):
        for _ in range(rng.randint(5, 10)):
            severity = rng.choices(SEVERITIES, weights=(68, 28, 4))[0]
            records.append(
                {
                    "발생일": month + pd.Timedelta(days=rng.randint(0, 27)),
                    "업종": rng.choice(industries),
                    "지역": rng.choice(regions),
                    "사고유형": rng.choice(accident_types),
                    "재해정도": severity,
                    "재해자수": rng.choices((1, 2, 3), weights=(85, 12, 3))[0],
                    "휴업일수": (
                        rng.randint(2, 15)
                        if severity == "경상"
                        else rng.randint(16, 90)
                        if severity == "중상"
                        else 0
                    ),
                }
            )

    return pd.DataFrame.from_records(records, columns=COLUMNS)


def read_incidents_csv(content: bytes) -> pd.DataFrame:
    """Read a Korean or UTF-8 CSV and report errors that can be fixed in the file."""
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("사고 CSV는 25MB 이하여야 합니다.")
    try:
        try:
            frame = pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(BytesIO(content), encoding="cp949")
    except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError("CSV 파일을 읽을 수 없습니다. 표 형식을 확인해 주세요.") from exc

    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)}")

    frame = frame.loc[:, COLUMNS].copy()
    if frame.empty:
        raise ValueError("CSV에 사고 기록이 없습니다.")
    if len(frame) > 250_000:
        raise ValueError("분석할 사고 기록은 250,000건 이하여야 합니다.")

    frame["발생일"] = pd.to_datetime(frame["발생일"], errors="coerce", format="mixed")
    for column in ("재해자수", "휴업일수"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("업종", "지역", "사고유형", "재해정도"):
        frame[column] = frame[column].astype("string").str.strip()

    if frame.isna().any().any() or (frame[["업종", "지역", "사고유형", "재해정도"]] == "").any().any():
        raise ValueError("빈 값이나 잘못된 날짜·숫자가 있습니다. 모든 열을 확인해 주세요.")
    text_limits = {"업종": 100, "지역": 100, "사고유형": 200, "재해정도": 10}
    if any(frame[column].str.len().gt(maximum).any() for column, maximum in text_limits.items()):
        raise ValueError("업종·지역·사고유형 값이 허용 길이를 넘었습니다.")
    if not frame["재해정도"].isin(SEVERITIES).all():
        raise ValueError("재해정도는 경상, 중상, 사망 중 하나여야 합니다.")
    if (frame["재해자수"] < 1).any() or (frame["재해자수"] % 1 != 0).any():
        raise ValueError("재해자수는 1 이상의 정수여야 합니다.")
    if (frame["휴업일수"] < 0).any() or (frame["휴업일수"] % 1 != 0).any():
        raise ValueError("휴업일수는 0 이상의 정수여야 합니다.")

    frame[["재해자수", "휴업일수"]] = frame[["재해자수", "휴업일수"]].astype(int)
    return frame
