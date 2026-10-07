"""Answer regional, monthly and seasonal questions from the current accident CSV."""

from __future__ import annotations

from datetime import date
import re
from uuid import uuid4

import pandas as pd

from shining_chatbot.record_pattern import SEASONS, season_index


REGION_ALIASES = {
    "서울": ("서울특별시", "서울시", "서울"),
    "부산": ("부산광역시", "부산시", "부산"),
    "대구": ("대구광역시", "대구시", "대구"),
    "인천": ("인천광역시", "인천시", "인천"),
    "광주": ("광주광역시", "광주시", "광주"),
    "대전": ("대전광역시", "대전시", "대전"),
    "울산": ("울산광역시", "울산시", "울산"),
    "세종": ("세종특별자치시", "세종시", "세종"),
    "경기": ("경기도", "경기"),
    "강원": ("강원특별자치도", "강원도", "강원"),
    "충북": ("충청북도", "충북"),
    "충남": ("충청남도", "충남"),
    "전북": ("전북특별자치도", "전라북도", "전북"),
    "전남": ("전라남도", "전남"),
    "경북": ("경상북도", "경북"),
    "경남": ("경상남도", "경남"),
    "제주": ("제주특별자치도", "제주도", "제주"),
}


def markdown_label(value: object) -> str:
    """Keep uploaded labels and categories from becoming active Markdown."""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return re.sub(r"([\\`*_{}\[\]()#+:!|<>~])", r"\\\1", text)


def _region_in(text: str, frame: pd.DataFrame) -> str | None:
    for region, aliases in REGION_ALIASES.items():
        if any(alias in text for alias in aliases):
            return region
    if "지역" not in frame.columns:
        return None
    for value in sorted(frame["지역"].dropna().astype(str).unique(), key=len, reverse=True):
        if value in text:
            return value
    return None


def _matching_rows(frame: pd.DataFrame, region: str | None) -> pd.DataFrame:
    if region is None:
        return frame
    if "지역" not in frame.columns:
        return frame.iloc[0:0]
    aliases = REGION_ALIASES.get(region, (region,))
    values = frame["지역"].astype(str)
    return frame.loc[values.map(lambda value: any(alias in value or value in alias for alias in aliases))]


def answer_data_question(
    question: str,
    frame: pd.DataFrame,
    *,
    is_sample: bool,
    history: list[dict],
    source_label: str | None = None,
) -> dict | None:
    """Return a local-data response, or None for a document RAG question."""
    compact = re.sub(r"\s+", "", question).lower()
    weather_question = any(term in compact for term in (
        "날씨", "기상", "기온", "강수", "비오는날", "비가오는날", "비올때", "비오면",
        "눈오는날", "눈오면", "눈이오면", "눈올때", "우천", "폭염", "한파", "장마", "강풍", "호우",
        "더울때", "더운날", "추울때", "추운날", "폭우", "폭설", "강설",
    ))
    incident_question = any(term in compact for term in ("사고", "재해"))
    pattern_terms = (
        "통계", "건수", "몇건", "추이", "경향", "패턴", "계절별", "계절마다", "상관", "영향",
        "비교", "차이", "달라", "관계있", "따라다르", "발생률",
        "많아", "많았", "많을", "더많", "높아", "높았", "더높", "증가", "감소", "더자주",
        "날씨별", "기상별", "비오는날", "비가오는날", "비올때", "비가올때", "우천", "강우", "강수시",
        "폭우", "폭설", "강설",
        "눈오는날", "눈오면", "눈이오면", "눈올때",
        "기온별", "폭염때", "한파때",
    )
    pattern_question = any(term in compact for term in pattern_terms)
    prevention_question = any(term in compact for term in (
        "주의사항", "주의할", "조심", "예방", "안전수칙", "위험성평가", "대책", "작업전", "확인할점",
    ))
    if prevention_question:
        return None
    if weather_question and incident_question and pattern_question:
        return {
            "role": "assistant",
            "status": "data_limit",
            "content": (
                "현재 사고 CSV에는 사고 당시 날씨·기온·강수 열이 없어 날씨별 사고 건수나 상관관계를 계산할 수 없습니다. "
                "현장 위치를 연결한 오늘·내일 예보는 확인할 수 있지만, 현재 예보는 과거 사고 당시 기상 기록이 아닙니다. "
                "날씨 영향을 분석하려면 사고 시각·현장 기상 관측과 함께 작업량·노출 시간 범위도 기록해야 합니다."
            ),
        }
    season_question = (
        incident_question
        and any(term in compact for term in ("계절별", "계절마다", "봄", "여름", "가을", "겨울"))
        and pattern_question
    )
    monthly = any(term in question for term in ("월간", "월별", "매월")) and any(
        term in question for term in ("그래프", "차트", "추이", "발생", "사고", "보여", "그려")
    )
    region = _region_in(question, frame)
    context_note = ""
    if (monthly or season_question) and region is None and "전체" not in question:
        previous_region = next(
            (
                previous_region
                for message in reversed(history)
                if message.get("role") == "user"
                if (previous_region := _region_in(str(message.get("content") or ""), frame))
            ),
            None,
        )
        if previous_region and "지역" not in frame.columns:
            region = previous_region
        elif previous_region and _matching_rows(frame, previous_region).empty:
            view_name = "그래프" if monthly else "계절별 기록"
            context_note = f"직전에 물어본 {markdown_label(previous_region)} 기록은 현재 CSV에 없어 전체 지역의 {view_name}를 보여드립니다. "
        else:
            region = previous_region
    if region is not None and "지역" not in frame.columns:
        source = markdown_label(source_label or ("시연용 가상 데이터" if is_sample else "현재 연결한 현장 기록"))
        safe_region = markdown_label(region)
        return {
            "role": "assistant",
            "status": "data_limit",
            "content": (
                f"현재 **{source}**에는 지역 열이 없어 **{safe_region} 지역 사고**를 분리해 조회할 수 없습니다. "
                "이 기록 범위의 월별·계절별 건수는 확인할 수 있지만, 지역별 0건으로 해석하지 않습니다. "
                "지역 분석은 지역 정보가 포함된 사고 CSV를 연결해 주세요."
            ),
        }
    if not monthly and not season_question and region is None:
        return None

    selected = _matching_rows(frame, region)
    source_label = markdown_label(source_label or ("시연용 가상 데이터" if is_sample else "업로드한 CSV"))
    subject = f"{markdown_label(region)} 지역" if region else ("전체 지역" if "지역" in frame.columns else "연결 현장 기록")
    if selected.empty:
        next_step = (
            "이 샘플에는 실제 지역별 현황이 담겨 있지 않습니다. 왼쪽 CSV 관리에서 제주 기록이 포함된 파일을 올리면 조회할 수 있습니다."
            if is_sample else "이는 해당 지역의 실제 사고가 0건이라는 뜻이 아닙니다. 업로드한 파일의 지역 표기와 포함 범위를 확인해 주세요."
        )
        return {
            "role": "assistant",
            "status": "data_answer",
            "content": f"현재 **{source_label}**에 **{subject} 사고 기록이 없습니다.** {next_step}",
        }

    if season_question:
        seasonal_counts = selected["발생일"].dt.month.map(season_index).value_counts().reindex(range(4), fill_value=0)
        counts = " · ".join(f"{SEASONS[index]} {int(value):,}건" for index, value in seasonal_counts.items())
        return {
            "role": "assistant",
            "status": "data_answer",
            "content": (
                context_note + f"**{source_label} · {subject} 계절별 사고 기록** · "
                f"{selected['발생일'].min():%Y.%m.%d}–{selected['발생일'].max():%Y.%m.%d}\n\n"
                f"{counts}\n\n"
                "발생일의 달력상 계절로 센 건수입니다. 당시 기상 상태나 작업량·근로자 수를 보정한 사고율, "
                "계절이 사고에 미친 영향은 뜻하지 않습니다."
            ),
        }

    if monthly:
        latest = selected["발생일"].max()
        earliest = selected["발생일"].min()
        start = max(earliest.to_period("M"), latest.to_period("M") - 23).start_time.date()
        end = latest.date()
        in_period = selected.loc[selected["발생일"].dt.date.between(start, end)]
        return {
            "role": "assistant",
            "status": "data_answer",
            "content": (
                context_note + f"**{source_label} · {subject}**의 월별 사고 기록입니다. "
                f"{start:%Y.%m}–{end:%Y.%m} 기간에 **{len(in_period):,}건**이 있습니다. "
                + (
                    "그래프의 막대에 마우스를 올리면 월별 건수와 재해정도를 볼 수 있습니다."
                    if "재해정도" in in_period.columns
                    else "그래프에는 월별 건수를 표시합니다. 원본에 재해정도 열이 없어 재해정도 구성은 표시하지 않습니다."
                )
            ),
            "chart": {"region": region, "start": start.isoformat(), "end": end.isoformat(), "id": f"chat-{uuid4().hex[:8]}"},
        }

    counts = selected["사고유형"].value_counts()
    leading_type = f" 가장 많은 사고유형은 **{markdown_label(counts.index[0])} {counts.iloc[0]:,}건**입니다." if not counts.empty else ""
    earliest = selected["발생일"].min()
    latest = selected["발생일"].max()
    return {
        "role": "assistant",
        "status": "data_answer",
        "content": (
            f"**{source_label}**에서 **{subject} 사고 기록 {len(selected):,}건**을 확인했습니다. "
            f"기록 기간은 {earliest:%Y.%m.%d}–{latest:%Y.%m.%d}입니다.{leading_type} "
            "이 수치는 현재 CSV에 포함된 기록만 집계합니다."
        ),
    }


def chart_frame(frame: pd.DataFrame, chart: dict) -> tuple[pd.DataFrame, date, date]:
    selected = _matching_rows(frame, chart.get("region"))
    start, end = date.fromisoformat(chart["start"]), date.fromisoformat(chart["end"])
    return selected.loc[selected["발생일"].dt.date.between(start, end)], start, end
