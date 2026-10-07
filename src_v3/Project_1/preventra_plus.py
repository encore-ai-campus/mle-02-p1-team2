"""Preventra Plus: existing assistant with conversation-scoped work plans."""
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
if not sys.path or sys.path[0] != str(APP_DIR):
    sys.path.insert(0, str(APP_DIR))

import streamlit as st
from preventra_settings import ConfigurationError
from preventra_runtime import CloudConfigurationError, require_configuration


def main():
    st.set_page_config(page_title="Preventra Plus | Safety Intelligence", page_icon="◈",
                       layout="wide", initial_sidebar_state="auto")
    try:
        require_configuration()
    except (CloudConfigurationError, ConfigurationError) as error:
        st.error(str(error))
        st.stop()
    from preventra_ui import state
    from preventra_ui_v2 import views
    from preventra_plan import ui

    state.initialize()
    st.session_state.preventra_plus_mode = True
    ui.initialize()
    views.apply_style()
    views.render_sidebar()
    with st.container(key="pv2_app"):
        views.render_header()
        page = st.session_state.preventra_page
        if page in ("작업 기록", "관리자 대시보드"):
            state.navigate("홈")
            page = "홈"
        if page == "홈":
            ui.render_home()
        elif page == "안전 어시스턴트":
            manager = ui.is_manager()
            if manager:
                ui.render_plan()
            views.render_assistant(
                consume=ui.consume_pending,
                turn_context_renderer=ui.render_turn_context,
                title='관리자 · 작업계획 상담' if manager else '작업자 · 안전 상담',
                examples=() if manager else None)
        else:
            views.render_sources()
    if page in ("안전 어시스턴트", "관리자 대시보드"):
        st.chat_input("작업 상황이나 이어서 궁금한 점을 입력해 주세요", key="preventra_chat_question",
                      on_submit=ui.submit_chat, max_chars=4000, disabled=ui.blocked())
    elif page == "작업 기록":
        st.chat_input("이 작업에 대해 궁금한 점을 물어보세요", key="preventra_record_question",
                      on_submit=ui.submit_record_chat, max_chars=4000, disabled=ui.blocked())


if __name__ == "__main__":
    main()
