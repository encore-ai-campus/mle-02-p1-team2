"""Manager-facing workday brief: site conditions and task-matched accident cases."""
from collections import Counter
from datetime import date, time, datetime
from hashlib import sha256
from html import escape
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import plotly.graph_objects as go
import streamlit as st

from preventra_plan import domain


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
        parts = area.split()
        city = next((part for part in reversed(parts)
                     if part.endswith(("특별시", "광역시", "특별자치시", "시", "군"))), None)
        province = next((part for part in parts
                         if part.endswith(("도", "특별시", "광역시", "특별자치도", "특별자치시"))), None)
        candidates = list(dict.fromkeys(filter(None, [
            f"{city}, {province}" if city and province and city != province else None,
            city, " ".join(parts[-2:]), parts[-1], area,
        ])))
        places = []
        for name in candidates:
            place_data = _request_json(
                "https://geocoding-api.open-meteo.com/v1/search",
                {"name": name, "count": 1, "language": "ko", "format": "json", "countryCode": "KR"},
            )
            places = place_data.get("results") or []
            if places:
                break
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
        place_labels = []
        for key in ("admin1", "admin2", "name"):
            label = (place.get(key) or "").strip()
            if label and label not in place_labels:
                place_labels.append(label)
        def value(key):
            values = daily.get(key) or []
            return values[at] if at < len(values) else None
        return {
            "status": "ok", "place": ", ".join(place_labels),
            "source": source, "temperature_max": value("temperature_2m_max"),
            "temperature_min": value("temperature_2m_min"), "precipitation": value("precipitation_sum"),
            "precipitation_probability": value("precipitation_probability_max"),
            "wind_max": value("wind_speed_10m_max"), "gust_max": value("wind_gusts_10m_max"),
            "weather_code": value("weather_code"),
        }
    except Exception:
        return {"status": "unavailable"}


def _season(day: date) -> str:
    month = day.month
    if month in (6, 7, 8):
        return "여름"
    if month in (12, 1, 2):
        return "겨울"
    if month in (3, 4, 5):
        return "봄"
    return "가을"


def _weather_brief(weather: dict, season: str) -> str:
    """A concise, non-alarmist instruction for the top of the site report."""
    if weather.get("status") != "ok":
        return "지역 예보를 확인할 수 없습니다. 작업 시작 전 현장 기상과 특보를 확인하세요."

    code = weather.get("weather_code")
    high, low = weather.get("temperature_max"), weather.get("temperature_min")
    rain, probability = weather.get("precipitation"), weather.get("precipitation_probability")
    wind = weather.get("gust_max") if weather.get("gust_max") is not None else weather.get("wind_max")
    snow_codes = {71, 73, 75, 77, 85, 86}
    storm_codes = {95, 96, 99}
    if code in snow_codes or (rain is not None and rain > 0 and low is not None and low <= 0):
        if low is not None and low <= -5:
            return "눈·한파·결빙 사고에 주의하세요. 통로 제설과 미끄럼 방지, 방한·휴식 여건을 확인하세요."
        return "눈·결빙 사고에 주의하세요. 작업통로 제설과 미끄럼 방지, 고소작업 발판 상태를 확인하세요."
    if low is not None and low <= -5:
        return "한파와 결빙에 주의하세요. 통로 미끄럼 방지와 방한·휴식 여건을 확인하세요."
    if code in storm_codes:
        return "낙뢰·강한 비에 주의하세요. 옥외·고소 작업은 현장 기상 기준과 작업중지 절차를 확인하세요."

    hazards = []
    if wind is not None and wind >= 50:
        hazards.append("강풍")
    elif wind is not None and wind >= 30:
        hazards.append("강한 바람")
    if rain is not None and rain >= 20 and (probability is None or probability >= 50):
        hazards.append("강한 비")
    elif rain is not None and rain >= 3:
        hazards.append("비")
    elif (rain is not None and rain >= 0.1) or (probability is not None and probability >= 50):
        hazards.append("약한 비")
    if high is not None and high >= 33:
        hazards.append("폭염")

    if hazards:
        advice = []
        if wind is not None and wind >= 30:
            advice.append("고소·양중 작업 전 풍속과 작업중지 기준을 확인하세요")
        if (rain is not None and rain >= 0.1) or (probability is not None and probability >= 50):
            advice.append("작업통로 미끄럼과 배수 상태를 점검하세요")
        if high is not None and high >= 33:
            advice.append("물·그늘·휴식과 작업자 건강 상태를 확인하세요")
        headline = f"오늘은 {'·'.join(hazards)} 예보입니다."
        return f"{headline} {' '.join(advice)}"

    seasonal_briefs = {
        "봄": "봄철 돌풍·황사와 겨울 이후 가설물 손상에 주의하세요. 고소·양중 작업 전 기상과 비계·난간을 확인하세요.",
        "여름": "여름철 온열질환에 주의하세요. 체감온도와 폭염특보를 확인하고 물·그늘·휴식 계획을 점검하세요.",
        "가을": "가을철 일교차와 짧아지는 일조시간에 유의하세요. 작업 조명과 보온·휴식 여건을 확인하세요.",
        "겨울": "겨울철 한랭질환과 결빙 사고에 주의하세요. 방한·휴식 여건과 작업통로 미끄럼 방지를 확인하세요.",
    }
    return seasonal_briefs[season]


def _weather_summary(weather: dict) -> tuple[str, str, str]:
    """Return plain-language conditions followed by their forecast values."""
    rain = weather.get("precipitation")
    probability = weather.get("precipitation_probability")
    snow_codes = {71, 73, 75, 77, 85, 86}
    if weather.get("weather_code") in snow_codes:
        rain_text = "눈 예보"
        if rain is not None:
            rain_text += f" · 예상 강수량 {rain:.1f}mm"
        if probability is not None:
            rain_text += f" · 확률 {probability}%"
    elif rain is None:
        rain_text = f"강수확률 {probability}%" if probability is not None else "자료 없음"
    else:
        rain_state = ("비 가능성" if probability is not None and probability >= 50 else "비 없음") if rain < 0.1 else "약한 비" if rain < 3 else "비" if rain < 15 else "강한 비"
        rain_text = f"{rain_state} · {rain:.1f}mm"
        if probability is not None:
            rain_text += f" · 강수확률 {probability}%"

    wind = weather.get("gust_max") if weather.get("gust_max") is not None else weather.get("wind_max")
    if wind is None:
        wind_text = "자료 없음"
    else:
        wind_state = "강풍" if wind >= 50 else "바람 강함" if wind >= 30 else "약한 바람" if wind >= 15 else "바람 잔잔"
        wind_text = f"{wind_state} · {wind:.1f}km/h"

    high, low = weather.get("temperature_max"), weather.get("temperature_min")
    if high is None and low is None:
        temp_text = "자료 없음"
    else:
        temp_state = "더움" if high is not None and high >= 28 else "추움" if low is not None and low <= 5 else "온화함"
        temp_text = (f"{temp_state} · 최고 {high:.1f}°C" if high is not None else f"최저 {low:.1f}°C")
        if high is not None and low is not None:
            temp_text += f" · 최저 {low:.1f}°C"
    return temp_text, rain_text, wind_text


def _metric_card(label: str, value: str, detail: str = "") -> str:
    return (f'<div class="plus-kpi"><div class="plus-kpi-label">{escape(label)}</div>'
            f'<div class="plus-kpi-value">{escape(value)}</div><div class="plus-kpi-detail">{escape(detail)}</div></div>')


def _base_figure() -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        height=340, margin=dict(l=8, r=20, t=18, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard, sans-serif", color="#202b3c", size=12),
        hoverlabel=dict(
            bgcolor="#ffffff", bordercolor="#dfe6ef", align="left", namelength=-1,
            font=dict(color="#344256", family="Pretendard, sans-serif", size=13),
        ),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#7c8798")),
        yaxis=dict(showgrid=True, gridcolor="#edf0f4", zeroline=False, tickfont=dict(color="#687487")),
        hovermode="closest",
    )
    return figure


def _render_case_candidates(items, day: date):
    if not items:
        return
    selected = st.selectbox("사고사례를 확인할 작업", items,
                            format_func=domain.work_selection_label, key="plus_case_task")
    title = selected.activity
    query = " / ".join(filter(None, [selected.activity, selected.trade, selected.equipment]))[:1200]
    cache_key = f"{day.isoformat()}:{query}"
    st.markdown(f'<div class="plus-section-kicker">작업별 사고사례</div>'
                f'<h2 class="plus-section-title">{escape(title)} · 유사 사고 유형</h2>', unsafe_allow_html=True)
    st.caption("작업명·공종·장비가 유사한 수록 사고사례를 유형별로 묶었습니다. 전체 발생 건수 통계는 아닙니다.")

    def search_cases():
        try:
            from preventra_agent.tools import SafetyTools
            with st.spinner("작업 표현과 유사한 사고사례를 찾고 있습니다…"):
                result = SafetyTools().search(query, "sif")
            st.session_state.plus_report_cases = {
                "key": cache_key,
                "rows": [{"title": evidence.title, "text": evidence.excerpt[:900], "metadata": evidence.source or {}}
                         for evidence in result.evidence[:12]],
            }
        except Exception:
            st.session_state.plus_report_cases = {"key": cache_key, "error": True, "rows": []}

    case_cache = st.session_state.setdefault("plus_report_case_cache", {})
    cached = case_cache.get(cache_key, {})
    requested = st.button("유사 사고사례 다시 검색" if cached else "유사 사고사례 불러오기",
                          key="plus_load_cases", disabled=ui_blocked())
    if requested and query:
        search_cases()
        cached = st.session_state.pop("plus_report_cases", {})
        case_cache[cache_key] = cached
    if not cached:
        st.caption("필요할 때 SIF 검색으로 이 작업의 사고사례와 출처를 확인하세요.")
        return
    if cached.get("error"):
        st.caption("유사 사고사례를 불러오지 못했습니다. 사고사례 데이터 연결을 확인해 주세요.")
        return
    rows = cached.get("rows", [])
    if not rows:
        st.caption("이 작업과 직접 연결되는 사고사례를 찾지 못했습니다.")
        return
    categories = []
    for row in rows:
        metadata = row["metadata"]
        label = next((str(metadata.get(key)).strip() for key in ("재해종류", "accident_type") if metadata.get(key)), "미분류")
        categories.append(label[:35])
    counts = Counter(categories).most_common(8)
    from preventra_plan.vendor.briefing_report import safety_briefing_html
    markup = safety_briefing_html({"cases": [{
        "activity": selected.activity, "total": len(rows),
        "counts": [{"name": name, "count": count} for name, count in counts],
    }]})
    # Keep the teammate's case cards/SVG; the plan briefing above already covers tasks.
    style = markup[markup.index("<style>"):markup.index("</style>") + 8]
    cases = markup[markup.index('<section class="sr-section sr-cases">'):]
    cases = cases.replace("공개 SIF 키워드 사례 빈도", "이번 SIF 검색에서 반환된 사례의 유형 분포")
    st.html('<section class="safety-report">' + style + cases)
    with st.expander(f"유사 사고사례 {len(rows)}건"):
        for row in rows:
            st.markdown(f"**{escape(row['title'])}**")
            st.write(row["text"])
            from preventra_ui.gateway import Evidence
            from preventra_ui.views import render_source
            render_source(Evidence(row["title"], "", row["text"], source=row["metadata"]))


def _brief_scope_options(items):
    options = {"day": "하루 전체"}
    morning = [item for item in items if item.start < time(12, 0)]
    afternoon = [item for item in items if item.start >= time(12, 0)]
    if morning:
        options["morning"] = "오전 작업"
    if afternoon:
        options["afternoon"] = "오후 작업"
    if len(items) > 1:
        for item in items:
            options[f"task:{item.work_id}"] = f"개별 작업 · {item.start:%H:%M} · {item.activity}"
    return options


def _items_in_brief_scope(items, scope):
    if scope == "morning":
        return [item for item in items if item.start < time(12, 0)]
    if scope == "afternoon":
        return [item for item in items if item.start >= time(12, 0)]
    if scope.startswith("task:"):
        work_id = scope.removeprefix("task:")
        return [item for item in items if item.work_id == work_id]
    return list(items)


def render_manager_dashboard(*, show_controls=True, show_heading=True, show_plan_change=True):
    value = st.session_state.plus_saved.snapshot
    if st.session_state.get("plus_notice"):
        st.warning(st.session_state.plus_notice)
    if not value:
        st.info("보고서를 열려면 작업계획서를 먼저 적용해 주세요.")
        return
    plan = domain.decode_plan(value["plan"])
    st.session_state.setdefault("plus_day", date.fromisoformat(value["day"]))
    day = st.session_state.plus_day
    daily = domain.daily_rows(plan, day)
    if show_controls:
        with st.container(key="plus_report_controls"):
            day_col, weather_col = st.columns([1, 1.5], gap="medium")
            with day_col:
                day = st.date_input("보고 기준일", key="plus_day", on_change=domain_day_change, disabled=ui_blocked())
            daily = domain.daily_rows(plan, day)
            location_default = " ".join(plan.site_location.split()[:3])
            st.session_state.setdefault("plus_weather_location", location_default)
            with weather_col:
                st.text_input("날씨 조회 지역 · 시/군/구", key="plus_weather_location", help="주소 전체 대신 앞의 세 행정구역 단위까지만 조회합니다.")
    else:
        st.session_state.plus_weather_location = " ".join(plan.site_location.split()[:3])

    scope_options = _brief_scope_options(daily)
    if st.session_state.get("plus_brief_scope") not in scope_options:
        st.session_state.plus_brief_scope = "day"
    selected_scope = st.session_state.plus_brief_scope
    scope_label = scope_options[selected_scope]
    if show_heading:
        st.html(f'''<section class="plus-report-hero">
      <div class="plus-report-overline">작업일 안전 브리핑 <span>·</span> {day:%Y년 %m월 %d일}</div>
      <div class="plus-report-heading"><div><h1>{escape(plan.site)}</h1><p>{escape(" · ".join(filter(None, [plan.site_location, "작업 전 관리자 확인용"])) )}</p></div>
      <span class="plus-report-badge">{escape(scope_label)}</span></div></section>''')
    if len(scope_options) > 1:
        with st.container(key="plus_brief_scope_row", horizontal=True,
                          horizontal_alignment="left", vertical_alignment="bottom"):
            st.selectbox("보고서 범위", list(scope_options),
                          format_func=lambda key: scope_options[key], key="plus_brief_scope",
                          disabled=ui_blocked())
            st.caption("오전·오후는 작업 시작 시각을 기준으로 나뉩니다.")
    selected_scope = st.session_state.get("plus_brief_scope", "day")
    scope_label = scope_options.get(selected_scope, "하루 전체")
    items = _items_in_brief_scope(daily, selected_scope)
    st.session_state.plus_brief_scope_label = scope_label
    st.session_state.plus_brief_work_ids = tuple(item.work_id for item in items)
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
    st.markdown('<div class="plus-divider"></div>', unsafe_allow_html=True)
    _render_plan_brief(plan, day, items, scope_label)
    st.markdown("#### 작업 시간표")
    st.plotly_chart(plan_timeline(items, day), width="stretch",
                    config={"displayModeBar": False}, key="plus_plan_timeline")
    st.caption("작업계획서의 시작·종료 시각입니다. 실제 수행 여부나 위험도를 나타내지 않습니다.")
    with st.expander("전체 작업·출처 확인"):
        from preventra_plan.ui import _table
        st.dataframe([{**row, "안전조치": item.planned_controls, "시작 전 확인": item.follow_up,
                       "담당": item.owner, "미기재": ", ".join(domain.missing_work_fields(item))}
                      for row, item in zip(_table(items), items)], hide_index=True, width="stretch")
    pairs = domain.coordination_candidates(plan.items, day)
    selected_ids = {item.work_id for item in items}
    relevant_pairs = [(a, b, reasons) for a, b, reasons in pairs
                      if a.work_id in selected_ids or b.work_id in selected_ids]
    if relevant_pairs:
        with st.expander(f"동시작업 조정 확인 · {len(relevant_pairs)}개 조합", expanded=True):
            for a, b, reasons in relevant_pairs[:20]:
                st.write(f"{a.activity} ({a.work_id}) / {b.activity} ({b.work_id}): " + ", ".join(reasons))
            if len(relevant_pairs) > 20:
                st.caption("앞 20개 조합을 표시합니다. 전체 일정에서 나머지 작업도 확인하세요.")
    st.markdown("#### 현장 날씨")
    _render_optional_weather(plan, day)
    _render_case_candidates(items, day)
    st.caption("출처: 적용한 작업계획서. 기상과 사고사례는 조회한 경우에만 추가됩니다.")
    st.button("선택 작업 주의사항 질문하기", key="plus_ask", type="primary",
              on_click=_ask_about_selection, width="stretch")
    if show_plan_change:
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
    context = current_context()
    work_plan = context.get("work_plan") or {}
    selected_ids = set(st.session_state.get("plus_brief_work_ids", ()))
    if selected_ids and work_plan.get("plan"):
        plan = work_plan["plan"]
        work_plan["plan"] = {**plan, "items": [item for item in plan.get("items", [])
                                                   if item.get("work_id") in selected_ids]}
        work_plan["work_id"] = None
    scope = st.session_state.get("plus_brief_scope_label", "하루 전체")
    state.queue_question(f"선택한 범위({scope})의 작업에 맞춰 안전교육에서 다룰 주요 주의사항과 확인 항목을 근거 자료와 함께 정리해 주세요.",
                         context=context,
                         destination="홈" if st.session_state.preventra_page == "홈" else "안전 어시스턴트")


def plan_timeline(items, day):
    figure = _base_figure()
    labels = [f"{item.activity} · {item.work_id}" for item in items]
    starts = [datetime.combine(day, item.start) for item in items]
    ends = [datetime.combine(day, item.end) for item in items]
    figure.add_trace(go.Bar(
        y=labels, x=[(end - start).total_seconds() * 1000 for start, end in zip(starts, ends)],
        base=starts, orientation="h", marker_color="#6a9fd7",
        customdata=[[f"{item.start:%H:%M}–{item.end:%H:%M}", item.area,
                     f"{item.sheet} {item.row}행"] for item in items],
        hovertemplate="%{y}<br>%{customdata[0]} · %{customdata[1]}<br>%{customdata[2]}<extra></extra>",
    ))
    figure.update_layout(height=max(240, min(900, 80 + 38 * len(items))), showlegend=False)
    figure.update_xaxes(type="date", tickformat="%H:%M", title="계획 시각")
    figure.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    return figure


def plan_brief_payload(plan, day, items, scope_label):
    tasks = []
    for item in items:
        missing = domain.missing_work_fields(item)
        check = item.follow_up or "시작 전 확인사항 미기재"
        if missing:
            check += " · 미기재: " + ", ".join(missing)
        tasks.append({
            "time": f"{item.start:%H:%M}–{item.end:%H:%M}", "area": item.area,
            "activity": item.activity, "equipment": item.equipment,
            "controls": item.planned_controls or "계획 안전조치 미기재", "check": check,
            "source": f"작업계획서 · {item.sheet} {item.row}행 · {item.work_id}",
            "detail": f"장비: {item.equipment or '미기재'} / 담당: {item.owner or '미기재'} / "
                      f"안전조치: {item.planned_controls or '미기재'} / 확인: {check}",
        })
    return {
        "date": f"{day:%Y.%m.%d}", "weekday": "월화수목금토일"[day.weekday()] + "요일",
        "site": plan.site, "location": plan.site_location, "scope": scope_label,
        "summary": f"{scope_label} 작업 {len(items)}건. 계획된 안전조치와 미기재 항목을 작업 전에 확인하세요.",
        "tasks": tasks, "season": _season(day),
        "season_note": "계획서에 기재된 내용입니다. 현장 이행 여부는 별도로 확인하세요.",
        "weather_label": "아래에서 현장 날씨 조회 가능",
    }


def _render_plan_brief(plan, day, items, scope_label):
    from preventra_plan.vendor.briefing_report import safety_briefing_html
    st.html(safety_briefing_html(plan_brief_payload(plan, day, items, scope_label), show_cases=False))


def _render_optional_weather(plan, day):
    location = st.session_state.get("plus_weather_location") or " ".join(plan.site_location.split()[:3])
    key = (location, day.isoformat())
    requested = st.button("날씨 불러오기·갱신", key="plus_load_weather", disabled=ui_blocked())
    weather = None
    if requested:
        with st.spinner("선택한 날짜의 지역 날씨를 확인하고 있습니다…"):
            weather = weather_for_day(location, day.isoformat())
        st.session_state.plus_report_weather = {"key": key, "weather": weather}
    elif st.session_state.get("plus_report_weather", {}).get("key") == key:
        weather = st.session_state.plus_report_weather["weather"]
    if weather is None:
        st.caption("계획서 보고서는 준비됐습니다. 지역 예보가 필요하면 불러오세요.")
        return
    if weather.get("status") == "ok":
        temp, rain, wind = _weather_summary(weather)
        metrics = (("현장 위치", weather.get("place") or location), ("기온", temp), ("강수", rain), ("바람", wind))
        st.html('<div class="plus-weather-strip">' + "".join(
            f'<div><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'
            for label, value in metrics) + '</div>')
        st.caption(f"출처: Open-Meteo · {weather.get('source', '')} · {day:%Y-%m-%d}")
        st.info(_weather_brief(weather, _season(day)))
    elif weather.get("status") == "out_of_range":
        st.info("선택한 날짜가 예보 제공 범위를 벗어났습니다. 현장 예보를 확인해 주세요.")
    else:
        st.info("날씨를 불러오지 못했습니다. 계획 보고서는 계속 이용할 수 있습니다.")
