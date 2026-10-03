"""Preventra UI entry point; the existing app.py remains independent."""
import streamlit as st

from preventra_ui.state import initialize, submit_chat
from preventra_ui.style import apply_style
from preventra_ui.views import render_assistant, render_home, render_navigation, render_sidebar, render_sources


def main():
    st.set_page_config(page_title="Preventra | Safety Assistant", page_icon="◈", layout="wide")
    initialize()
    apply_style()
    render_sidebar()
    with st.container(key="preventra"):
        render_navigation()
        page = st.session_state.preventra_page
        if page == "홈":
            render_home()
        elif page == "안전 어시스턴트":
            render_assistant()
        else:
            render_sources()
    # Root-level chat_input stays pinned at the bottom of the assistant screen.
    if page == "안전 어시스턴트":
        st.chat_input("작업 상황이나 궁금한 안전 정보를 입력해 주세요", key="preventra_chat_question", on_submit=submit_chat, max_chars=4000)


if __name__ == "__main__":
    main()
