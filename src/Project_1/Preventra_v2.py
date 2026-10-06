"""Integrated Preventra UI. Original entry points and services stay independent."""
import streamlit as st

from preventra_ui import state
from preventra_ui_v2.views import apply_style, render_header, render_home, render_assistant, render_sidebar, render_sources


def main():
    st.set_page_config(page_title="Preventra | Safety Intelligence", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")
    state.initialize()
    apply_style()
    render_sidebar()
    with st.container(key="pv2_app"):
        render_header()
        page = st.session_state.preventra_page
        if page == "홈":
            render_home()
        elif page == "안전 어시스턴트":
            render_assistant()
        else:
            render_sources()
    if page == "안전 어시스턴트":
        st.chat_input("작업 상황이나 이어서 궁금한 점을 입력해 주세요", key="preventra_chat_question",
                      on_submit=state.submit_chat, max_chars=4000,
                      disabled=st.session_state.preventra_unsaved is not None)


if __name__ == "__main__":
    main()
