"""Day 12 · SIF/KOSHA Dual RAG 기반 산업안전 AI 어시스턴트."""

import logging
from uuid import uuid4

import streamlit as st

from services.safety_rag import SafetyAnalysis, SafetyRAGConfigurationError, analyze_work, is_followup
from services.statistics import (
    SIZE_ORDER, industry_death_rate_comparison,
    industry_totals, industry_trend, kpi_value, load_statistics,
)
from services.visualization import (
    plot_death_rate_comparison, plot_industry_bar, plot_six_year_line,
)


from preventra_plan import ui as plan_ui
from preventra_ui import state as plan_state
from preventra_ui.views import render_assistant as render_plan_assistant


def open_plan_conversation():
    identifier = st.session_state.get("plan_conversation_choice")
    if identifier and identifier != st.session_state.preventra_conversation_id:
        plan_state.open_conversation(identifier)


st.set_page_config(page_title="산업안전 AI 어시스턴트", page_icon="🦺", layout="wide")
logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600, show_spinner="산업재해 통계를 불러오는 중입니다.")
def get_data():
    return load_statistics()


def reset_filters():
    """통계 조건만 초기화한다. 안전 분석 대화는 유지한다."""
    st.session_state.context_year = 2025
    st.session_state.context_industry = "전체"
    st.session_state.context_size = "전체"


def new_chat():
    """Day 5의 session_id와 호환되는 UUID로 새 대화를 시작한다."""
    st.session_state.safety_session_id = str(uuid4())
    st.session_state.safety_messages = []


def render_analysis(report: SafetyAnalysis | None):
    """생성한 분석과 검색 출처를 분리해 보여주고 상세 원문은 접어서 둔다."""
    if report is None:
        st.info("이전 대화의 분석 결과가 없습니다.")
        return

    followup = getattr(report, "followup", False)
    st.markdown("#### 이번 질문에 대한 답변" if followup else "#### 작업 및 위험요인 요약")
    st.write(report.work_summary)
    if not followup or report.intent == "위험" or not report.prevention:
        for hazard in report.hazards:
            st.write(f"• {hazard}")
    if followup and report.prevention:
        for action in report.prevention:
            st.write(f"• {action}")

    sif_col, kosha_col = st.columns(2)
    with sif_col:
        st.markdown("#### 실제 유사 사고사례 — SIF")
        if followup and report.sif_cases and report.debug.get("reused_evidence", {}).get("sif"):
            st.caption("앞선 답변에서 확인한 사고사례를 사용했습니다.")
        else:
            st.write(report.sif_summary)
        for rank, item in enumerate(report.sif_cases, 1):
            with st.expander(f"[SIF-{rank}] {item.title}"):
                st.write(f"doc_id: {item.source_id}")
                st.write(f"문서명: {item.source_file or 'SIF 아카이브'}")
                st.write(f"시트: {item.sheet or '—'} · 연번: {item.row_number or '—'}")
                st.write(item.excerpt)
    with kosha_col:
        st.markdown("#### 관련 안전기준 — KOSHA GUIDE")
        if followup and report.kosha_guides and report.debug.get("reused_evidence", {}).get("kosha"):
            st.caption("앞선 답변에서 확인한 안전기준을 사용했습니다.")
        else:
            st.write(report.kosha_summary)
        for rank, item in enumerate(report.kosha_guides, 1):
            with st.expander(f"[GUIDE-{rank}] {item.title}"):
                st.write(f"guide_id: {item.source_id}")
                st.write(f"문서명: {item.title}")
                st.write(f"section: {item.section or '—'} · page: {item.page or '—'}")
                st.write(item.excerpt)
                if item.source_url:
                    st.link_button("공식 출처", item.source_url)

    if not followup:
        st.markdown("#### 종합 예방조치")
        if report.prevention:
            for action in report.prevention:
                st.write(f"• {action}")
        else:
            st.write("검색 근거만으로 예방조치를 제시하기 어렵습니다.")
    if report.notice:
        st.info(report.notice)
    debug = getattr(report, "debug", {})
    if debug:
        with st.expander("개발용 검색 진단", expanded=False):
            st.markdown("**분석된 Query / Work Context**")
            st.json(debug.get("query", {}))
            st.caption("아래는 검색 후보입니다. SIF 점수는 모델 평가값, KOSHA 점수는 섹션·메타데이터를 더한 상대 순위값이며 최종 근거 채택과 구분됩니다.")
            st.markdown("**SIF Top 결과 · 재정렬 이유**")
            st.dataframe(debug.get("sif_top", []), hide_index=True, width="stretch")
            st.markdown("**KOSHA Top 결과 · 재정렬 이유**")
            st.dataframe(debug.get("kosha_top", []), hide_index=True, width="stretch")
            if debug.get("answer_gate"):
                st.markdown("**최종 답변의 근거 채택 판단**")
                st.json(debug["answer_gate"])
            for note in debug.get("retrieval_notes", []):
                st.caption(note)


try:
    data = get_data()
except (RuntimeError, ValueError) as exc:
    logger.error("통계 데이터 로딩 실패: %s", exc)
    st.error("통계 데이터를 불러오지 못했습니다. 저장소 연결과 데이터 준비 상태를 확인해 주세요.")
    st.stop()
years = sorted(data["연도"].unique().tolist(), reverse=True) if not data.empty else [2025]
industries = ["전체", *sorted(data["산업중분류"].unique().tolist())] if not data.empty else ["전체"]
sizes = ["전체", *SIZE_ORDER]
st.session_state.setdefault("context_year", 2025 if 2025 in years else years[0])
st.session_state.setdefault("context_industry", "전체")
st.session_state.setdefault("context_size", "전체")
if "safety_session_id" not in st.session_state:
    new_chat()
plan_state.initialize()
plan_ui.initialize()

with st.sidebar:
    st.header("통계 조건")
    st.selectbox("산업중분류", industries, key="context_industry")
    st.selectbox("연도", years, key="context_year")
    with st.expander("상세 조건"):
        st.selectbox("사업장 규모", sizes, key="context_size")
        st.button("조건 초기화", on_click=reset_filters, width="stretch")

year = st.session_state.context_year
industry = None if st.session_state.context_industry == "전체" else st.session_state.context_industry
size = None if st.session_state.context_size == "전체" else st.session_state.context_size

st.title("산업안전 AI 어시스턴트")
st.caption("작업·장비를 자연어로 설명하면 SIF 사고사례와 KOSHA GUIDE를 함께 찾아 안전 정보를 제공합니다.")
safety_tab, plan_tab, stats_tab = st.tabs(["\U0001f9ba \uc791\uc5c5 \uc548\uc804 \uc0c1\ub2f4", "\U0001f4cb \uc791\uc5c5\uacc4\ud68d \uc0c1\ub2f4", "\U0001f4ca \uc0b0\uc5c5\uc7ac\ud574 \ud604\ud669"])

with safety_tab:
    st.subheader("작업 안전 상담")
    st.caption("작업명·장비·위험요인을 자연어로 적어 주세요. 사이드바 산업분류는 답변의 보조 정보로만 사용합니다.")
    st.button("새 대화 시작", on_click=new_chat)

    for message in st.session_state.safety_messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            elif message.get("error"):
                st.error(message["error"])
            else:
                render_analysis(message["analysis"])

    question = st.chat_input("예: 고소작업대로 천장 배관을 교체합니다. 어떤 위험을 주의해야 하나요?")
    if question and question.strip():
        question = question.strip()
        previous = st.session_state.safety_messages.copy()
        try:
            status = ("이전 대화의 근거를 확인하고 있습니다..." if previous and is_followup(question)
                      else "SIF 사고사례와 KOSHA 안전기준을 찾고 있습니다...")
            with st.spinner(status):
                report = analyze_work(question, st.session_state.safety_session_id, previous, industry)
            reply = {"role": "assistant", "analysis": report}
        except SafetyRAGConfigurationError as exc:
            reply = {"role": "assistant", "error": str(exc)}
        except Exception:
            logger.exception("작업 안전 상담 처리 실패")
            reply = {"role": "assistant", "error": "지금은 안전 근거를 조회하거나 답변을 생성할 수 없습니다. 잠시 후 다시 시도해 주세요."}
        st.session_state.safety_messages.extend([
            {"role": "user", "content": question},
            reply,
        ])
        st.rerun()



with plan_tab:
    st.subheader("\uc791\uc5c5\uacc4\ud68d \uc5f0\uacc4 \uc0c1\ub2f4")
    st.caption("Excel \uacc4\ud68d\uc11c\ub97c \ud655\uc778\ud55c \ud6c4 \ub300\ud654\uc5d0 \uc5f0\uacb0\ud558\uba74, \uacc4\ud68d \ub0b4\uc6a9\uacfc SIF\u00b7KOSHA \uadfc\uac70\ub97c \ud568\uaed8 \uc9c8\uc758\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.")
    st.caption("\uacc4\ud68d \uae30\ub2a5\uc758 \uc811\uadfc \ubc94\uc704\ub294 \ubc30\ud3ec \uad8c\ud55c\uc5d0 \ub530\ub985\ub2c8\ub2e4. \uc5ed\ud560\ubcc4 \uad8c\ud55c \uc778\uc99d\uc740 \uc81c\uacf5\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.")
    if st.session_state.preventra_history_notice:
        st.warning(st.session_state.preventra_history_notice)
    recent = st.session_state.preventra_recent
    titles = {item.conversation_id: item.title for item in recent}
    current = st.session_state.preventra_conversation_id
    options = [item.conversation_id for item in recent]
    if current and current not in options:
        options.insert(0, current)
    if options:
        selected_index = options.index(current) if current in options else 0
        st.selectbox("\uacc4\ud68d \uc0c1\ub2f4 \ub300\ud654", options, index=selected_index,
                     format_func=lambda identifier: titles.get(identifier, "\ud604\uc7ac \ub300\ud654"),
                     key="plan_conversation_choice", on_change=open_plan_conversation)
    col_new, col_status = st.columns([1, 3])
    with col_new:
        st.button("\uc0c8 \uacc4\ud68d \uc0c1\ub2f4", key="plan_new_conversation",
                  on_click=plan_state.new_chat, disabled=bool(st.session_state.preventra_unsaved))
    with col_status:
        st.caption("\uacc4\ud68d\uc11c\uc640 \ub300\ud654\ub294 \uc0c1\ub2f4 \ub300\ud654\ubcc4\ub85c \uc800\uc7a5\ub429\ub2c8\ub2e4.")
    plan_ui.render_plan()
    with st.form("plan_question_form", clear_on_submit=True):
        plan_question = st.text_input("\uacc4\ud68d \uad00\ub828 \uc9c8\ubb38", max_chars=4000,
                                      placeholder="\uc608: \uc624\ub298 \uc9c0\uac8c\ucc28 \uc791\uc5c5\uc758 \uacc4\ud68d\uc0c1 \uc870\uce58\uc640 \ucd94\uac00 \ud655\uc778\uc0ac\ud56d\uc740?",
                                      key="plan_question")
        send_plan_question = st.form_submit_button("\uc9c8\ubb38 \ubcf4\ub0b4\uae30", type="primary",
                                                   disabled=plan_ui.blocked(),
                                                   key="plan_question_submit")
    if send_plan_question:
        plan_state.queue_question(plan_question, context=plan_ui.current_context())
    render_plan_assistant(consume=plan_ui.consume_pending)

with stats_tab:
    st.subheader(f"{year}년 산업재해 현황")
    st.caption(f"산업중분류: {industry or '전체'} · 사업장 규모: {size or '전체 (상세 조건)'}")
    if data.empty:
        st.info("통계 CSV를 찾지 못했습니다. data 및 data/history 폴더를 확인해 주세요.")
    else:
        injured = kpi_value(data, year, industry, size, "사고재해자수")
        deaths = kpi_value(data, year, industry, size, "사고사망자수")
        col_injured, col_deaths = st.columns(2)
        col_injured.metric("사고재해자수", "—" if injured is None else f"{injured:,.0f}")
        col_deaths.metric("사고사망자수", "—" if deaths is None else f"{deaths:,.0f}")

        st.subheader("산업별 사고재해자수·사고사망자수")
        chart_cols = st.columns(2)
        for column, metric in zip(chart_cols, ("사고재해자수", "사고사망자수")):
            totals = industry_totals(data, year, metric, size)
            with column:
                if totals.empty:
                    st.info(f"{metric} 데이터가 없습니다.")
                else:
                    st.plotly_chart(plot_industry_bar(totals, metric, industry), width="stretch")
        st.caption("막대는 산업별 건수 합계입니다. 선택 산업은 주황색으로 표시됩니다.")

        st.subheader("사고사망자수와 사망만인율 비교")
        comparison = industry_death_rate_comparison(data, year, size)
        if comparison["비교 사망만인율"].notna().any():
            st.plotly_chart(plot_death_rate_comparison(comparison, industry, size), width="stretch")
            if size is None:
                st.caption("가로축은 각 산업의 사망자수 합계, 세로축은 규모별 사망만인율의 중앙값입니다. 중앙값은 업종 전체 사망만인율이 아닙니다. 세로축은 큰 값도 보이도록 로그 눈금을 사용합니다.")
            else:
                st.caption("두 지표 모두 선택한 사업장 규모 기준입니다. 세로축은 로그 눈금이며 실제 사망만인율은 마우스를 올려 확인할 수 있습니다.")
        else:
            st.info("이 연도의 사망만인율 원본 자료가 없어 비교할 수 없습니다.")

        st.subheader("선택 산업의 2020~2025 추세")
        line_metric = st.selectbox("추세 지표", ["사고재해자수", "사고사망자수", "사망만인율"], index=1)
        if industry is None:
            st.info("사이드바에서 산업중분류를 선택하면 6년 추세를 볼 수 있습니다.")
        else:
            trend = industry_trend(data, industry, line_metric, size)
            if trend["값"].notna().sum() == 0:
                st.info("선택 산업의 해당 지표 자료가 없습니다.")
            else:
                st.plotly_chart(plot_six_year_line(trend, industry, line_metric, year, size), width="stretch")
                if line_metric == "사망만인율" and size is None:
                    st.caption("규모별 사망만인율의 중앙값 추세이며 업종 전체율을 뜻하지 않습니다.")
                missing = trend.loc[trend["값"].isna(), "연도"].tolist()
                if missing:
                    st.caption("원본 자료가 없는 연도: " + ", ".join(map(str, missing)))
