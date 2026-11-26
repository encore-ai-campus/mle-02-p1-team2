"""Compact forecast context with explicit site selection."""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from shining_chatbot.business_time import now_korea
from shining_chatbot.weather_data import WeatherLocation, fetch_forecast, forecast_label, search_locations, summarize_work_window, weather_query_from_site_location, work_weather_notes
from shining_chatbot.work_plan import WorkItem


@st.cache_data(ttl=3600, show_spinner=False)
def _locations(query: str) -> tuple[WeatherLocation, ...]:
    return search_locations(query)


def resolve_plan_weather_location(site_location: str) -> tuple[WeatherLocation | None, str]:
    """Resolve only the plan's administrative area; never send its full address."""
    query = weather_query_from_site_location(site_location)
    if not query:
        return None, "계획서에서 시·군·구 지역을 확인하지 못했습니다. 상단에 ‘현장 지역’과 지역명을 입력해 주세요."
    try:
        matches = _locations(query)
    except ValueError as exc:
        return None, f"{query} 날씨 위치를 찾지 못했습니다. {exc}"
    if not matches:
        return None, f"계획서 지역 ‘{query}’에 맞는 예보 위치가 없습니다. 지역명을 확인해 주세요."
    location = matches[0]
    reference = " · 도심 참고 좌표" if "도심 참고 위치" in location.name else ""
    return location, f"날씨 자동 연결 · {location.region} {location.name}{reference} · 계획서 지역 {query} 기준"


@st.cache_data(ttl=1800, show_spinner=False)
def _forecast(location: WeatherLocation):
    return fetch_forecast(location)


def _weather_styles() -> None:
    st.markdown("""<style>
.weather-panel{border:1px solid #DCE7DC;border-radius:8px;background:#F7FAF6;padding:15px 18px;margin:17px 0 22px}
.weather-head{display:flex;justify-content:space-between;gap:18px;align-items:baseline}.weather-head strong{font-size:13px;font-weight:620;color:#294333}
.weather-head span{font-size:10px;color:#5F6D62}.weather-values{display:flex;gap:24px;flex-wrap:wrap;margin:15px 0 5px}
.weather-value b{display:block;color:#324D3A;font-size:18px;line-height:1.2;font-weight:610;letter-spacing:-.03em}
.weather-value small{display:block;color:#5F6D62;font-size:10px;margin-top:4px}.weather-notes{margin-top:10px;padding-top:10px;border-top:1px solid #E0E9DF;color:#506553;font-size:11px;line-height:1.65}
.weather-source{color:#68796D;font-size:10px;line-height:1.6;margin-top:8px}.weather-source a{color:#456A4E;text-decoration:underline;text-underline-offset:2px}
.weather-work-list{display:grid;gap:7px;margin-top:13px;padding-top:12px;border-top:1px solid #E0E9DF}
.weather-work-head{font-size:10px;font-weight:620;letter-spacing:.02em;color:#415B47;margin-bottom:1px}
.weather-work-row{display:grid;grid-template-columns:96px minmax(0,1fr);gap:8px;padding:9px;border:1px solid #E5ECE4;border-radius:6px;background:#FFFFFFB8}.weather-work-row>div{min-width:0}
.weather-work-time{font-size:10px;font-weight:600;color:#506A55;line-height:1.5}.weather-work-name{font-size:10px;font-weight:580;color:#3D5042;line-height:1.6;overflow-wrap:anywhere;word-break:keep-all}
.weather-work-detail{font-size:10px;color:#5F6D62;line-height:1.65;margin-top:3px;overflow-wrap:anywhere;word-break:keep-all}.weather-work-note{font-size:10px;color:#786440;line-height:1.65;margin-top:4px;overflow-wrap:anywhere;word-break:keep-all}
[class*="st-key-field_weather_refresh"] button,[class*="st-key-tbm_weather_refresh"] button{min-height:34px;font-size:11px}
@media(max-width:640px){.weather-values{gap:12px}.weather-value{width:calc(50% - 10px)}}
</style>""", unsafe_allow_html=True)


def _location_setup() -> None:
    current: WeatherLocation | None = st.session_state.get("field_weather_location")
    candidates = st.session_state.get("field_location_candidates", ())
    title = "현장 예보 위치 변경" if current is not None else "현장 예보 위치 설정"
    with st.expander(title, expanded=current is None or bool(candidates)):
        if current is not None:
            st.caption(f"현재 연결 위치 · {current.region} · {current.name}")
        st.caption("계획서 상단의 ‘현장 지역’이 자동 연결되지 않은 경우 행정구역을 확인해 검색할 수 있습니다. 현장명만으로 위치를 추측하지 않습니다.")
        st.caption("검색 결과가 하나면 바로 예보를 연결합니다. 여러 후보나 도심 참고 좌표는 위치를 확인한 뒤 연결하세요.")
        st.caption("위치 검색어와 선택한 예보 좌표는 Open-Meteo로 전송됩니다. 현장명·작업계획·작업자 정보는 전송하지 않습니다.")
        with st.form("field_weather_search"):
            query = st.text_input(
                "시·군·구 검색",
                placeholder="예: 수원, 서울, 경기도 수원시 영통구",
                max_chars=80,
                key="field_weather_query",
            )
            searched = st.form_submit_button("위치 찾기")
        if searched:
            st.session_state.pop("field_weather_candidate", None)
            st.session_state.pop("field_location_candidates", None)
            try:
                with st.spinner("현장 위치 검색 중..."):
                    found = _locations(query)
            except ValueError as exc:
                st.error(str(exc))
            else:
                if len(found) == 1 and "도심 참고 위치" not in found[0].name:
                    # Common city searches usually resolve to one exact geocoder
                    # result. Connect it in the same action so the forecast appears
                    # without a second select-and-confirm step.
                    st.session_state["field_weather_location"] = found[0]
                    st.session_state.pop("field_weather_error", None)
                    st.rerun()
                st.session_state["field_location_candidates"] = found
                if not found:
                    st.info("위치 후보가 없습니다. 현장·건물명 대신 시·군·구를 입력하거나, 도와 시를 함께 적어 보세요. 예: 용인, 경기도 수원시, 서울특별시.")
        candidates = st.session_state.get("field_location_candidates", ())
        if candidates:
            if any("도심 참고 위치" in location.name for location in candidates):
                st.caption("도시 중심 참고 좌표입니다. 실제 작업 위치와 다를 수 있으니, 작업 장소와 가까운지 확인한 뒤 연결하세요.")
            labels = {
                f"{location.region} · {location.name} ({location.latitude:.3f}, {location.longitude:.3f})": location
                for location in candidates
            }
            selected = st.selectbox("현장과 가장 가까운 위치", list(labels), key="field_weather_candidate")
            if st.button("이 위치로 예보 연결", type="primary", key="field_weather_save"):
                st.session_state["field_weather_location"] = labels[selected]
                st.session_state.pop("field_location_candidates", None)
                st.rerun()


def weather_for_day(day: date):
    location: WeatherLocation | None = st.session_state.get("field_weather_location")
    if location is None:
        return None
    try:
        with st.spinner("현장 예보 불러오는 중..."):
            forecasts = _forecast(location)
    except ValueError as exc:
        st.session_state["field_weather_error"] = (day, str(exc))
        st.warning(str(exc))
        return None
    st.session_state.pop("field_weather_error", None)
    return next((forecast for forecast in forecasts if forecast.day == day), None)


def show_weather_refresh_button(key: str) -> None:
    """Let a manager bypass the short forecast cache before an operational review."""
    if st.button(
        "예보 최신 값으로 다시 확인", key=key, icon=":material/refresh:",
        help="현재 화면의 예보 응답은 최대 30분 캐시됩니다. 누르면 캐시를 지우고 다시 조회합니다.",
    ):
        _forecast.clear()
        st.rerun()


def _hourly_work_rows(items: list[WorkItem], forecast) -> str:
    rows = []
    for item in sorted(items, key=lambda work: (work.start, work.end, work.work_id)):
        summary = summarize_work_window(item, forecast)
        note_html = (
            f'<div class="weather-work-note">작업 전 확인 · {escape(" · ".join(summary.checks))}</div>'
            if summary.checks else ""
        )
        rows.append(
            '<div class="weather-work-row"><div class="weather-work-time">'
            f'{escape(summary.time_label)}</div><div>'
            f'<div class="weather-work-name">{escape(summary.activity)}</div>'
            f'<div class="weather-work-detail">{escape(summary.detail)}</div>'
            f'{note_html}</div></div>'
        )
    if not rows:
        return ""
    return '<div class="weather-work-list"><div class="weather-work-head">작업 시간대별 예보 · 작업별 현장 확인</div>' + "".join(rows) + '</div>'


def show_weather_panel(day: date, items: list[WorkItem]) -> None:
    _weather_styles()
    st.caption("날씨 조회 시 선택한 시·군·구와 예보 좌표가 Open-Meteo로 전송됩니다. 현장명·작업계획·작업자 정보는 전송하지 않습니다.")
    location: WeatherLocation | None = st.session_state.get("field_weather_location")
    if location is None:
        st.markdown(
            '<div class="weather-panel"><div class="weather-head"><strong>현장 날씨</strong><span>위치 설정 필요</span></div>'
            '<div class="weather-source">위치를 확인하면 이 날짜의 예보와 작업 관련 확인 문구를 표시합니다.</div></div>',
            unsafe_allow_html=True,
        )
        _location_setup()
        return
    forecast = weather_for_day(day)
    if forecast is None:
        error = st.session_state.get("field_weather_error")
        failed = isinstance(error, tuple) and error[0] == day
        guidance = (
            "예보 연결에 실패했습니다. 잠시 뒤 다시 시도하고 기상청 특보를 직접 확인하세요."
            if failed else
            "선택한 날짜의 예보 범위를 확인할 수 없습니다. 현장 기상과 기상특보를 직접 확인하세요."
        )
        st.markdown(
            '<div class="weather-panel"><div class="weather-head"><strong>현장 날씨</strong>'
            f'<span>{escape(location.region)} · {escape(location.name)}</span></div>'
            f'<div class="weather-source">{guidance}</div></div>',
            unsafe_allow_html=True,
        )
        if failed:
            if st.button("예보 다시 불러오기", key=f"field_weather_retry_{day}"):
                _forecast.clear()
                st.rerun()
        _location_setup()
        return
    values = (
        (forecast_label(forecast.weather_code), "하루 예보"),
        (f"{forecast.precipitation_probability_max}%" if forecast.precipitation_probability_max is not None else "—", "최대 강수확률"),
        (f"{forecast.temperature_max:.1f}°" if forecast.temperature_max is not None else "—", "최고 기온"),
        (f"{forecast.apparent_temperature_max:.1f}°" if forecast.apparent_temperature_max is not None else "—", "모델 체감 최고"),
        (f"{forecast.wind_gusts_max:.0f} km/h" if forecast.wind_gusts_max is not None else "—", "최대 순간풍속 예보"),
    )
    cells = "".join(f'<div class="weather-value"><b>{escape(value)}</b><small>{escape(label)}</small></div>' for value, label in values)
    notes = work_weather_notes(tuple(item.activity for item in items), forecast)
    note_html = "<br>".join(escape(note) for note in notes) if notes else "작업 전 현장 기상과 장비·작업 기준을 확인하세요."
    hourly_html = _hourly_work_rows(items, forecast)
    st.markdown(
        '<div class="weather-panel"><div class="weather-head"><strong>현장 날씨 · 작업 확인</strong>'
        f'<span>{escape(location.region)} · {escape(location.name)} · {day:%m.%d}</span></div>'
        f'<div class="weather-values">{cells}</div><div class="weather-notes">{note_html}</div>'
        f'{hourly_html}'
        '<div class="weather-source">모델 예보: <a href="https://open-meteo.com/en/docs" target="_blank" rel="noopener noreferrer">Open-Meteo</a> · '
        '<a href="https://www.weather.go.kr/w/weather/warning/status.do" target="_blank" rel="noopener noreferrer">기상청 특보 확인 ↗</a> · '
        '<a href="https://www.kosha.or.kr/safety1team/tr/reference.do?articleNo=456837&attachNo=263892&mode=download" target="_blank" rel="noopener noreferrer">안전보건공단 폭염 예방수칙 ↗</a> · '
        '<a href="https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=273603" target="_blank" rel="noopener noreferrer">산업안전보건기준에 관한 규칙 ↗</a> · '
        '<a href="https://www.moel.go.kr/news/cardinfo/view.do?bbs_seq=20251200063" target="_blank" rel="noopener noreferrer">고용노동부 한파 안전 안내 ↗</a> · '
        f'화면 확인 {now_korea():%H:%M} KST · 예보 응답은 최대 30분 캐시 · '
        '모델 예보는 현장 측정이나 작업 허가 기준을 대신하지 않습니다.</div></div>',
        unsafe_allow_html=True,
    )
    show_weather_refresh_button(f"field_weather_refresh_{day:%Y%m%d}")
    _location_setup()
