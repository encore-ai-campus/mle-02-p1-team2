"""Presentation only: reuse durable history, dispatch, evidence and statistics."""
from pathlib import Path
import streamlit as st

from preventra_ui import state
from preventra_ui import views as original
from preventra_ui.statistics_view import render_statistics_banner
from preventra_ui_v2.actions import start_from_home, submit_home

ROOT = Path(__file__).resolve().parent


def apply_style():
    st.html(ROOT / "styles.css")


def render_sidebar():
    # Same database, callbacks, save retry and recent-conversation ordering.
    original.render_sidebar()


def render_header():
    with st.container(key="pv2_header", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.html('<div class="pv2-brand">Preventra<span aria-hidden="true"> ◈</span></div>')
        with st.container(key="pv2_menu", horizontal=True, width="content", gap="medium"):
            for page in ("홈", "데이터·출처"):
                st.button(page, key=f"pv2_nav_{page}", type="tertiary", on_click=state.navigate, args=(page,),
                          help="현재 화면" if st.session_state.preventra_page == page else None)


def render_home():
    with st.container(key="pv2_hero", horizontal=True, gap="large", vertical_alignment="center"):
        with st.container(width=500, key="pv2_message"):
            st.html('''<section class="pv2-hero-copy">
                <div class="pv2-eyebrow">Preventra Safety Intelligence</div>
                <h1>Learn from incidents.<br><span>Prevent accidents.</span></h1>
                <p>실제 사고사례, 안전기술 가이드와 산업재해 통계를 연결해<br class="pv2-desktop-break"> 현장의 판단을 돕습니다.</p>
                </section>''')
        with st.container(width=450, key="pv2_question_area"):
            with st.container(key="pv2_question"):
                st.html('<div class="pv2-eyebrow">ASK PREVENTRA</div>')
                st.markdown("### 어떤 작업을 준비하고 있나요?")
                with st.form("pv2_home_form", clear_on_submit=True, border=False):
                    st.text_area("작업 상황이나 안전 질문", label_visibility="collapsed", height=110,
                                 placeholder="예: 지게차로 자재를 옮기기 전, 무엇을 확인해야 할까요?",
                                 key="preventra_home_question", max_chars=4000)
                    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
                        st.caption("사고사례 · 안전가이드 · 산업재해 통계")
                        st.form_submit_button("질문 보내기", on_click=submit_home, type="primary", icon=":material/arrow_upward:")
            if st.session_state.preventra_input_notice:
                st.info(st.session_state.preventra_input_notice)
            with st.container(key="pv2_examples", horizontal=True, gap="small"):
                for question in original.EXAMPLES:
                    st.button(question, key=f"pv2_example_{question}", type="tertiary", on_click=start_from_home,
                              args=(question,), icon=":material/north_east:", icon_position="right")
            st.caption("새 대화로 시작합니다. 이전 질문은 사이드바의 최근 대화에서 이어가세요.")
    with st.container(key="pv2_help", horizontal=True, gap="large"):
        with st.container(width=300):
            st.html('<div class="pv2-eyebrow">HOW WE HELP</div><h2 class="pv2-section-title">자료를 넘어,<br>작업의 맥락으로.</h2>')
        with st.container(width=650):
            for number, title, body in (
                ("01", "사고에서 배우기", "유사한 사고의 상황과 원인을 살펴보고, 현장에서 놓치기 쉬운 위험을 찾아봅니다."),
                ("02", "작업 전에 확인하기", "작업과 장비에 맞는 안전기술 가이드를 찾아, 점검과 예방조치의 근거를 확인합니다."),
                ("03", "숫자로 이해하기", "산업과 사업장 규모에 따른 재해 현황을 읽고, 연도별 변화를 살펴봅니다."),
            ):
                # All strings in this HTML are authored constants, never model/user data.
                st.html(f'<article class="pv2-service-row"><span>{number}</span><div><h3>{title}</h3><p>{body}</p></div></article>')
    with st.container(key="pv2_statistics"):
        render_statistics_banner()
    st.html('''<footer class="pv2-principles"><div class="pv2-eyebrow">Our Principles</div>
      <h3>근거를 확인하고, 맥락을 이해하고, 예방으로 연결합니다.</h3>
      <p>Preventra는 출처를 확인할 수 있는 정보와 읽기 쉬운 데이터로 현장의 판단을 돕고자 합니다.</p>
      <p>Preventra는 산업안전 정보 활용을 위한 가상 기업·교육 프로젝트입니다.</p></footer>''')


def render_assistant():
    with st.container(key="pv2_chat"):
        with st.container(key="pv2_chat_heading"):
            st.markdown("### Preventra Safety Assistant")
            st.caption("작업의 맥락을 이어가고, 답변에 사용된 근거를 확인하세요.")
        if st.session_state.preventra_input_notice:
            st.info(st.session_state.preventra_input_notice)
        if not st.session_state.preventra_turns and not st.session_state.preventra_pending:
            with st.container(key="pv2_empty"):
                st.markdown("## 오늘의 작업을 함께 살펴볼까요?")
                st.write("작업명, 사용하는 장비, 궁금한 점을 알려주세요.")
                for question in original.EXAMPLES[:2]:
                    st.button(question, key=f"pv2_empty_{question}", type="tertiary",
                              on_click=state.queue_question, args=(question,), icon=":material/north_east:")
        for turn in st.session_state.preventra_turns:
            with st.chat_message("user"):
                st.write(turn["request"].question)
            with st.chat_message("assistant"):
                original.render_result(turn["result"], turn["request"].request_id)
        if st.session_state.preventra_pending:
            with st.chat_message("user"):
                st.write(st.session_state.preventra_pending["question"])
            with st.spinner("질문을 확인하고 필요한 자료를 찾고 있습니다…"):
                state.consume_pending()
            st.rerun()


def render_sources():
    with st.container(key="pv2_sources"):
        original.render_sources()
