"""Home starts a conversation; follow-ups use the unchanged shared state API."""
import streamlit as st
from preventra_ui import state


def start_from_home(question):
    question = question.strip()
    if not question:
        st.session_state.preventra_input_notice = "질문을 입력해 주세요."
        return
    if st.session_state.preventra_pending:
        return
    # The shared callback protects unsaved turns and handles connection failures.
    previous = st.session_state.preventra_conversation_id
    state.new_chat()
    if st.session_state.preventra_conversation_id == previous:
        st.session_state.preventra_input_notice = "새 대화를 시작하지 못했습니다. 사이드바의 저장·연결 안내를 확인해 주세요."
        return
    state.queue_question(question)


def submit_home():
    start_from_home(st.session_state.get("preventra_home_question", ""))
