"""Session-only navigation and one-time question handoff."""
from uuid import uuid4

import streamlit as st

from preventra_ui import gateway

PAGES = ("홈", "안전 어시스턴트", "데이터·출처")


def initialize():
    defaults = {
        "preventra_page": "홈",
        "preventra_session_id": str(uuid4()),
        "preventra_turns": [],
        "preventra_pending": None,
        "preventra_consumed": set(),
        "preventra_input_notice": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def navigate(page: str):
    if page not in PAGES:
        raise ValueError("Unknown Preventra page")
    st.session_state.preventra_page = page


def new_chat():
    st.session_state.preventra_session_id = str(uuid4())
    st.session_state.preventra_turns = []
    st.session_state.preventra_pending = None
    st.session_state.preventra_consumed = set()
    st.session_state.preventra_input_notice = ""
    navigate("안전 어시스턴트")


def queue_question(question: str):
    question = question.strip()
    if not question:
        st.session_state.preventra_input_notice = "질문을 입력해 주세요."
        return
    st.session_state.preventra_input_notice = ""
    st.session_state.preventra_pending = {"id": str(uuid4()), "question": question}
    navigate("안전 어시스턴트")


def submit_home():
    queue_question(st.session_state.get("preventra_home_question", ""))


def submit_chat():
    queue_question(st.session_state.get("preventra_chat_question", "") or "")


def consume_pending():
    pending = st.session_state.preventra_pending
    st.session_state.preventra_pending = None
    if not pending or pending["id"] in st.session_state.preventra_consumed:
        return
    # Consume before dispatch so reruns cannot re-submit the same event.
    st.session_state.preventra_consumed.add(pending["id"])
    request = gateway.AssistantRequest(
        request_id=pending["id"],
        session_id=st.session_state.preventra_session_id,
        question=pending["question"],
        previous_questions=tuple(turn["request"].question for turn in st.session_state.preventra_turns),
        history=tuple(gateway.ConversationTurn(turn["request"].question,
                      turn["result"].answer if turn["result"].status == "ready" else "이전 답변을 완료하지 못했습니다.")
                      for turn in st.session_state.preventra_turns),
    )
    try:
        result = gateway.dispatch(request)
    except Exception:
        # Never expose provider errors, credentials, or response bodies to the UI.
        result = gateway.AssistantResult(status="error")
    st.session_state.preventra_turns.append({"request": request, "result": result})
