"""Preventra screens and optional answer sections."""
import streamlit as st

from preventra_ui.gateway import AssistantResult
from preventra_ui.state import PAGES, consume_pending, navigate, new_chat, open_conversation, queue_question, retry_save, submit_home
from preventra_ui.statistics_view import render_loaded_coverage, render_statistics_banner

EXAMPLES = ("지게차 사고사례", "고소작업 전 확인사항", "우리 업종의 사고 추이")


def render_sidebar():
    with st.sidebar, st.container(key="preventra_sidebar"):
        st.html('<div class="pv-brand">Preventra<span> ◈</span></div>')
        st.caption("현장의 판단을 돕는 안전 정보")
        st.button("＋ 새 대화", key="preventra_new_chat", on_click=new_chat, type="primary", width="stretch")
        st.caption("새 대화를 시작해도 저장된 대화는 유지됩니다.")
        st.divider()
        st.markdown("### 최근 대화")
        if st.session_state.preventra_history_notice:
            st.warning(st.session_state.preventra_history_notice)
            st.button("저장 다시 시도" if st.session_state.preventra_unsaved else "목록 새로고침",
                      key="preventra_retry_save", on_click=retry_save, width="stretch")
        if not st.session_state.preventra_recent:
            st.caption("아직 저장된 대화가 없습니다.")
        for conversation in st.session_state.preventra_recent:
            st.button(conversation.title, key=f"preventra_conversation_{conversation.conversation_id}",
                      on_click=open_conversation, args=(conversation.conversation_id,), width="stretch",
                      type="primary" if conversation.conversation_id == st.session_state.preventra_conversation_id else "secondary",
                      help=f"최근 사용: {conversation.updated_at:%Y-%m-%d %H:%M %Z}")
        st.caption("이 작업공간의 최근 대화 · 최대 50개")
        st.button("홈으로 돌아가기", key="preventra_sidebar_home", on_click=navigate, args=("홈",), width="stretch")


def render_navigation():
    brand, navigation = st.columns([1, 2])
    with brand:
        st.html('<div class="pv-brand">Preventra<span> ◈</span></div>')
    with navigation:
        for column, page in zip(st.columns(3), PAGES):
            column.button(page, key=f"preventra_nav_{page}", on_click=navigate, args=(page,), width="stretch", type="primary" if st.session_state.preventra_page == page else "secondary")
    st.divider()


def render_home():
    st.html('''<section class="pv-hero">
      <div class="pv-eyebrow">Preventra Safety Intelligence</div>
      <h1>Learn from incidents.<br><span>Prevent accidents.</span></h1>
      <p>실제 사고사례, 안전기술 가이드와 산업재해 통계를 연결해<br>
      현장의 판단을 돕습니다.</p>
    </section>''')
    with st.form("preventra_home_form", clear_on_submit=True):
        st.text_input("어떤 작업의 안전 정보가 필요한가요?", placeholder="작업·장비 또는 궁금한 사고사례를 입력해 주세요", key="preventra_home_question", max_chars=4000)
        st.form_submit_button("안전 어시스턴트에서 질문하기 →", on_click=submit_home, type="primary", width="stretch")
    if st.session_state.preventra_input_notice:
        st.info(st.session_state.preventra_input_notice)
    st.caption("질문으로 시작해 보세요 · 필요한 사고사례·안전가이드·통계를 찾아 출처와 함께 답합니다.")
    for column, question in zip(st.columns(3), EXAMPLES):
        column.button(question, key=f"preventra_example_{question}", on_click=queue_question, args=(question,), width="stretch")
    st.write("")
    cards = (
        ("01 / INCIDENTS", "사고에서 배우기", "유사한 사고의 상황과 원인을 살펴보고, 현장에서 놓치기 쉬운 위험을 찾아봅니다."),
        ("02 / GUIDANCE", "작업 전에 확인하기", "작업과 장비에 맞는 안전기술 가이드를 찾아, 점검과 예방조치의 근거를 확인합니다."),
        ("03 / STATISTICS", "숫자로 이해하기", "산업과 사업장 규모에 따른 재해 현황을 읽고, 연도별 변화를 살펴봅니다."),
    )
    for column, (label, title, body) in zip(st.columns(3, gap="medium"), cards):
        with column:
            st.html(f'<article class="pv-card"><div class="pv-eyebrow">{label}</div><h3>{title}</h3><p>{body}</p></article>')
    st.write("")
    st.divider()
    render_statistics_banner()
    st.html('''<footer class="pv-footer"><div class="pv-eyebrow">Our Principles</div>
      <h3>근거를 확인하고, 맥락을 이해하고, 예방으로 연결합니다.</h3>
      <p>Preventra는 출처를 확인할 수 있는 정보와 읽기 쉬운 데이터로 현장의 판단을 돕고자 합니다.</p>
      <p>Preventra는 산업안전 정보 활용을 위한 가상 기업·교육 프로젝트입니다.</p></footer>''')


def render_source(item):
    labels = {"source": "자료", "doc_id": "사례 ID", "guide_id": "GUIDE ID", "title": "문서명",
              "section": "절", "page": "PDF 페이지", "sheet": "시트", "row_number": "연번"}
    for key, label in labels.items():
        if item.source.get(key):
            st.write(f"{label}: {item.source[key]}")
    if item.location:
        st.caption(item.location)
    url = item.source.get("source_url")
    if url and url.startswith("https://"):
        st.link_button("원문 출처 열기", url)


def render_cases(cases):
    st.markdown("#### 관련 사고사례")
    for case in cases:
        with st.container(border=True):
            st.write(f"[{case.reference}] {case.title}")
            st.write(case.excerpt[:500])
            with st.expander("사고사례 원문·출처 확인"):
                st.write(case.excerpt)
                render_source(case)


def render_guides(guides):
    st.markdown("#### 안전가이드 근거")
    for guide in guides:
        with st.expander(f"[{guide.reference}] {guide.title}"):
            st.write(guide.excerpt)
            render_source(guide)


def render_result(result: AssistantResult, request_id=""):
    if result.status == "not_connected":
        st.caption("질문 전달 완료 · 답변 기능 연결 준비 중")
        return
    if result.status == "error":
        st.warning(result.answer or "질문은 유지했지만 답변을 처리하지 못했습니다. 잠시 후 새 질문으로 다시 시도해 주세요.")
        return
    if result.answer:
        st.write(result.answer)
    if result.plan_sources:
        st.markdown("작업계획서 근거")
        for item in result.plan_sources:
            with st.expander(f"[{item.reference}] {item.title}"):
                st.write(item.excerpt)
                if item.source:
                    st.json(item.source)
    if result.cases:
        render_cases(result.cases)
    if result.guides:
        render_guides(result.guides)
    if result.figures:
        st.markdown("#### 관련 통계")
        for index, figure in enumerate(result.figures):
            st.plotly_chart(figure, width="stretch", key=f"preventra_answer_{request_id}_{index}")
        st.caption(result.statistics_caption)
    elif result.statistics_caption:
        with st.expander("통계 출처·집계 범위"):
            st.caption(result.statistics_caption)


def render_assistant(*, consume=consume_pending):
    st.html('<div class="pv-eyebrow">Your Safety Workspace</div>')
    st.title("Preventra Safety Assistant")
    st.write("작업 상황을 설명하거나 사고사례·안전가이드·통계에 대해 질문해 주세요.")
    st.caption("필요한 자료만 찾아 답합니다. 문서의 적용 범위와 출처를 함께 확인해 주세요.")
    if st.session_state.preventra_input_notice:
        st.info(st.session_state.preventra_input_notice)
    if not st.session_state.preventra_turns and not st.session_state.preventra_pending:
        with st.container(height=250, border=False):
            st.markdown("### 현장의 질문에서 시작하세요")
            st.write("작업명, 사용하는 장비, 궁금한 점을 함께 적어 주세요.")
            st.caption("예: 지게차로 자재를 옮기기 전에 어떤 점을 확인해야 하나요?")
    for turn in st.session_state.preventra_turns:
        with st.chat_message("user"):
            st.write(turn["request"].question)
        with st.chat_message("assistant"):
            render_result(turn["result"], turn["request"].request_id)
    if st.session_state.preventra_pending:
        with st.chat_message("user"):
            st.write(st.session_state.preventra_pending["question"])
        with st.spinner("질문을 확인하고 필요한 자료를 찾고 있습니다…"):
            consume()
        st.rerun()


def render_sources():
    st.html('<div class="pv-eyebrow">Data & Sources</div>')
    st.title("데이터·출처")
    st.write("프로젝트에서 확인한 자료의 범위와 한계를 함께 안내합니다.")
    st.caption("아래 검색 자료의 수량은 프로젝트 기록 기준입니다. 현재 DB의 적재 수량이나 검색 가능 여부를 실시간 조회한 결과는 아닙니다.")
    with st.container(border=True):
        st.subheader("SIF · 실제 산업재해 사고사례")
        st.write("한국산업안전보건공단의 산업재해 고위험요인(SIF) 아카이브를 바탕으로 작업 상황, 위험요인과 예방조치를 살펴보는 사례 자료입니다.")
        st.write("Project_1의 원본 파일명은 ‘한국산업안전보건공단_산업재해 고위험요인(SIF) 아카이브_20260401.xlsx’입니다. Day 13 검색 품질 점검 기록의 검색 대상은 SIF 24건입니다. 전체 아카이브를 포함하지 않으며 작업·장비별 사례가 부족할 수 있습니다.")
        st.caption("출처 식별: 문서 ID · 원본 파일 · 시트 · 연번. 파일명의 날짜를 사고 발생 기간으로 해석하지 않습니다. 검색 후보가 곧 답변에 채택된 근거는 아닙니다.")
        st.link_button("SIF 원자료 안내", "https://www.data.go.kr/data/15140383/fileData.do")
    with st.container(border=True):
        st.subheader("KOSHA GUIDE · 안전기술 가이드")
        st.write("프로젝트 수집 목록에는 공식 PDF 18건이 기록되어 있습니다. 지게차, 굴착기, 크레인·줄걸이, 고소작업대, 작업발판·비계·사다리, 용접·용단, 전기작업 관련 자료입니다.")
        st.write("수집 목록의 확인일은 2026-09-30이며, GUIDE 식별번호 기준 연도는 2015~2026년입니다. Day 13 점검 기록에는 검색용 청크 813개가 기재되어 있습니다. 일부 PDF의 OCR 오탈자와 절 구분 오류가 있어 문서 ID·절·PDF 페이지를 원문과 대조해야 합니다.")
        st.caption("수집 범위 밖의 작업에 해당하는 GUIDE는 없을 수 있습니다. 현재 개정·폐지 상태와 적용 범위는 공식 원문에서 다시 확인하세요.")
        st.link_button("KOSHA GUIDE 공식 조회", "https://portal.kosha.or.kr/archive/resources/tech-support/search/all")
    with st.container(border=True):
        st.subheader("산업재해 통계 · 산업중분류 × 사업장 규모")
        st.write("한국산업안전보건공단의 산업중분류별 규모별 CSV를 사용합니다. 프로젝트 파일 매핑은 사고재해자수·사고사망자수 2020–2025년, 사망만인율 2020년 및 2022–2025년, 사업장수 2025년입니다. 2021년 사망만인율 자료는 제공되지 않았습니다.")
        st.write("홈에서는 확보된 자료의 건수 지표만 합산합니다. 사망만인율은 단순 합산·평균하지 않으며, 누락값을 0으로 바꾸지 않습니다. 산업 분류와 포함 범위를 확인한 뒤 연도를 비교해야 합니다.")
        st.caption("현재 불러온 자료의 범위 · 연도 목록은 실제 값이 있는 연도 기준")
        render_loaded_coverage()
        links = (("사고재해자수 출처", "15084672"), ("사고사망자수 출처", "15084674"), ("사업장수 출처", "15064487"), ("사망만인율 출처", "15064491"))
        for column, (label, identifier) in zip(st.columns(4), links):
            column.link_button(label, f"https://www.data.go.kr/data/{identifier}/fileData.do", width="stretch")
        st.caption("공공데이터포털 링크는 저장소 출처 문서에 기록된 원자료 안내입니다. 과거 연도 자료는 프로젝트의 history CSV 기준이며, 이 화면에서 원자료의 최신 여부를 재검증하지는 않습니다.")
    st.caption("근거 기록: Project_1/README.md · Day13_검색품질_점검.md · data/kosha_guide 수집 목록 · services/statistics.py · 저장소 docs/data-sources.md")
    st.info("Preventra는 가상 기업·교육 프로젝트입니다. 제공 자료는 현장별 위험성평가와 담당자의 검토를 돕기 위한 참고 정보입니다.")
