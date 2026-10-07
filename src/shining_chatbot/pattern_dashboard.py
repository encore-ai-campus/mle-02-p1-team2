"""Historical record patterns from a manager-provided CSV."""

from __future__ import annotations

import csv
from datetime import date
from hashlib import sha256
from html import escape
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from shining_chatbot.business_time import today_korea
from shining_chatbot.csv_safety import safe_spreadsheet_cell as _csv_cell
from shining_chatbot.chat_data import markdown_label
from shining_chatbot.field_dashboard import _styles
from shining_chatbot.record_pattern import (
    MAX_PATTERN_CSV_BYTES,
    SEASONS,
    RecordPattern,
    context_signals,
    read_pattern_csv,
    season_index,
    summarize_records,
)


_DAYS = ("월", "화", "수", "목", "금", "토", "일")
_SAMPLE_CSV = Path(__file__).parent / "static" / "sample_incident_pattern.csv"


def _clear_incident_data(upload_version: int) -> None:
    for key in (
        "field_incident_frame", "field_incident_name", "field_incident_scope",
        "field_incident_token", "field_incident_scope_input", "field_pattern_range", "field_pattern_type_filter",
        "field_pattern_day",
    ):
        st.session_state.pop(key, None)
    st.session_state["field_incident_upload_version"] = upload_version + 1


def _pattern_styles() -> None:
    st.markdown("""<style>
.pattern-layout{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:17px}.pattern-card{min-width:0;border:1px solid #DFE7DE;background:#fff;border-radius:8px;padding:19px 20px 16px}
.pattern-section{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin:27px 0 9px}.pattern-section h2{margin:0;color:#29392E;font-size:14px;font-weight:620}.pattern-section span{color:#68776D;font-size:10px}
.pattern-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px}.pattern-head strong{font-size:13px;color:#29392E;font-weight:620}.pattern-head span{font-size:10px;color:#68776D}
.pattern-weekdays{margin-top:20px}.pattern-day{display:grid;grid-template-columns:18px 1fr 32px;align-items:center;gap:12px;margin:11px 0;font-size:11px;color:#677A6C;outline:0}
.pattern-day span:last-child{text-align:right;color:#395442;font-weight:560}.pattern-track{height:9px;border-radius:3px;background:#EEF2EC;overflow:hidden}.pattern-fill{height:100%;background:linear-gradient(90deg,#BED7C1,#5E8D68);border-radius:0 3px 3px 0;transition:filter .2s,transform .2s}
.pattern-day:hover .pattern-fill,.pattern-day:focus-visible .pattern-fill,.pattern-day:focus .pattern-fill{filter:saturate(1.4);transform:scaleY(1.3)}.pattern-day:focus-visible,.pattern-day:focus{outline:2px solid #7BA984;outline-offset:3px;border-radius:3px}
.pattern-months{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:7px;align-items:end;height:150px;margin-top:29px;border-bottom:1px solid #DCE7DB}
.pattern-month{height:100%;display:flex;flex-direction:column;justify-content:end;align-items:center;position:relative;outline:0}.pattern-month .bar{width:100%;height:var(--height);min-height:2px;background:linear-gradient(180deg,#739F7B,#D0E2D0);border-radius:3px 3px 0 0;transition:filter .2s,transform .2s;transform-origin:bottom}.pattern-month:hover .bar,.pattern-month:focus-visible .bar,.pattern-month:focus .bar{filter:saturate(1.4) brightness(.9);transform:scaleX(1.08)}
.pattern-month:focus-visible,.pattern-month:focus{outline:2px solid #7BA984;outline-offset:2px}.pattern-month em{position:absolute;bottom:calc(var(--height) + 7px);font-style:normal;color:#45664D;font-size:10px;opacity:0;transition:opacity .15s}.pattern-month:hover em,.pattern-month:focus-visible em,.pattern-month:focus em{opacity:1}
.pattern-month-labels{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:7px;margin-top:7px;color:#657368;font-size:10px;text-align:center}
.pattern-seasons{margin-top:14px;border:1px solid #DFE7DE;background:#fff;border-radius:8px;padding:15px 18px 13px}.pattern-season-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:13px}
.pattern-season{border:1px solid #E8EDE7;border-radius:6px;padding:10px 11px;outline:0;transition:border-color .18s,background .18s}.pattern-season:hover,.pattern-season:focus-visible,.pattern-season:focus{border-color:#AFC5B1;background:#F8FAF7}.pattern-season:focus-visible,.pattern-season:focus{box-shadow:0 0 0 2px #DCE9DC}
.pattern-season-head{display:flex;justify-content:space-between;gap:8px;align-items:baseline;color:#627467;font-size:10px}.pattern-season-head strong{font-size:15px;line-height:1.2;color:#334D39;font-weight:620}.pattern-season-track{height:4px;margin-top:9px;border-radius:3px;background:#EEF2EC;overflow:hidden}.pattern-season-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#C8DCC8,#789B7B);transition:filter .18s,transform .18s;transform-origin:left}.pattern-season:hover .pattern-season-fill,.pattern-season:focus-visible .pattern-season-fill,.pattern-season:focus .pattern-season-fill{filter:saturate(1.35);transform:scaleY(1.5)}
.pattern-foot{font-size:10px;color:#68776D;line-height:1.6;margin-top:14px}.pattern-focus{background:#F4F8F3;border:1px solid #E2EBE0;border-radius:8px;padding:16px 18px;margin-top:20px;color:#4A6551;font-size:12px;line-height:1.65}.pattern-focus strong{font-weight:650;color:#2A4933}
@media(max-width:850px){.pattern-layout{grid-template-columns:1fr}}@media(max-width:520px){.pattern-card{padding:15px}.pattern-months,.pattern-month-labels{gap:3px}.pattern-seasons{padding:13px}.pattern-season-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.st-key-pattern_filters [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important}.st-key-pattern_filters [data-testid="stColumn"]{flex:1 1 100% !important;width:100% !important}}
@media(prefers-reduced-motion:reduce){.pattern-fill,.pattern-month .bar,.pattern-month em,.pattern-season,.pattern-season-fill{transition:none !important}.pattern-day:hover .pattern-fill,.pattern-day:focus-visible .pattern-fill,.pattern-day:focus .pattern-fill,.pattern-month:hover .bar,.pattern-month:focus-visible .bar,.pattern-month:focus .bar,.pattern-season:hover .pattern-season-fill,.pattern-season:focus-visible .pattern-season-fill,.pattern-season:focus .pattern-season-fill{transform:none !important;filter:none !important}}
</style>""", unsafe_allow_html=True)


def _charts(pattern: RecordPattern) -> None:
    day_max = max(pattern.weekdays) or 1
    month_max = max(pattern.months) or 1
    season_max = max(pattern.seasons, default=0) or 1
    weekday_rows = "".join(
        f'<div class="pattern-day" tabindex="0" role="img" aria-label="{_DAYS[index]}요일 {count}건">'
        f'<span>{_DAYS[index]}</span><div class="pattern-track"><div class="pattern-fill" style="width:{count / day_max * 100:.1f}%"></div></div>'
        f'<span>{count}</span></div>'
        for index, count in enumerate(pattern.weekdays)
    )
    months = "".join(
        f'<div class="pattern-month" tabindex="0" role="img" aria-label="{index}월 {count}건" style="--height:{count / month_max * 100:.1f}%">'
        f'<em>{count}</em><div class="bar"></div></div>'
        for index, count in enumerate(pattern.months, 1)
    )
    labels = "".join(f'<span>{index}</span>' for index in range(1, 13))
    season_cards = "".join(
        f'<div class="pattern-season" tabindex="0" role="img" aria-label="{SEASONS[index]}: {count}건">'
        f'<div class="pattern-season-head"><span>{SEASONS[index]} · 달력 기준</span><strong>{count:,}</strong></div>'
        f'<div class="pattern-season-track"><div class="pattern-season-fill" style="width:{count / season_max * 100:.1f}%"></div></div></div>'
        for index, count in enumerate(pattern.seasons)
    )
    st.markdown(
        '<div class="pattern-layout"><div class="pattern-card"><div class="pattern-head"><strong>요일별 발생 기록</strong><span>MON — SUN</span></div>'
        f'<div class="pattern-weekdays">{weekday_rows}</div><div class="pattern-foot">각 요일의 기록 건수 · 근무 인원·작업시간을 보정하지 않은 값</div></div>'
        '<div class="pattern-card"><div class="pattern-head"><strong>월별 발생 기록</strong><span>JAN — DEC</span></div>'
        f'<div class="pattern-months">{months}</div><div class="pattern-month-labels">{labels}</div>'
        '<div class="pattern-foot">연도별 같은 달을 합산 · 수집 기간이 짧으면 월별 비교에 주의</div></div></div>'
        '<div class="pattern-seasons"><div class="pattern-head"><strong>계절별 발생 기록</strong><span>CALENDAR SEASON</span></div>'
        f'<div class="pattern-season-grid">{season_cards}</div>'
        '<div class="pattern-foot">봄 3–5월 · 여름 6–8월 · 가을 9–11월 · 겨울 12–2월 · 실제 기상 상태나 사고 위험률이 아닌 날짜 집계</div></div>',
        unsafe_allow_html=True,
    )


def _summary_csv(
    pattern: RecordPattern, scope: str, type_filter: str,
    period_start: date, period_end: date,
) -> bytes:
    """Export only the aggregates visible in the record-pattern dashboard."""
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("구분", "항목", "기록 건수", "기록 범위", "유형 검색", "분석 시작일", "분석 종료일"))
    rows = [
        ("전체", "등록 기록", pattern.total),
        *(("요일", f"{_DAYS[index]}요일", count) for index, count in enumerate(pattern.weekdays)),
        *(("월", f"{index}월", count) for index, count in enumerate(pattern.months, 1)),
        *(("계절", SEASONS[index], count) for index, count in enumerate(pattern.seasons)),
        *(("사고유형 상위 6", name, count) for name, count in pattern.accident_types),
    ]
    writer.writerows(
        tuple(_csv_cell(value) if isinstance(value, str) else value for value in (
            *row, scope or "범위 미입력", type_filter or "전체",
            period_start.isoformat(), period_end.isoformat(),
        ))
        for row in rows
    )
    return output.getvalue().encode("utf-8-sig")


def show_pattern_dashboard() -> None:
    _styles()
    _pattern_styles()
    st.markdown(
        '<div class="field-hero"><div><div class="field-kicker">SAFETY ATLAS / SITE RECORDS</div>'
        '<h1>사고 기록 경향</h1><p class="field-hero-site">현장 기록의 요일·월·계절 분포</p>'
        '<p>관리자가 가진 사고 기록을 연결해 반복되는 날짜 패턴을 확인하세요.</p></div>'
        f'<span class="field-date"><small>오늘 기준</small>{today_korea():%Y.%m.%d}</span></div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown('<div class="field-panel-title">현장 사고 CSV 연결</div>', unsafe_allow_html=True)
        max_mb = MAX_PATTERN_CSV_BYTES // (1024 * 1024)
        st.caption(f"발생일·사고유형 두 열이면 됩니다. 최대 {max_mb}MB의 실제 현장 또는 관리 범위 기록만 올리세요. 날짜가 없는 SANUP-P 사례 자료로 요일·월·계절 경향을 추정하지 않습니다.")
        st.caption("화면을 먼저 살펴보려면 아래 가상 시연용 파일을 올리고 기록 범위에 ‘가상 시연용(실제 현장자료 아님)’이라고 적으세요.")
        st.caption("현장 사고 CSV는 현재 브라우저 세션에서만 분석합니다. 서버를 다시 시작하면 다시 연결해야 하며 SQLite 자동 저장·JSON 백업에는 포함되지 않습니다.")
        upload_version = st.session_state.get("field_incident_upload_version", 0)
        file = st.file_uploader(
            "사고 기록 CSV", type="csv", key=f"field_incident_upload_{upload_version}",
            max_upload_size=max_mb,
        )
        scope = st.text_input("기록 범위", placeholder="예: 온누리 현장 2024–2026", max_chars=200, key="field_incident_scope_input")
        frame: pd.DataFrame | None = st.session_state.get("field_incident_frame")
        token = sha256(file.getvalue()).hexdigest() if file is not None else None
        current_scope = st.session_state.get("field_incident_scope", "")
        if frame is not None:
            st.caption(
                f"현재 그래프 기준: {markdown_label(current_scope or '범위 미입력')} · "
                f"{markdown_label(st.session_state.get('field_incident_name', '사고 CSV'))}"
            )
        pending_upload = file is not None and (
            token != st.session_state.get("field_incident_token") or scope.strip() != current_scope
        )
        if pending_upload and frame is not None:
            st.info("새 CSV 또는 기록 범위가 선택됐지만 아직 적용되지 않았습니다. 아래 그래프는 현재 기준 자료를 유지합니다.")
        if file is not None:
            content = file.getvalue()
            if len(content) > MAX_PATTERN_CSV_BYTES:
                st.error(f"CSV 파일은 {MAX_PATTERN_CSV_BYTES // (1024 * 1024)}MB 이하여야 합니다.")
            elif st.button("이 기록으로 분석", type="primary", key="field_incident_apply"):
                if not scope.strip():
                    st.error("현장명 또는 기록 범위를 입력하세요.")
                else:
                    try:
                        frame = read_pattern_csv(content)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["field_incident_frame"] = frame
                        st.session_state["field_incident_name"] = file.name
                        st.session_state["field_incident_scope"] = scope.strip()
                        st.session_state["field_incident_token"] = token
                        st.session_state.pop("field_pattern_range", None)
                        st.session_state.pop("field_pattern_type_filter", None)
                        st.rerun()
        sample_col, template_col = st.columns(2, gap="small")
        with sample_col:
            st.download_button(
                "가상 시연용 CSV 받기", data=_SAMPLE_CSV.read_bytes(),
                file_name="사고기록_경향_가상시연용.csv", mime="text/csv",
                help="실제 사고자료가 아닌 2023–2025년 가상 기록 240건입니다.",
            )
        with template_col:
            st.download_button("CSV 열 형식 받기", data="발생일,사고유형\n".encode("utf-8-sig"), file_name="사고기록_열형식.csv", mime="text/csv")
        st.download_button(
            "상세 사고 사례 CSV 받기 · 24건",
            data=(_SAMPLE_CSV.parent / "sample_incident_pattern_detailed.csv").read_bytes(),
            file_name="가상_건설현장_상세_사고기록_24건.csv",
            mime="text/csv",
            help="사고 개요, 원인, 즉시 조치, 재발방지대책을 포함한 가상 시연 데이터입니다. 실제 사고 사례가 아닙니다.",
        )
        st.caption("상세 파일의 모든 사고 사례는 기능 시연용으로 만든 가상 데이터이며, 실제 사고 통계나 안전 판단 근거로 사용하지 마세요.")
    frame: pd.DataFrame | None = st.session_state.get("field_incident_frame")
    if frame is None:
        st.markdown('<div class="field-panel"><div class="field-panel-title">기록을 올리면 분포가 나타납니다</div><p class="field-sub">샘플로 만든 숫자를 현장 경향으로 표시하지 않습니다.</p></div>', unsafe_allow_html=True)
        return
    data_start = frame["발생일"].min().date()
    data_end = frame["발생일"].max().date()
    with st.container(key="pattern_filters"):
        range_col, type_col = st.columns([1.15, 1], gap="small")
        with range_col:
            period_value = st.date_input(
                "분석 기간", value=(data_start, data_end), min_value=data_start, max_value=data_end,
                key="field_pattern_range",
            )
        with type_col:
            type_filter = st.text_input(
                "사고유형 좁혀 보기",
                placeholder="예: 떨어짐 · 입력한 글자를 포함한 유형만 집계",
                max_chars=100,
                key="field_pattern_type_filter",
            ).strip()
    if (
        isinstance(period_value, (tuple, list)) and len(period_value) == 2
        and all(isinstance(value, date) for value in period_value)
    ):
        period_start, period_end = period_value
        period_mask = frame["발생일"].dt.date.between(period_start, period_end)
        filtered_frame = frame.loc[period_mask]
    else:
        period_start, period_end = data_start, data_end
        filtered_frame = frame
        st.caption("종료 날짜를 선택하면 기간 범위를 적용합니다.")
    if filtered_frame.empty:
        st.info("선택한 기간에 사고 기록이 없습니다. 날짜 범위를 조정하세요.")
        return
    if type_filter:
        filtered_frame = filtered_frame.loc[
            filtered_frame["사고유형"].astype(str).str.contains(type_filter, case=False, regex=False)
        ]
        if filtered_frame.empty:
            st.info(f"‘{markdown_label(type_filter)}’를 포함한 사고유형이 없습니다. 검색어를 줄이거나 지우면 전체 기록을 다시 볼 수 있습니다.")
            return
        st.caption(
            f"유형 필터 적용 · {len(filtered_frame):,}/{len(frame):,}건 · "
            f"{filtered_frame['사고유형'].nunique():,}개 유형"
        )
    pattern = summarize_records(filtered_frame)
    st.info(
        f"{period_start:%Y.%m.%d}–{period_end:%Y.%m.%d}에 등록된 기록 "
        f"{pattern.total:,}건의 분포입니다. 기록 범위: {markdown_label(st.session_state.get('field_incident_scope', '범위 미입력'))}. "
        "작업일수·근로자 수가 없어 사고율이나 발생 확률을 뜻하지 않고, "
        "날씨나 계절의 인과관계도 나타내지 않습니다."
    )
    st.markdown(
        '<div class="field-metrics action-metrics">'
        f'<div class="field-metric"><span>등록 기록</span><strong>{pattern.total:,}</strong><small>건</small></div>'
        f'<div class="field-metric"><span>시작</span><strong style="font-size:17px">{pattern.first_day:%Y.%m}</strong><small>월</small></div>'
        f'<div class="field-metric"><span>마지막</span><strong style="font-size:17px">{pattern.last_day:%Y.%m}</strong><small>월</small></div>'
        f'<div class="field-metric"><span>수집 범위</span><strong style="font-size:14px;line-height:1.3">{escape(st.session_state.get("field_incident_scope", "범위 미입력"))}</strong></div>'
        '</div>', unsafe_allow_html=True,
    )
    _charts(pattern)
    plan = st.session_state.get("field_plan")
    plan_days = sorted({item.day for item in plan.items}) if plan else []
    field_day = st.session_state.get("field_day")
    default_day = field_day if isinstance(field_day, date) else today_korea()
    context_days = sorted(set(plan_days) | {default_day})
    if st.session_state.get("field_pattern_day") not in context_days:
        st.session_state["field_pattern_day"] = default_day
    context_day = st.selectbox(
        "작업일에 적용해 보기", context_days,
        format_func=lambda day: f"{day:%Y.%m.%d} ({_DAYS[day.weekday()]})",
        key="field_pattern_day",
    )
    count = pattern.weekdays[context_day.weekday()]
    month_count = pattern.months[context_day.month - 1]
    season_name = SEASONS[season_index(context_day.month)]
    season_count = pattern.seasons[season_index(context_day.month)]
    st.markdown(
        '<div class="pattern-focus"><strong>'
        f'{context_day:%Y.%m.%d} {_DAYS[context_day.weekday()]}요일</strong>과 같은 요일의 기록은 '
        f'{count}건, {context_day.month}월 기록은 {month_count}건, 달력상 {season_name} 기록은 {season_count}건입니다. '
        '날짜 기준 집계이며 해당 작업일의 사고 확률이나 실제 날씨 영향을 뜻하지 않습니다.</div>',
        unsafe_allow_html=True,
    )
    for signal in context_signals(pattern, context_day):
        st.markdown(f'<div class="field-note">기록 검토 · {escape(signal)} 사고 확률을 뜻하지 않습니다.</div>', unsafe_allow_html=True)
    if pattern.accident_types:
        st.markdown('<div class="pattern-section"><h2>기록에 많이 나온 사고유형</h2><span>TOP TYPES</span></div>', unsafe_allow_html=True)
        st.markdown(" · ".join(f"{escape(name)} {count}건" for name, count in pattern.accident_types), unsafe_allow_html=True)
    st.caption(f"자료: {markdown_label(st.session_state.get('field_incident_name', '사고 CSV'))} · {pattern.first_day:%Y.%m.%d}–{pattern.last_day:%Y.%m.%d} · 사고 건수만 집계합니다. 작업일수·근로자 수·기상 관측값이 없어 발생률이나 날씨별 사고 위험을 계산하지 않습니다.")
    st.caption("집계표에는 원본 사고 행이 포함되지 않습니다.")
    export_col, clear_col = st.columns([1, 1], gap="small")
    with export_col:
        st.download_button(
            "집계표 CSV 다운로드",
            data=_summary_csv(
                pattern, st.session_state.get("field_incident_scope", ""), type_filter,
                period_start, period_end,
            ),
            file_name=f"사고기록_집계_{today_korea():%Y%m%d}.csv", mime="text/csv",
            key="field_incident_summary_download",
        )
    with clear_col:
        st.button(
            "연결한 사고 기록 해제", key="field_incident_clear",
            on_click=_clear_incident_data, args=(upload_version,),
        )
