"""Manager-facing workday brief: weather, seasonal checks and sourced statistics."""
from collections import Counter
from datetime import date
from hashlib import sha256
from html import escape
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from preventra_plan import domain
from preventra_ui.statistics_view import get_statistics


KOSHA_HEAT = "https://www.kosha.or.kr/safety1team/news/news.do?articleNo=455846&mode=view"
KOSHA_COLD = "https://kosha.or.kr/kosha/data/business/occuHealthBusinessData.do?articleNo=296437&attachNo=166975&mode=download"
OPEN_METEO = "https://open-meteo.com/"


def _request_json(url: str, params: dict) -> dict:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "PreventraPlus/1.0"})
    with urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


@st.cache_data(ttl=1800, show_spinner=False)
def weather_for_day(location: str, day_iso: str) -> dict:
    """Resolve a coarse locality and return one day's forecast or archive summary."""
    area = " ".join(location.split()[:3]).strip()
    if not area:
        return {"status": "missing_location"}
    try:
        place_data = _request_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": area, "count": 1, "language": "ko", "format": "json", "countryCode": "KR"},
        )
        places = place_data.get("results") or []
        if not places:
            return {"status": "not_found"}
        place = places[0]
        target = date.fromisoformat(day_iso)
        today = domain.today_korea()
        offset = (target - today).days
        common = {
            "latitude": place["latitude"], "longitude": place["longitude"],
            "timezone": "Asia/Seoul", "temperature_unit": "celsius",
            "wind_speed_unit": "kmh", "precipitation_unit": "mm",
        }
        if -92 <= offset <= 16:
            params = {
                **common, "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max",
                "start_date": day_iso, "end_date": day_iso,
            }
            payload = _request_json("https://api.open-meteo.com/v1/forecast", params)
            source = "기상 예보 모델" if offset >= 0 else "과거 기상 모델 자료"
        elif offset < -92:
            payload = _request_json("https://archive-api.open-meteo.com/v1/archive", {
                **common, "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                "start_date": day_iso, "end_date": day_iso,
            })
            source = "과거 재분석 자료"
        else:
            return {"status": "out_of_range", "place": place.get("name", area)}
        daily = payload.get("daily") or {}
        if not daily.get("time"):
            return {"status": "unavailable", "place": place.get("name", area)}
        at = daily["time"].index(day_iso)
        def value(key):
            values = daily.get(key) or []
            return values[at] if at < len(values) else None
        return {
            "status": "ok", "place": ", ".join(filter(None, [place.get("admin1"), place.get("admin2"), place.get("name")])),
            "source": source, "temperature_max": value("temperature_2m_max"),
            "temperature_min": value("temperature_2m_min"), "precipitation": value("precipitation_sum"),
            "precipitation_probability": value("precipitation_probability_max"),
            "wind_max": value("wind_speed_10m_max"), "gust_max": value("wind_gusts_10m_max"),
            "weather_code": value("weather_code"),
        }
    except Exception:
        return {"status": "unavailable"}


def _season(day: date) -> tuple[str, list[str], str | None]:
    month = day.month
    if month in (6, 7, 8):
        return "여름", [
            "작업 전 체감온도와 폭염특보를 확인하고, 물·그늘·휴식 제공 계획을 작업자에게 안내합니다.",
            "옥외 고강도 작업과 온열질환 민감군을 확인하고, 이상 증상 발생 시 즉시 작업을 멈추는 절차를 공유합니다.",
        ], KOSHA_HEAT
    if month in (12, 1, 2):
        return "겨울", [
            "따뜻한 물과 바람을 피할 수 있는 휴식 장소, 방한복·장갑·미끄럼 방지 신발을 확인합니다.",
            "한파특보와 결빙 구간을 확인하고, 추운 시간대 옥외 작업 조정 및 이상 증상 시 보고·응급조치를 안내합니다.",
        ], KOSHA_COLD
    if month in (3, 4, 5):
        return "봄", [
            "일교차와 돌풍·황사 예보를 작업 전 확인하고, 고소·양중 작업은 현장 기상 기준과 작업허가 절차를 재확인합니다.",
            "겨울철 이후 통로·난간·비계·장비의 변형 또는 풀림이 없는지 작업 전 점검합니다.",
        ], None
    return "가을", [
        "일몰 시각과 일교차를 고려해 작업 조명·보온·휴식 계획을 확인합니다.",
        "강풍·강우 예보가 있으면 고소·양중 작업 기준과 배수·미끄럼 방지 조치를 작업 전에 재확인합니다.",
    ], None


def _weather_notes(weather: dict) -> list[tuple[str, str]]:
    notes = []
    if weather.get("status") != "ok":
        return notes
    hi, lo = weather.get("temperature_max"), weather.get("temperature_min")
    rain, gust = weather.get("precipitation"), weather.get("gust_max") or weather.get("wind_max")
    if hi is not None and hi >= 30:
        notes.append(("주의", "기온이 높습니다. 체감온도·폭염특보를 확인하고 물·그늘·휴식 및 작업자 건강 상태 확인을 계획하세요."))
    if lo is not None and lo <= 0:
        notes.append(("점검", "영하 기온 예보가 있습니다. 결빙 구간, 미끄럼 방지, 방한 및 따뜻한 휴식 장소를 확인하세요."))
    if rain is not None and rain >= 3:
        notes.append(("점검", "강수 예보가 있습니다. 통로 미끄럼, 배수, 옥외 전기기기 보호와 작업허가 조건을 점검하세요."))
    if gust is not None and gust >= 35:
        notes.append(("주의", "돌풍 예보가 있습니다. 양중·고소·가설 구조물 작업은 현장 기준과 기상특보를 확인한 뒤 판단하세요."))
    if not notes:
        notes.append(("확인", "표시된 일 단위 예보는 작업 위치의 관측값이 아닙니다. 작업 직전 현장 기상과 특보를 다시 확인하세요."))
    return notes


def _metric_card(label: str, value: str, detail: str = "") -> str:
    return (f'<div class="plus-kpi"><div class="plus-kpi-label">{escape(label)}</div>'
            f'<div class="plus-kpi-value">{escape(value)}</div><div class="plus-kpi-detail">{escape(detail)}</div></div>')


def _base_figure() -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        height=340, margin=dict(l=8, r=20, t=18, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard, sans-serif", color="#202b3c", size=12),
        hoverlabel=dict(bgcolor="#172536", bordercolor="#172536", font=dict(color="white", family="Pretendard, sans-serif", size=13)),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#7c8798")),
        yaxis=dict(showgrid=True, gridcolor="#edf0f4", zeroline=False, tickfont=dict(color="#687487")),
        hovermode="closest",
    )
    return figure


def _render_statistics(items, day: date):
    st.markdown('<div class="plus-section-kicker">산업재해 데이터</div><h2 class="plus-section-title">작업 맥락과 함께 보는 재해 현황</h2>', unsafe_allow_html=True)
    try:
        data = get_statistics()
    except Exception:
        data = pd.DataFrame()
    if data.empty:
        st.info("공식 산업 통계를 불러오지 못했습니다. 통계 저장소 연결 후 다시 확인해 주세요.")
        return
    industries = sorted(data["산업중분류"].dropna().unique().tolist())
    default = "건설업" if "건설업" in industries else industries[0]
    chosen = st.selectbox("비교할 산업중분류", industries, index=industries.index(default), key="plus_report_industry")
    metric_options = [name for name in ("사고재해자수", "사고사망자수") if name in set(data["지표"])]
    if not metric_options:
        st.info("표시할 사고 건수 통계가 없습니다.")
        return
    metric = st.radio("지표", metric_options, horizontal=True, key="plus_report_metric", label_visibility="collapsed")
    selected = data.loc[(data["산업중분류"] == chosen) & (data["지표"] == metric)].dropna(subset=["값"])
    if selected.empty:
        st.info("선택한 업종의 유효 통계가 없습니다.")
        return
    latest = int(selected["연도"].max())
    selected = selected.loc[selected["연도"] == latest].copy()
    values = selected.groupby("규모", observed=True)["값"].sum().sort_values(ascending=True)
    figure = _base_figure()
    colors = ["#b9c9ff"] * max(len(values) - 1, 0) + ["#4169e1"]
    figure.add_trace(go.Bar(
        x=values.values, y=[str(value) for value in values.index], orientation="h",
        marker=dict(color=colors, line=dict(width=0), cornerradius=7),
        hovertemplate=f"사업장 규모  %{{y}}<br>{escape(metric)}  <b>%{{x:,.0f}}명</b><extra></extra>",
    ))
    figure.update_layout(showlegend=False, bargap=.38, xaxis_title="명", yaxis_title=None)
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.plotly_chart(figure, width="stretch", config={"displayModeBar": False}, key="plus_report_industry_chart")
    with right:
        total = float(values.sum())
        st.html(_metric_card(f"{latest}년 {chosen} · {metric}", f"{total:,.0f}명", "수록된 규모 구간 합계"))
        work_summary = ", ".join(dict.fromkeys(item.trade or item.activity for item in items[:3]))
        st.markdown(f"**오늘 계획 작업**  \n{escape(work_summary) if work_summary else '작업 정보 미기재'}")
        st.caption("산업 분류 단위의 연간 집계입니다. 이 값은 선택 작업의 발생 건수·위험도·확률을 뜻하지 않습니다.")
    st.caption("출처: 한국산업안전보건공단 산업중분류·사업장 규모별 사고 통계. 누락 셀은 합계에서 제외됩니다.")


def _render_case_candidates(items, day: date):
    title = ", ".join(item.activity for item in items[:4])
    query = " / ".join(filter(None, [title, ", ".join(dict.fromkeys(i.equipment for i in items[:4] if i.equipment))]))[:1200]
    cache_key = f"{day.isoformat()}:{query}"
    st.markdown('<div class="plus-section-kicker">작업 연관 검색</div><h2 class="plus-section-title">계획 작업과 유사한 사고사례</h2>', unsafe_allow_html=True)
    st.caption("사고사례 검색 후보를 요약합니다. 후보 건수는 실제 발생빈도나 확률 통계가 아닙니다.")
    if st.button("작업 관련 사례 검색", key="plus_report_search_cases", type="primary", disabled=not query):
        try:
            from preventra_agent.tools import SafetyTools
            with st.spinner("작업 표현과 유사한 사고사례를 찾고 있습니다…"):
                result = SafetyTools().search(query, "sif")
            st.session_state.plus_report_cases = {
                "key": cache_key,
                "rows": [{"title": evidence.title, "text": evidence.content[:900], "metadata": evidence.metadata or {}}
                         for evidence in result.evidence[:12]],
            }
        except Exception:
            st.session_state.plus_report_cases = {"key": cache_key, "error": True, "rows": []}
    cached = st.session_state.get("plus_report_cases", {})
    if cached.get("key") != cache_key:
        st.info("오늘 작업을 선택한 뒤 검색하면 관련 사고사례 후보를 확인할 수 있습니다.")
        return
    if cached.get("error"):
        st.info("사고사례 검색 서비스를 사용할 수 없습니다. 저장소·모델 설정을 확인해 주세요.")
        return
    rows = cached.get("rows", [])
    if not rows:
        st.info("현재 검색 조건에서 표시할 후보 사례가 없습니다.")
        return
    categories = []
    for row in rows:
        metadata = row["metadata"]
        label = next((str(metadata.get(key)).strip() for key in ("재해유발요인", "재해종류", "소분류", "기인물") if metadata.get(key)), "분류 미기재")
        categories.append(label[:35])
    counts = Counter(categories).most_common(8)
    figure = _base_figure()
    figure.add_trace(go.Bar(
        x=[value for _, value in counts], y=[label for label, _ in counts], orientation="h",
        marker=dict(color=["#466cf5" if n == max(v for _, v in counts) else "#b9c9ff" for _, n in counts], cornerradius=7),
        hovertemplate="검색 후보 분류  %{y}<br>사례 후보  <b>%{x}건</b><extra></extra>",
    ))
    figure.update_layout(showlegend=False, bargap=.38, yaxis=dict(autorange="reversed"))
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False}, key="plus_report_case_chart")
    with st.expander(f"검색 후보 {len(rows)}건 확인"):
        for row in rows:
            st.markdown(f"**{escape(row['title'])}**")
            st.caption(escape(row["text"]))


def render_manager_dashboard():
    value = st.session_state.plus_saved.snapshot
    if not value:
        st.info("보고서를 열려면 작업계획서를 먼저 적용해 주세요.")
        return
    plan = domain.decode_plan(value["plan"])
    st.session_state.setdefault("plus_day", date.fromisoformat(value["day"]))
    day = st.session_state.plus_day
    st.html(f'''<section class="plus-report-hero">
      <div class="plus-report-overline">DAILY SAFETY BRIEF · {day:%Y.%m.%d}</div>
      <div class="plus-report-heading"><div><h1>{escape(plan.site)}</h1><p>{escape(" · ".join(filter(None, [plan.site_location, "오늘의 작업 안전 브리핑"])) )}</p></div>
      <span class="plus-report-badge">MANAGER REPORT</span></div></section>''')
    day_col, work_col, weather_col = st.columns([1, 1.5, 1.5], gap="medium")
    with day_col:
        day = st.date_input("보고 기준일", key="plus_day", on_change=domain_day_change, disabled=ui_blocked())
    daily = domain.daily_rows(plan, day)
    choices = [""] + [item.work_id for item in daily]
    st.session_state.setdefault("plus_work", value.get("work_id") or "")
    if st.session_state.plus_work not in choices:
        st.session_state.plus_work = ""
    labels = {item.work_id: domain.work_selection_label(item) for item in daily}
    with work_col:
        selected_id = st.selectbox("작업 범위", choices, format_func=lambda key: labels.get(key, "해당 날짜 전체"),
                                   key="plus_work", on_change=domain_work_change, disabled=ui_blocked())
    location_default = " ".join(plan.site_location.split()[:3])
    st.session_state.setdefault("plus_weather_location", location_default)
    with weather_col:
        st.text_input("날씨 조회 지역 · 시/군/구", key="plus_weather_location", help="주소 전체 대신 앞의 세 행정구역 단위까지만 조회합니다.")
    items = [item for item in daily if not selected_id or item.work_id == selected_id]
    if not items:
        st.info(f"해당 날짜에 등록된 작업이 없습니다. ({day:%Y년 %m월 %d일}) 다른 날짜의 작업을 확인해 주세요.")
        return
    workers = sum(item.people or 0 for item in items)
    people_recorded = sum(item.people is not None for item in items)
    missing = sum(bool(domain.missing_work_fields(item)) for item in items)
    st.html('<div class="plus-kpi-grid">' + _metric_card("계획 작업", f"{len(items)}건", "선택한 날짜·작업 범위")
            + _metric_card("계획 투입 인원", f"{workers:,}명" if people_recorded else "미기재",
                           f"인원 기재 {people_recorded}/{len(items)}건")
            + _metric_card("추가 확인 작업", f"{missing}건", "계획 안전조치·담당·장비 등 누락 포함")
            + '</div>')
    st.markdown('<div class="plus-section-kicker">오늘의 환경</div><h2 class="plus-section-title">현장 날씨와 계절별 확인사항</h2>', unsafe_allow_html=True)
    weather = weather_for_day(st.session_state.plus_weather_location, day.isoformat())
    season, seasonal_items, seasonal_source = _season(day)
    if weather.get("status") == "ok":
        stats = st.columns(4, gap="medium")
        place = weather.get("place") or st.session_state.plus_weather_location
        for col, label, value_text in zip(stats, ("현장 지역", "최고 / 최저", "강수량 / 확률", "최대 순간풍속"),
            (place, f"{weather['temperature_max'] if weather['temperature_max'] is not None else '—'}° / {weather['temperature_min'] if weather['temperature_min'] is not None else '—'}°C",
             f"{weather['precipitation'] if weather['precipitation'] is not None else '—'}mm / {weather['precipitation_probability'] if weather['precipitation_probability'] is not None else '—'}%",
             f"{weather['gust_max'] if weather['gust_max'] is not None else weather['wind_max'] if weather['wind_max'] is not None else '—'}km/h")):
            with col:
                st.html(_metric_card(label, value_text))
        st.markdown(f"{weather['source']} · {day.isoformat()} · 지역 단위 참고값 · 출처: [Open-Meteo]({OPEN_METEO})")
    elif weather.get("status") == "out_of_range":
        st.info("선택 날짜가 예보 제공 범위를 벗어났습니다. 현장 기상청 예보를 확인해 주세요.")
    else:
        st.info("지역 날씨를 가져오지 못했습니다. 작업계획서의 현장지역 또는 조회 지역을 확인해 주세요.")
    for label, note in _weather_notes(weather):
        st.markdown(f'<div class="plus-safety-note"><strong>{escape(label)}</strong><span>{escape(note)}</span></div>', unsafe_allow_html=True)
    if weather.get("status") == "ok":
        st.caption("날씨 주의 알림은 일 단위 예보에 기반한 참고 신호입니다. 법정 기준이나 작업중지 기준을 대신하지 않으므로 현장 절차와 기상특보를 확인하세요.")
    st.markdown(f'<div class="plus-season-card"><div class="plus-season-label">{season}철 안전 점검</div><ul>'
                + "".join(f"<li>{escape(note)}</li>" for note in seasonal_items) + '</ul></div>', unsafe_allow_html=True)
    source_link = f' · <a href="{seasonal_source}" target="_blank" rel="noreferrer">안전보건공단 가이드 확인</a>' if seasonal_source else ""
    st.markdown(f'<div class="plus-source-note">계절별 항목은 작업 전 확인을 돕는 참고 점검표입니다. 현장 절차와 최신 특보를 우선 확인하세요.{source_link}</div>', unsafe_allow_html=True)
    st.markdown('<div class="plus-divider"></div>', unsafe_allow_html=True)
    _render_statistics(items, day)
    st.markdown('<div class="plus-divider"></div>', unsafe_allow_html=True)
    _render_case_candidates(items, day)
    st.markdown('<div class="plus-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="plus-section-kicker">작업 전 브리핑</div><h2 class="plus-section-title">계획서에서 확인할 항목</h2>', unsafe_allow_html=True)
    for item in items:
        with st.expander(f"{item.start:%H:%M}–{item.end:%H:%M}  ·  {item.activity}  ·  {item.area}", expanded=False):
            st.markdown(f"**공종 / 장비**  \n{escape(item.trade or '미기재')} · {escape(item.equipment or '장비 미기재')}")
            st.markdown(f"**계획 안전조치**  \n{escape(item.planned_controls or '계획서에 기재되지 않았습니다.')}")
            st.markdown(f"**추가 확인**  \n{escape(item.follow_up or '계획서에 기재되지 않았습니다.')}")
            missing_fields = domain.missing_work_fields(item)
            if missing_fields:
                st.warning("작업 전 확인 필요: " + ", ".join(missing_fields))
    st.markdown('<div class="plus-report-footer">이 보고서는 작업계획서, 지역 단위 기상자료, 수록 통계와 검색 후보를 요약합니다. 현장의 실제 상태와 적법성 판단을 대신하지 않습니다.</div>', unsafe_allow_html=True)
    st.button("선택 작업 주의사항 질문하기", key="plus_ask", type="primary",
              on_click=_ask_about_selection, width="stretch")
    with st.expander("작업계획서 변경", expanded=False):
        upload = st.file_uploader("새 작업계획서 (.xlsx)", type=["xlsx"], max_upload_size=10,
                                  key=f"plus_report_upload_{st.session_state.plus_upload_generation}")
        if upload is not None:
            content = upload.getvalue()
            token = sha256(content).hexdigest()
            if token != st.session_state.plus_candidate_token:
                st.session_state.plus_candidate = None
                st.session_state.plus_candidate_token = token
                try:
                    st.session_state.plus_candidate = domain.read_work_plan(content)
                except Exception:
                    st.error("작업계획서를 읽지 못했습니다. .xlsx 형식과 날짜·시간·필수 열을 확인해 주세요.")
        candidate = st.session_state.plus_candidate
        if candidate:
            st.caption(f"{candidate.site} · 작업 {len(candidate.items)}건 · 적용 전 미리보기")
            if candidate.issues:
                for issue in candidate.issues:
                    st.warning(issue)
            acknowledge = not candidate.issues or st.checkbox("제외된 행과 확인사항을 읽었습니다.",
                key="plus_report_ack_" + st.session_state.plus_candidate_token)
            from preventra_plan import ui as plan_ui
            if st.button("계획서 적용", key="plus_apply", type="primary",
                         disabled=plan_ui.blocked() or not acknowledge):
                plan_ui.apply_candidate()


def domain_day_change():
    from preventra_plan.ui import select_day
    select_day()


def domain_work_change():
    from preventra_plan.ui import select_work
    select_work()


def ui_blocked():
    from preventra_plan.ui import blocked
    return blocked()


def _ask_about_selection():
    from preventra_ui import state
    from preventra_plan.ui import current_context
    state.queue_question("선택한 날짜와 작업계획을 바탕으로 작업 전 주요 주의사항과 확인 항목을 근거 자료와 함께 정리해 주세요.",
                         context=current_context())
