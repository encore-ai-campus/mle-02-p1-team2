"""Presentation only: reuse durable history, dispatch, evidence and statistics."""
from pathlib import Path
import streamlit as st

from preventra_ui import state
from preventra_ui import views as original
from preventra_ui.statistics_view import render_statistics_banner
from preventra_ui_v2.actions import start_from_home, submit_home
from preventra_ui_v2.presentation import for_display

ROOT = Path(__file__).resolve().parent


def apply_style():
    st.html(ROOT / "styles.css")


def _turns_for_workday(turns, selected_day):
    if not selected_day:
        return list(turns)
    day_iso = selected_day.isoformat() if hasattr(selected_day, "isoformat") else str(selected_day)
    return [turn for turn in turns
            if (turn["request"].context.get("work_plan") or {}).get("day") == day_iso]


def _work_title_key(title):
    return "".join(str(title).casefold().split())


def render_sidebar():
    # Presentation only: keep the same database, ordering and state callbacks.
    from preventra_plan import ui as plan_ui
    manager_workspace = (st.session_state.get("preventra_plus_mode") and
                        st.session_state.get("plus_home_role", "관리자") == "관리자")
    with st.sidebar, st.container(key="preventra_sidebar"):
        st.html('<div class="pv-brand">Preventra<span aria-hidden="true"> ◈</span></div>')
        st.caption("SAFETY WORKSPACE")
        st.button("새 작업 등록" if manager_workspace else "새 대화",
                  key="preventra_new_chat", on_click=plan_ui.new_workspace_chat,
                  type="primary", width="stretch")
        work_groups = {}
        for item in st.session_state.preventra_recent:
            if getattr(item, "record_type", "chat") == "work":
                work_groups.setdefault(_work_title_key(item.title), []).append(item)
        visible_recent = (len(work_groups) if manager_workspace else sum(
            getattr(item, "record_type", "chat") != "work" and getattr(item, "has_messages", False)
            for item in st.session_state.preventra_recent))
        with st.container(key="pv2_recent_heading", horizontal=True,
                          horizontal_alignment="distribute", vertical_alignment="center"):
            st.markdown("### 작업 목록" if manager_workspace else "### 최근 대화")
            st.caption(str(visible_recent))
        if st.session_state.preventra_history_notice:
            st.warning(st.session_state.preventra_history_notice)
            st.button("저장 다시 시도" if st.session_state.preventra_unsaved else "목록 새로고침",
                      key="preventra_retry_save", on_click=state.retry_save, width="stretch",
                      )
        with st.container(key="pv2_recent_list", gap="small"):
            if visible_recent == 0:
                if manager_workspace:
                    st.html('<div class="pv2-history-empty"><strong>등록된 작업이 없습니다</strong>'
                            '<p>작업계획서를 올리면<br>공사별 날짜 기록이 여기에 모입니다.</p></div>')
                else:
                    st.html('<div class="pv2-history-empty"><strong>첫 질문을 기다리고 있어요</strong>'
                            '<p>대화를 시작하면 이곳에서<br>언제든 이어갈 수 있습니다.</p></div>')
            for conversation in st.session_state.preventra_recent:
                selected = conversation.conversation_id == st.session_state.preventra_conversation_id
                is_work = getattr(conversation, "record_type", "chat") == "work"
                if manager_workspace and not is_work:
                    continue
                if not manager_workspace and is_work:
                    continue
                if not is_work and not getattr(conversation, "has_messages", False):
                    continue
                if is_work:
                    group = work_groups[_work_title_key(conversation.title)]
                    canonical = group[0]
                    if conversation.conversation_id != canonical.conversation_id:
                        continue
                    identifier = conversation.conversation_id
                    active_id = st.session_state.get("plus_selected_record_id") or st.session_state.preventra_conversation_id
                    group_ids = {item.conversation_id for item in group}
                    expanded_ids = st.session_state.get("plus_expanded_records", set())
                    expanded = bool(group_ids & expanded_ids) or active_id in group_ids
                    with st.container(key=f"preventra_work_record_{identifier}"):
                        st.button(conversation.title, key=f"preventra_conversation_{identifier}",
                                  on_click=plan_ui.open_work_record, args=(identifier,),
                                  width="stretch", type="primary" if active_id in group_ids else "tertiary",
                                  help=f"{conversation.title} · 작업 기록 열기")
                        if expanded:
                            day_sources = {}
                            for member in group:
                                for day in getattr(member, "work_days", ()) or ():
                                    day_sources.setdefault(day, member.conversation_id)
                            days = tuple(sorted(day_sources))
                            if days:
                                st.html('<div class="plus-workday-label">날짜별 브리핑 · 작업 상세 · 대화</div>')
                                current_day = st.session_state.get("plus_day") if active_id in group_ids else None
                                weekdays = ("월", "화", "수", "목", "금", "토", "일")
                                for day in days:
                                    day_value = day.isoformat()
                                    st.button(f"{day:%m.%d} · {weekdays[day.weekday()]}요일",
                                              key=f"preventra_workday_{identifier}_{day_value}",
                                              on_click=plan_ui.open_workday, args=(day_sources[day], day_value),
                                              width="stretch", type="primary" if day == current_day else "tertiary",
                                              help=f"{day:%Y년 %m월 %d일} 보고서·작업 상세·대화 열기")
                            else:
                                st.caption("날짜 정보를 불러오는 중입니다")
                else:
                    st.button(conversation.title, key=f"preventra_conversation_{conversation.conversation_id}",
                              on_click=state.open_conversation, args=(conversation.conversation_id, "안전 어시스턴트"),
                              width="stretch", type="primary" if selected else "tertiary",
                              help=f"{conversation.title} · 최근 사용: {conversation.updated_at:%Y-%m-%d %H:%M %Z}")
    if manager_workspace:
        with st.container(key="preventra_float_home"):
            st.button("홈", key="preventra_home_icon", on_click=state.navigate,
                      args=("홈",), type="tertiary", icon=":material/home:", help="홈")


def render_header():
    with st.container(key="pv2_header", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.html('<div class="pv2-brand">Preventra<span aria-hidden="true"> ◈</span></div>')
        with st.container(key="pv2_menu", horizontal=True, width="content", gap="medium"):
            pages = ("홈", "데이터·출처")
            for page in pages:
                st.button(page, key=f"pv2_nav_{page}",
                          type="primary" if st.session_state.preventra_page == page else "tertiary",
                          on_click=state.navigate, args=(page,),
                          help="현재 화면" if st.session_state.preventra_page == page else None)


def render_home(*, show_statistics=True, after_hero=None):
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
                        st.form_submit_button("질문 보내기", on_click=submit_home, type="primary")
            if st.session_state.preventra_input_notice:
                st.info(st.session_state.preventra_input_notice)
            with st.container(key="pv2_examples", horizontal=True, gap="small"):
                for question in original.EXAMPLES:
                    st.button(question, key=f"pv2_example_{question}", type="secondary",
                              on_click=start_from_home, args=(question,))
    if after_hero:
        after_hero()
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
    if show_statistics:
        with st.container(key="pv2_statistics"):
            render_statistics_banner()
    st.html('''<footer class="pv2-principles"><div class="pv2-eyebrow">Our Principles</div>
      <h3>근거를 확인하고, 맥락을 이해하고, 예방으로 연결합니다.</h3>
      <p>Preventra는 출처를 확인할 수 있는 정보와 읽기 쉬운 데이터로 현장의 판단을 돕고자 합니다.</p>
      <p>Preventra는 산업안전 정보 활용을 위한 가상 기업·교육 프로젝트입니다.</p></footer>''')


def render_assistant(*, consume=None, turn_context_renderer=None,
                     title="Preventra Safety Assistant", examples=None):
    with st.container(key="pv2_chat"):
        turns = st.session_state.preventra_turns
        active_plan = st.session_state.get("plus_saved")
        if (st.session_state.get("preventra_plus_mode") and active_plan and active_plan.snapshot
                and st.session_state.get("plus_loaded_id") == st.session_state.get("preventra_conversation_id")):
            turns = _turns_for_workday(turns, st.session_state.get("plus_day"))
        pending = st.session_state.preventra_pending
        if pending and st.session_state.get("preventra_plus_mode"):
            selected_day = st.session_state.get("plus_day")
            pending_day = ((pending.get("context") or {}).get("work_plan") or {}).get("day")
            if selected_day and pending_day and pending_day != selected_day.isoformat():
                pending = None
        with st.container(key="pv2_chat_heading"):
            st.markdown("### " + title)
            st.caption("선택한 작업 날짜의 대화와 답변 근거를 확인하세요." if turns or pending
                       else "이 날짜의 작업에 대해 질문하고, 답변 근거를 확인하세요.")
        if st.session_state.preventra_input_notice:
            st.info(st.session_state.preventra_input_notice)
        if not turns and not pending:
            with st.container(key="pv2_empty"):
                st.markdown("## 오늘의 작업을 함께 살펴볼까요?")
                st.write("위에서 계획 기준일과 작업을 고른 뒤 아래에 질문해 주세요." if examples == ()
                         else "작업명, 사용하는 장비, 궁금한 점을 알려주세요.")
                for question in (original.EXAMPLES[:2] if examples is None else examples):
                    st.button(question, key=f"pv2_empty_{question}", type="tertiary",
                              on_click=state.queue_question, args=(question,))
        for turn in turns:
            with st.chat_message("user"):
                st.write(turn["request"].question)
            with st.chat_message("assistant"):
                original.render_result(for_display(turn["result"]), turn["request"].request_id)
                if turn_context_renderer:
                    turn_context_renderer(turn)
        if pending:
            with st.chat_message("user"):
                st.write(pending["question"])
            with st.spinner("질문을 확인하고 필요한 자료를 찾고 있습니다…"):
                (consume or state.consume_pending)()
            st.rerun()


def render_sources():
    with st.container(key="pv2_sources"):
        # The current shared view already displays the project scope and data notice.
        original.render_sources()
