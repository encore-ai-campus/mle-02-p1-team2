"""Industrial accident operations dashboard built with Streamlit."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
from html import escape
import os
import sqlite3

import pandas as pd
import streamlit as st

from shining_chatbot.chatbot import show_chatbot
from shining_chatbot.chat_data import markdown_label
from shining_chatbot.action_dashboard import show_action_dashboard
from shining_chatbot.action_data import action_due_kst
from shining_chatbot.business_time import today_korea
from shining_chatbot.csv_safety import safe_spreadsheet_cell as _safe_csv_cell
from shining_chatbot.field_dashboard import show_field_dashboard
from shining_chatbot.field_state import export_backup, import_backup
from shining_chatbot.field_session import clear_site_context
from shining_chatbot.field_storage import FieldStateStore, StorageConflict
from shining_chatbot.tbm_dashboard import show_tbm_dashboard
from shining_chatbot.pattern_dashboard import show_pattern_dashboard
from shining_chatbot.incident_data import COLUMNS, SEVERITIES, read_incidents_csv, sample_incidents
from shining_chatbot.infographics import monthly_infographic, ranking_infographic, severity_infographic
from shining_chatbot.ui import (
    apply_styles,
    panel_heading,
    render_header,
    render_sidebar_brand,
    render_back_to_top,
    section_heading,
)


def reset_filters(earliest: date, latest: date) -> None:
    st.session_state["filter_dates"] = (earliest, latest)
    st.session_state["filter_industries"] = []
    st.session_state["filter_regions"] = []
    st.session_state["quick_severity"] = "전체"


def _storage_caption() -> str:
    state = st.session_state
    if state.get("_field_storage_enabled"):
        if state.get("_field_storage_saved"):
            return "자동 저장됨 · 이 기기의 로컬 저장소 · 민감 정보는 백업 파일과 함께 안전하게 보관하세요."
        return "로컬 자동 저장 사용 · 작업계획을 등록하면 이 기기에 저장됩니다."
    if state.get("_field_storage_error"):
        return "자동 저장을 사용할 수 없음 · 오류를 확인하고 백업 파일로 보관하세요."
    return "세션 기록 · 새로고침이나 서버 재시작 전 백업하세요."


def _render_sidebar_snapshot() -> None:
    """Keep a compact, current operational summary beside every workspace page."""
    plan = st.session_state.get("field_plan")
    if plan is None:
        st.markdown(
            '<div class="sidebar-live" role="group" aria-label="현장 운영 요약"><div class="sidebar-live-head"><span>FIELD STATUS</span>'
            '<span class="sidebar-live-state">계획 없음</span></div>'
            '<div class="sidebar-live-empty-title">현장 계획을 연결하세요</div>'
            '<p class="sidebar-live-note">작업계획을 등록하면 날짜별 작업, 확인 대기, 미완료 조치를 한곳에서 확인할 수 있습니다.</p></div>',
            unsafe_allow_html=True,
        )
        st.caption(_storage_caption())
        st.button(
            "백업 · 복원", key="sidebar_backup", icon=":material/save:",
            on_click=open_backup_panel, width="stretch",
        )
        return
    today = today_korea()
    selected = st.session_state.get("field_day")
    if not isinstance(selected, date):
        selected = today
    daily = [item for item in plan.items if item.day == selected]
    work_ids = {item.work_id for item in daily}
    reviews = st.session_state.get("field_reviews", {})
    pending = sum(reviews.get(item.work_id, {}).get("status") != "확인 완료" for item in daily)
    pending_label = str(pending) if daily else "—"
    work_days = {item.work_id: item.day for item in plan.items}
    remaining = 0
    for action in st.session_state.get("field_actions", ()):
        if action.status != "open":
            continue
        origin = action.work_day or work_days.get(action.work_id)
        due_day = action_due_kst(action).date()
        if (
            action.work_id in work_ids
            or (origin is not None and origin <= selected)
            or due_day <= selected
            or (action.needs_review and (action.work_day is None or action.work_day <= selected))
        ):
            remaining += 1
    st.markdown(
        '<div class="sidebar-live" role="group" aria-label="현장 운영 요약"><div class="sidebar-live-head"><span>FIELD STATUS</span>'
        f'<span class="sidebar-live-state">{"오늘" if selected == today else "조회"} · {selected:%m.%d}</span></div>'
        f'<div class="sidebar-live-site">{escape(plan.site)}</div><div class="sidebar-live-grid">'
        f'<div class="sidebar-live-metric"><strong>{len(daily)}</strong><span>예정 작업</span></div>'
        f'<div class="sidebar-live-metric"><strong>{pending_label}</strong><span>확인 대기</span></div>'
        f'<div class="sidebar-live-metric"><strong>{remaining}</strong><span>남은 조치</span></div>'
        '</div><div class="sidebar-live-qualifiers">'
        '<span>기준: 계획서 · 현장 기록</span>'
        '<span>일정 없음은 작업 없음 확인과 다릅니다.</span>'
        '<span>위험도 점수가 아닌 일정·확인 현황입니다.</span></div></div>',
        unsafe_allow_html=True,
    )
    st.caption(_storage_caption())
    st.button(
        "백업 · 복원", key="sidebar_backup", icon=":material/save:",
        on_click=open_backup_panel, width="stretch",
    )


def set_view(view: str) -> None:
    st.session_state["view"] = view
    st.query_params["page"] = view


def open_backup_panel() -> None:
    st.session_state["view"] = "field"
    st.session_state["field_panel_mode"] = "backup"
    st.query_params["page"] = "field"


def _sparkline(frame: pd.DataFrame, start: date, end: date, column: str | None = None) -> str:
    periods = pd.period_range(start=start, end=end, freq="M")[-12:]
    if column is None:
        values = frame.groupby(frame["발생일"].dt.to_period("M")).size()
    else:
        values = frame.groupby(frame["발생일"].dt.to_period("M"))[column].sum()
    points = values.reindex(periods, fill_value=0).tolist()
    point_periods = list(periods)
    ceiling = max(points) or 1
    popovers = []
    popover_rules = []

    def add_popover(index: int, x: float, period: pd.Period, value: int) -> None:
        unit = "명" if column is not None else "건"
        popovers.append(
            f'<span class="spark-popover spark-popover-{index}" '
            f'style="left:clamp(48px,{x / 300 * 100:.2f}%,calc(100% - 48px))">'
            f'{period.strftime("%y.%m")} · {value:,}{unit}</span>'
        )
        popover_rules.append(
            f'.spark-wrap:has([data-spark-index="{index}"]:hover) .spark-popover-{index},'
            f'.spark-wrap:has([data-spark-index="{index}"]:focus-visible) .spark-popover-{index},'
            f'.spark-wrap:has([data-spark-index="{index}"]:focus) .spark-popover-{index}'
            '{opacity:1;visibility:visible;}'
        )

    chart = [
        '<div class="spark-wrap"><svg class="sparkline" viewBox="0 0 300 50" preserveAspectRatio="none" '
        'role="img" aria-label="최근 기간의 월별 추이">'
        '<path d="M0 46H300 M0 23H300" stroke="#E9ECE9" stroke-width="1" '
        'stroke-dasharray="3 4"/>'
    ]
    if column is not None:
        step = 288 / len(points)
        for index, (period, value) in enumerate(zip(point_periods, points)):
            height = max(2, value / ceiling * 37)
            x = 6 + index * step + step * .18
            chart.append(
                f'<rect class="spark-bar" data-spark-index="{index}" '
                f'x="{x:.1f}" y="{46 - height:.1f}" '
                f'width="{step * .64:.1f}" height="{height:.1f}" rx="1.5" '
                f'fill="{["#727A73", "#ADB4AD"][index % 2]}" tabindex="0" '
                f'aria-label="{period.strftime("%Y.%m")} · {value:,}명"/>'
            )
            add_popover(index, x + step * .32, period, value)
    else:
        if len(points) == 1:
            y = 46 - points[0] * 37 / ceiling
            line_coords = [(6, y), (294, y)]
            focus_coords = [(150, y)]
        else:
            line_coords = [
                (6 + index * 288 / (len(points) - 1), 46 - value * 37 / ceiling)
                for index, value in enumerate(points)
            ]
            focus_coords = line_coords
        points_attr = " ".join(f"{x:.1f},{y:.1f}" for x, y in line_coords)
        area = f"6,46 {points_attr} 294,46"
        chart.append(
            '<defs><linearGradient id="incident-spark-fill" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#BFC5BF" stop-opacity=".55"/>'
            '<stop offset="1" stop-color="#BFC5BF" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="{area}" fill="url(#incident-spark-fill)"/>'
            f'<polyline points="{points_attr}" fill="none" stroke="#646C65" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
        for index, ((x, y), period, value) in enumerate(zip(focus_coords, point_periods, points)):
            chart.append(
                f'<g class="spark-point" data-spark-index="{index}" '
                f'tabindex="0" role="img" '
                f'aria-label="{period.strftime("%Y.%m")} 사고 {value:,}건">'
                f'<line class="spark-guide" x1="{x:.1f}" y1="5" '
                f'x2="{x:.1f}" y2="46"/>'
                f'<circle class="spark-hit" cx="{x:.1f}" cy="{y:.1f}" r="11" fill="transparent"/>'
                '</g>'
            )
            add_popover(index, x, period, value)
    chart.append('</svg>')
    chart.extend(popovers)
    chart.append('<style>' + ''.join(popover_rules) + '</style></div>')
    return "".join(chart)


def _feature_card(title: str, subtitle: str, value: int, unit: str, icon: str, graph: str) -> None:
    st.markdown(
        f'<div class="feature-card"><div class="feature-card-top"><div>'
        f'<div class="feature-card-title">{escape(title)}</div>'
        f'<div class="feature-card-sub">{escape(subtitle)}</div></div>'
        f'<div class="card-icon">{escape(icon)}</div></div>'
        f'<div class="feature-value">{value:,}</div>'
        f'<div class="feature-unit">{escape(unit)}</div>{graph}</div>',
        unsafe_allow_html=True,
    )


def _distribution_card(frame: pd.DataFrame, column: str, title: str, description: str) -> None:
    counts = frame[column].value_counts().head(9)
    top = str(counts.index[0]) if not counts.empty else "기록 없음"
    maximum = int(counts.max()) if not counts.empty else 1
    bars = "".join(
        f'<span class="distribution-bar" style="height:{max(13, int(value / maximum * 58))}px" '
        f'data-label="{escape(str(label), quote=True)}: {value:,}건" '
        f'aria-label="{escape(str(label), quote=True)}: {value:,}건" tabindex="0"></span>'
        for label, value in counts.items()
    )
    st.markdown(
        f'<div class="distribution-card"><div class="distribution-visual">{bars}</div>'
        f'<div class="distribution-content"><div class="distribution-title">{escape(title)}</div>'
        f'<div class="distribution-description">{escape(description)} · 최다 {escape(top)}</div>'
        f'<div class="distribution-meta">{len(counts)} CATEGORIES · {len(frame):,} INCIDENTS</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _quick_stat(value: int, label: str, icon: str) -> None:
    st.markdown(
        f'<div class="quick-stat"><span class="quick-icon">{escape(icon)}</span><div>'
        f'<div class="quick-num">{value:,}</div><div class="quick-label">{escape(label)}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def show_overview(filtered: pd.DataFrame, start_date: date, end_date: date) -> None:
    with st.container(key="quick_filters"):
        filter_col, period_col = st.columns([2, 1], gap="small", vertical_alignment="center")
        with filter_col:
            st.segmented_control(
                "재해정도 바로 선택",
                ["전체", *SEVERITIES],
                key="quick_severity",
                label_visibility="collapsed",
            )
        with period_col:
            st.markdown(
                f'<div class="period-chip">▣ &nbsp; {start_date:%Y.%m.%d} — {end_date:%Y.%m.%d}</div>',
                unsafe_allow_html=True,
            )
    if filtered.empty:
        st.info("선택한 조건에 맞는 기록이 없습니다. 재해정도나 왼쪽 필터를 조정해 주세요.")
        return
    with st.container(key="dashboard_main"):
        left, right = st.columns([1.72, 1], gap="small")
        with left:
            st.markdown(
                '<div class="dashboard-row-label"><h2>핵심 지표</h2><span>SELECTED PERIOD</span></div>',
                unsafe_allow_html=True,
            )
            with st.container(key="feature_grid"):
                incident_col, people_col = st.columns(2, gap="small")
                with incident_col:
                    _feature_card(
                        "사고 건수", "INCIDENT RECORDS", len(filtered), "선택 기간 발생 기록", "◇",
                        _sparkline(filtered, start_date, end_date),
                    )
                with people_col:
                    _feature_card(
                        "재해자 수", "AFFECTED PEOPLE", int(filtered["재해자수"].sum()),
                        "기록상 재해자 합계", "♧", _sparkline(filtered, start_date, end_date, "재해자수"),
                    )
            st.markdown(
                '<div class="dashboard-row-label"><h2>사고 분포</h2><span>BY CATEGORY</span></div>',
                unsafe_allow_html=True,
            )
            with st.container(key="distribution_grid"):
                for col, field, title, description in zip(
                    st.columns(3, gap="small"),
                    ("업종", "사고유형", "지역"),
                    ("업종별 기록", "유형별 기록", "지역별 기록"),
                    ("업종별 발생 건수", "사고유형별 건수", "지역별 발생 건수"),
                ):
                    with col:
                        _distribution_card(filtered, field, title, description)
        with right:
            st.markdown(
                '<div class="dashboard-row-label"><h2>재해정도</h2><span>INCIDENT MIX</span></div>',
                unsafe_allow_html=True,
            )
            icons = {"경상": "♧", "중상": "◇", "사망": "✳"}
            severity_rows = "".join(
                f'<div class="pillar-row"><span class="pillar-icon">{icons[severity]}</span><div>'
                f'<div class="pillar-name">{severity}</div>'
                f'<div class="pillar-sub">전체 {len(filtered):,}건 중 {len(filtered.loc[filtered["재해정도"] == severity]) / len(filtered):.0%}</div>'
                f'</div><span class="pillar-count">{len(filtered.loc[filtered["재해정도"] == severity]):,}건</span></div>'
                for severity in SEVERITIES
            )
            st.markdown(f'<div class="pillar-panel">{severity_rows}</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="dashboard-row-label"><h2>빠른 통계</h2><span>AT A GLANCE</span></div>',
                unsafe_allow_html=True,
            )
            with st.container(key="quick_grid"):
                for col, value, label, icon in zip(
                    st.columns(2, gap="small"),
                    (int(filtered.loc[filtered["재해정도"] == "사망", "재해자수"].sum()),
                     int(filtered["휴업일수"].sum())),
                    ("사망자 수", "휴업일수 합계"),
                    ("◉", "▤"),
                ):
                    with col:
                        _quick_stat(value, label, icon)
                for col, value, label, icon in zip(
                    st.columns(2, gap="small"),
                    (filtered["업종"].nunique(), filtered["지역"].nunique()),
                    ("분석 업종", "분석 지역"),
                    ("⌘", "▥"),
                ):
                    with col:
                        _quick_stat(value, label, icon)

    section_heading("01", "상세 분석", "필터 결과의 기간별 추이와 분포")
    trend_col, severity_col = st.columns([1.7, 1], gap="small")
    with trend_col:
        st.markdown(monthly_infographic(filtered, start_date, end_date), unsafe_allow_html=True)
    with severity_col:
        st.markdown(severity_infographic(filtered), unsafe_allow_html=True)

    section_heading("02", "항목별 상세", "업종·사고유형·지역별 건수")
    for col, field, title, index in zip(
        st.columns(3, gap="small"),
        ("업종", "사고유형", "지역"),
        ("업종별 사고", "사고유형별 사고", "지역별 사고"),
        ("03", "04", "05"),
    ):
        with col:
            st.markdown(ranking_infographic(filtered, field, title, index), unsafe_allow_html=True)
    st.markdown(
        '<div class="interpret-note">업종·지역별 수치는 사고 기록 건수입니다. '
        '근로자 수나 작업시간을 반영한 위험도 비교로 해석하지 마세요.</div>',
        unsafe_allow_html=True,
    )

def show_records(filtered: pd.DataFrame) -> None:
    st.segmented_control(
        "재해정도", ["전체", *SEVERITIES], key="quick_severity", label_visibility="collapsed"
    )
    section_heading("01", "검색 및 내보내기", "현재 필터에서 검색하고 결과를 내려받기")
    query = st.text_input(
        "기록 검색",
        placeholder="발생일, 업종, 지역, 사고유형, 재해정도로 검색",
        key="record_search",
    ).strip()
    display = filtered.sort_values("발생일", ascending=False).loc[:, COLUMNS].copy()
    if query and not display.empty:
        searchable = display[["업종", "지역", "사고유형", "재해정도"]].astype(str).agg(" ".join, axis=1)
        searchable = searchable + " " + display["발생일"].dt.strftime("%Y-%m-%d")
        display = display.loc[searchable.str.contains(query, case=False, regex=False)]

    with st.container(border=True):
        panel_heading("SOURCE RECORDS", "사고 목록", f"검색 결과 {len(display):,}건", "검색 결과 CSV")
        if display.empty:
            st.info("검색 결과가 없습니다. 검색어를 지우거나 왼쪽 필터를 조정해 주세요.")
            return
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            height=470,
            column_config={
                "발생일": st.column_config.DateColumn("발생일", format="YYYY-MM-DD"),
                "재해자수": st.column_config.NumberColumn("재해자 수", format="%d명"),
                "휴업일수": st.column_config.NumberColumn("휴업일수", format="%d일"),
            },
        )
        export_frame = display.copy()
        for column in export_frame.columns:
            if pd.api.types.is_object_dtype(export_frame[column]) or pd.api.types.is_string_dtype(export_frame[column]):
                export_frame[column] = export_frame[column].map(_safe_csv_cell)
        st.download_button(
            "현재 검색 결과 CSV 다운로드",
            data=export_frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="산업재해_검색결과.csv",
            mime="text/csv",
        )


def show_guide(incidents: pd.DataFrame, source_name: str, is_sample: bool) -> None:
    section_heading("01", "데이터 상태", "현재 분석에 사용 중인 파일과 검증 내용")
    with st.container(border=True):
        panel_heading("DATA SOURCE", source_name, "업로드한 파일 전체 기준", "시연용" if is_sample else "검증 완료")
        earliest = incidents["발생일"].min()
        latest = incidents["발생일"].max()
        st.markdown(
            f"**{len(incidents):,}건** · {earliest:%Y.%m.%d}–{latest:%Y.%m.%d} · "
            f"업종 {incidents['업종'].nunique()}개 · 지역 {incidents['지역'].nunique()}개"
        )
        if is_sample:
            st.info("이 데이터는 화면 시연을 위해 생성한 가상 기록입니다. 실제 산업재해 현황을 뜻하지 않습니다.")
        else:
            st.success("필수 열, 날짜, 빈 값, 재해정도, 인원 수와 휴업일수 형식을 확인했습니다.")

    section_heading("02", "집계와 해석 기준", "수치의 의미를 확인한 뒤 활용해 주세요")
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(border=True):
            panel_heading("METRIC DEFINITIONS", "지표 계산 방식", "표와 차트는 동일한 필터를 사용", "기록 기준")
            st.markdown(
                "- **사고 건수:** CSV의 행 수\n"
                "- **재해자 수:** `재해자수` 합계\n"
                "- **사망자 수:** `재해정도=사망` 기록의 `재해자수` 합계\n"
                "- **휴업일수 합계:** 입력된 `휴업일수` 합계"
            )
    with right:
        with st.container(border=True):
            panel_heading("INTERPRETATION", "해석 시 주의", "관측 범위와 자료의 한계", "안내")
            st.markdown(
                "- 근로자 수·작업시간 정보가 없어 **재해율이나 업종별 위험도**를 계산하지 않습니다.\n"
                "- 같은 내용의 행도 별도 사고일 수 있어 자동으로 합치지 않습니다.\n"
                "- 파일의 완전성·실제 사건 여부는 형식 검사만으로 확인할 수 없습니다."
            )

    section_heading("03", "CSV 업로드 형식", "샘플 파일은 왼쪽 메뉴에서 내려받을 수 있습니다")
    with st.container(border=True):
        panel_heading("FILE FORMAT", "필수 열과 입력 규칙", "UTF-8 또는 CP949 인코딩 CSV", "7개 열")
        st.markdown(
            "`발생일`, `업종`, `지역`, `사고유형`, `재해정도`, `재해자수`, `휴업일수`가 필요합니다. "
            "재해정도는 `경상`·`중상`·`사망` 중 하나, 재해자수는 1 이상의 정수, "
            "휴업일수는 0 이상의 정수로 입력해 주세요."
        )


_PERSISTED_FIELD_KEYS = (
    "field_plan", "field_reviews", "field_actions", "field_tbm_records",
    "field_tbm_deliveries", "field_revisions", "field_weather_location",
    "field_plan_name", "field_plan_applied_at",
)


def _apply_persisted_snapshot(state, payload: bytes | None, revision: int) -> None:
    if payload is not None:
        plan, reviews, actions, records, deliveries, revisions, weather, name, applied_at = import_backup(payload)
        state["field_plan"] = plan
        state["field_reviews"] = reviews
        state["field_actions"] = actions
        state["field_tbm_records"] = records
        state["field_tbm_deliveries"] = deliveries
        state["field_revisions"] = revisions
        state["field_weather_location"] = weather
        state["field_plan_name"] = name
        state["field_plan_applied_at"] = applied_at
    state["_field_storage_revision"] = revision
    state["_field_storage_conflict"] = False
    state["_field_storage_error"] = ""
    state["_field_storage_saved"] = payload is not None


def _field_snapshot(state) -> bytes | None:
    plan = state.get("field_plan")
    if plan is None:
        return None
    return export_backup(
        plan, state.get("field_reviews", {}), state.get("field_plan_name", "작업계획서"),
        state.get("field_plan_applied_at", ""), tuple(state.get("field_actions", ())),
        state.get("field_tbm_records", {}), state.get("field_weather_location"),
        state.get("field_tbm_deliveries", {}), tuple(state.get("field_revisions", ())),
    )


def _initialize_field_storage(state) -> None:
    if state.get("_field_storage_initialized") and not state.get("_field_storage_error"):
        return
    state["_field_storage_initialized"] = True
    if os.environ.get("SHINING_CHATBOT_DISABLE_PERSISTENCE") == "1":
        state["_field_storage_enabled"] = False
        return
    try:
        payload, revision = FieldStateStore().load()
        if state.get("field_plan") is None:
            _apply_persisted_snapshot(state, payload, revision)
        else:
            state["_field_storage_revision"] = revision
            state["_field_storage_conflict"] = False
            state["_field_storage_error"] = ""
            state["_field_storage_enabled"] = True
            state["_field_storage_saved"] = payload is not None
            current = _field_snapshot(state)
            if payload is not None and current != payload:
                state["_field_storage_conflict"] = True
        state["_field_storage_enabled"] = True
    except (OSError, ValueError, sqlite3.Error) as exc:
        state["_field_storage_enabled"] = False
        state["_field_storage_error"] = f"로컬 저장본을 읽지 못했습니다: {exc}"


def _persist_field_storage(state) -> None:
    if not state.get("_field_storage_enabled") or state.get("_field_storage_conflict"):
        return
    if state.get("field_plan") is None:
        return
    try:
        payload = _field_snapshot(state)
        if payload is None:
            return
        revision = FieldStateStore().save(payload, int(state.get("_field_storage_revision", 0)))
    except StorageConflict:
        state["_field_storage_conflict"] = True
        return
    except (OSError, ValueError, sqlite3.Error) as exc:
        state["_field_storage_error"] = f"자동 저장 실패: {exc}"
        return
    state["_field_storage_revision"] = revision
    state["_field_storage_saved"] = True
    state["_field_storage_error"] = ""


def _reload_latest_field_storage(state) -> None:
    clear_site_context(state)
    for key in _PERSISTED_FIELD_KEYS:
        state.pop(key, None)
    try:
        payload, revision = FieldStateStore().load()
        _apply_persisted_snapshot(state, payload, revision)
    except (OSError, ValueError, sqlite3.Error) as exc:
        state["_field_storage_error"] = f"최신 저장본을 읽지 못했습니다: {exc}"


def _render_app() -> None:
    apply_styles()
    st.markdown('<div id="page-top"></div>', unsafe_allow_html=True)
    route = st.query_params.get("page")
    if route in ("field", "actions", "tbm", "patterns", "overview", "records", "guide", "chat"):
        st.session_state["view"] = route
    if st.session_state.get("view") not in ("field", "actions", "tbm", "patterns", "overview", "records", "guide", "chat"):
        st.session_state["view"] = "chat"
    view = st.session_state["view"]
    if view == "chat":
        st.markdown(
            """<style>
            [data-testid="stSidebar"], [data-testid="stExpandSidebarButton"] { display:none !important; }
            [data-testid="stAppViewContainer"] { gap:0 !important; }
            [data-testid="stMain"] { flex:1 1 100% !important; width:100% !important; min-width:0 !important; }
            [data-testid="stMainBlockContainer"] { box-sizing:border-box; width:100% !important; max-width:1080px !important; margin-inline:auto !important; padding:48px 32px 60px !important; }
            [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"], button, input, textarea { font-family:'Pretendard Variable','Pretendard','Noto Sans KR','Malgun Gothic',sans-serif !important; }
            [data-testid="stMain"] h1 { color:#202923 !important; font-size:clamp(28px,3vw,34px) !important; font-weight:650 !important; letter-spacing:-.035em !important; line-height:1.3 !important; margin:0 0 8px !important; }
            .chat-page-subtitle { color:#46534A !important; font-size:16px !important; line-height:1.7 !important; margin:0 0 28px !important; }
            .chat-page-heading { margin:8px 0 28px !important; }
            [data-testid="stMarkdownContainer"] .chat-page-heading h2 { color:#202923 !important; font-size:34px !important; font-weight:650 !important; letter-spacing:-.035em !important; line-height:1.3 !important; margin:0 0 10px !important; }
            [data-testid="stMarkdownContainer"] .chat-page-heading p { color:#46534A !important; font-size:16px !important; line-height:1.7 !important; margin:0 !important; }
            .st-key-daily_briefing_upload h3 { color:#27332A !important; font-size:23px !important; font-weight:650 !important; letter-spacing:-.025em !important; line-height:1.4 !important; margin:0 0 21px !important; }
            [data-testid="stWidgetLabel"] p { color:#303B33 !important; font-size:16px !important; font-weight:560 !important; line-height:1.5 !important; }
            [data-testid="stCaptionContainer"] { color:#46534A !important; font-size:14.5px !important; line-height:1.65 !important; }
            [data-testid="stTextInput"] input, [data-testid="stChatInput"] textarea { color:#26312A !important; font-size:16px !important; line-height:1.6 !important; }
            [data-testid="stButton"] button, [data-testid="stChatInput"] button { font-family:'Pretendard Variable','Pretendard','Noto Sans KR','Malgun Gothic',sans-serif !important; font-size:15.5px !important; font-weight:580 !important; min-height:50px !important; border-radius:9px !important; }
            [data-testid="stChatInput"] { border-radius:12px !important; }
            @media(max-width:780px) { [data-testid="stMainBlockContainer"] { padding:34px 16px 48px !important; } [data-testid="stMain"] h1 { font-size:28px !important; } .chat-page-subtitle { font-size:15px !important; } }
            @media(max-width:780px) { [data-testid="stMarkdownContainer"] .chat-page-heading h2 { font-size:28px !important; } [data-testid="stMarkdownContainer"] .chat-page-heading p { font-size:15px !important; } .st-key-daily_briefing_upload h3 { font-size:21px !important; } [data-testid="stWidgetLabel"] p { font-size:15px !important; } }
            </style>""",
            unsafe_allow_html=True,
        )

    with st.sidebar:
        render_sidebar_brand()
        groups = (("오늘 안전 브리핑", (("chat", "작업계획 · 안전 안내", ":material/forum:"),)),)
        for heading, pages in groups:
            st.markdown(f'<div class="sidebar-section">{heading}</div>', unsafe_allow_html=True)
            with st.container(gap=4):
                for page, label, icon in pages:
                    st.button(
                        label,
                        key=f"nav_{page}",
                        icon=icon,
                        type="tertiary",
                        width="stretch",
                        on_click=set_view,
                        args=(page,),
                        help="현재 화면" if view == page else None,
                    )
        if view != "chat":
            _render_sidebar_snapshot()
        st.markdown(
            f'<style>[data-testid="stSidebar"] .st-key-nav_{view} button, '
            f'[data-testid="stSidebar"] .st-key-nav_{view} button:hover '
            '{ background: #252B26 !important; color: #FFFFFF !important; '
            'border: 1px solid #252B26 !important; }</style>',
            unsafe_allow_html=True,
        )
    if view == "field":
        with st.sidebar:
            st.markdown('<div class="sidebar-section">FIELD PLAN</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-help">작업계획서에서 오늘 작업과 시작 전 확인할 항목을 가져옵니다.</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-foot">SAFETY ATLAS &nbsp; / &nbsp; FIELD OPERATIONS</div>', unsafe_allow_html=True)
        show_field_dashboard()
        render_back_to_top()
        return
    if view == "actions":
        with st.sidebar:
            st.markdown('<div class="sidebar-section">FIELD ACTIONS</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-help">담당자와 기한별 조치, 변경 기록을 확인합니다.</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-foot">SAFETY ATLAS &nbsp; / &nbsp; FIELD OPERATIONS</div>', unsafe_allow_html=True)
        show_action_dashboard()
        render_back_to_top()
        return
    if view == "tbm":
        with st.sidebar:
            st.markdown('<div class="sidebar-section">FIELD BRIEFING</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-help">작업 확인과 남은 조치를 묶어 작업자 공유용 브리핑을 만듭니다.</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-foot">SAFETY ATLAS &nbsp; / &nbsp; FIELD OPERATIONS</div>', unsafe_allow_html=True)
        show_tbm_dashboard()
        render_back_to_top()
        return
    if view == "patterns":
        with st.sidebar:
            st.markdown('<div class="sidebar-section">SITE RECORDS</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-help">관리 범위의 실제 사고 CSV를 연결해 날짜별 기록 건수를 봅니다.</div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-foot">SAFETY ATLAS &nbsp; / &nbsp; FIELD OPERATIONS</div>', unsafe_allow_html=True)
        show_pattern_dashboard()
        render_back_to_top()
        return
    uploaded_file = None
    if view != "chat":
        with st.sidebar:
            st.markdown('<div class="sidebar-section">사고 통계 자료</div>', unsafe_allow_html=True)
            with st.expander("CSV 관리"):
                uploaded_file = st.file_uploader("사고 기록 CSV", type="csv", max_upload_size=25)
                st.download_button(
                    "CSV 형식 샘플 받기",
                    data=sample_incidents().to_csv(index=False).encode("utf-8-sig"),
                    file_name="산업재해_샘플.csv",
                    mime="text/csv",
                    width="stretch",
                )
                st.caption("업로드한 CSV는 챗봇의 사고 통계 답변에 사용됩니다.")

    site_incidents = st.session_state.get("field_incident_frame")
    global_csv_valid = uploaded_file is None
    global_csv_error = None
    source_is_sample = uploaded_file is None
    if uploaded_file is None:
        incidents = sample_incidents()
        source_name = "가상 샘플 데이터"
        source_token = "sample"
    else:
        content = uploaded_file.getvalue()
        try:
            incidents = read_incidents_csv(content)
        except ValueError as exc:
            if view != "chat":
                st.error(f"CSV를 읽을 수 없습니다. {markdown_label(exc)}")
                st.stop()
            global_csv_error = str(exc)
            if isinstance(site_incidents, pd.DataFrame):
                incidents = site_incidents
                source_name = (
                    f"{st.session_state.get('field_incident_scope', '연결 현장')} · "
                    f"{st.session_state.get('field_incident_name', '사고 CSV')}"
                )
                source_token = f"site:{st.session_state.get('field_incident_token', '')}"
                source_is_sample = False
            else:
                incidents = sample_incidents()
                source_name = "가상 샘플 데이터"
                source_token = "sample"
                source_is_sample = True
        else:
            global_csv_valid = True
            source_name = uploaded_file.name
            source_token = sha256(content).hexdigest()

    if view == "chat":
        use_site_incidents = isinstance(site_incidents, pd.DataFrame) and (
            uploaded_file is None or not global_csv_valid
        )
        with st.sidebar:
            if isinstance(site_incidents, pd.DataFrame):
                if uploaded_file is not None and global_csv_valid:
                    source_choice = st.selectbox(
                        "챗봇 통계 자료",
                        options=("현장 기록", "전체 CSV"),
                        key="chat_incident_source",
                        help="월별·계절별·지역별 사고 질문에 사용할 자료입니다. 문서 검색과 작업계획 답변은 이 선택과 무관합니다.",
                    )
                    st.caption(
                        "현장 기록 · "
                        + markdown_label(st.session_state.get("field_incident_scope", "기록 범위 미입력"))
                        + " · "
                        + markdown_label(st.session_state.get("field_incident_name", "사고 CSV"))
                        + "　/　전체 CSV · "
                        + markdown_label(uploaded_file.name)
                    )
                    use_site_incidents = source_choice == "현장 기록"
                elif global_csv_error:
                    st.warning("전체 사고 CSV를 읽을 수 없어 연결한 현장 기록을 사용합니다.")
                    st.caption(f"파일 확인: {markdown_label(global_csv_error)}")
                else:
                    st.caption(
                        "챗봇 통계 자료: 현장 기록 · "
                        + markdown_label(st.session_state.get("field_incident_scope", "기록 범위 미입력"))
                    )
            elif global_csv_error:
                st.warning("전체 사고 CSV를 읽을 수 없어 가상 샘플을 통계에 사용합니다. 문서 검색과 현장 계획 질문은 계속 사용할 수 있습니다.")
                st.caption(f"파일 확인: {markdown_label(global_csv_error)}")
        chat_incidents = incidents
        chat_source = source_name
        chat_is_sample = source_is_sample
        chat_token = source_token
        # Use the site history by default; when both sources exist, the sidebar
        # makes the chosen scope explicit for every local-data answer.
        if use_site_incidents and isinstance(site_incidents, pd.DataFrame):
            chat_incidents = site_incidents
            scope = st.session_state.get("field_incident_scope", "연결 현장")
            filename = st.session_state.get("field_incident_name", "사고 CSV")
            chat_source = f"{scope} · {filename}"
            chat_is_sample = False
            chat_token = f"site:{st.session_state.get('field_incident_token', '')}:{scope}"
        show_chatbot(chat_incidents, chat_source, chat_is_sample, chat_token)
        render_back_to_top()
        return

    earliest = incidents["발생일"].min().date()
    latest = incidents["발생일"].max().date()
    industries = sorted(incidents["업종"].unique().tolist())
    regions = sorted(incidents["지역"].unique().tolist())
    if st.session_state.get("_source_token") != source_token or st.session_state.get("_filter_semantics") != "empty_is_all":
        reset_filters(earliest, latest)
        st.session_state["record_search"] = ""
        st.session_state["_source_token"] = source_token
        st.session_state["_filter_semantics"] = "empty_is_all"

    with st.sidebar:
        st.markdown('<div class="sidebar-section">RECENT RECORDS</div>', unsafe_allow_html=True)
        recent = incidents.sort_values("발생일", ascending=False).head(5)
        recent_rows = "".join(
            f'<div class="recent-row"><span class="recent-dot"></span>'
            f'<span class="recent-title">{escape(str(row["사고유형"]))} · {escape(str(row["지역"]))}</span>'
            f'<span class="recent-date">{row["발생일"]:%m.%d}</span></div>'
            for _, row in recent.iterrows()
        )
        st.markdown(f'<div class="sidebar-recent">{recent_rows}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-section">ANALYSIS</div>', unsafe_allow_html=True)
        with st.expander("조회 조건", expanded=False):
            dates = st.date_input(
                "발생 기간",
                min_value=earliest,
                max_value=latest,
                key="filter_dates",
            )
            selected_industries = st.multiselect("업종", industries, key="filter_industries", placeholder="전체 업종")
            selected_regions = st.multiselect("지역", regions, key="filter_regions", placeholder="전체 지역")
            st.button("필터 초기화", on_click=reset_filters, args=(earliest, latest), width="stretch")
            st.caption("비워 둔 항목은 전체 기록으로 봅니다.")
        st.markdown('<div class="sidebar-foot">SAFETY ATLAS &nbsp; / &nbsp; INCIDENT OS<br>ANALYTICS WORKSPACE</div>', unsafe_allow_html=True)

    # Streamlit returns a scalar date while a range selection is incomplete.
    # Ask for the second endpoint instead of crashing or silently narrowing to
    # a one-day report.
    if isinstance(dates, date):
        st.info("조회 기간의 시작일과 종료일을 모두 선택해 주세요.")
        st.stop()
    if (
        not isinstance(dates, (tuple, list))
        or len(dates) != 2
        or any(not isinstance(endpoint, date) for endpoint in dates)
    ):
        st.info("시작일과 종료일을 모두 선택해 주세요.")
        st.stop()

    start_date, end_date = dates
    mask = incidents["발생일"].dt.date.between(start_date, end_date)
    if selected_industries:
        mask &= incidents["업종"].isin(selected_industries)
    if selected_regions:
        mask &= incidents["지역"].isin(selected_regions)
    quick_severity = st.session_state.get("quick_severity", "전체")
    if quick_severity in SEVERITIES:
        mask &= incidents["재해정도"].eq(quick_severity)
    filtered = incidents.loc[mask].copy()

    render_header(
        source_name,
        f"{earliest:%Y.%m.%d}–{latest:%Y.%m.%d}"
        if view == "guide"
        else f"{start_date:%Y.%m.%d}–{end_date:%Y.%m.%d}",
        len(incidents) if view == "guide" else len(filtered),
        f"{latest:%Y.%m.%d}",
        uploaded_file is None,
        view,
    )

    if view == "overview":
        show_overview(filtered, start_date, end_date)
    elif view == "records":
        show_records(filtered)
    else:
        show_guide(incidents, source_name, uploaded_file is None)
    render_back_to_top()


def main() -> None:
    st.set_page_config(
        page_title="오늘 안전 브리핑 | Safety Atlas",
        page_icon="🦺",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _initialize_field_storage(st.session_state)
    storage_error = st.session_state.get("_field_storage_error")
    if storage_error:
        st.warning(storage_error)
    if st.session_state.get("_field_storage_conflict"):
        st.error("다른 브라우저 세션에서 저장한 최신 기록이 있습니다. 현재 입력은 저장하지 않았습니다.")
        if st.button("최신 저장본 다시 불러오기", type="primary", key="field_storage_reload"):
            _reload_latest_field_storage(st.session_state)
            st.rerun()
    try:
        _render_app()
    finally:
        _persist_field_storage(st.session_state)


if __name__ == "__main__":
    main()
