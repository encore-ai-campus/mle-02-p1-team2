"""UI selection/cache only; PostgreSQL is the durable conversation source."""
from uuid import uuid4
from copy import deepcopy
import streamlit as st
from preventra_ui import gateway
from preventra_ui.history import get_store

PAGES = ("홈", "안전 어시스턴트", "데이터·출처")
SAVE_NOTICE = "답변을 아직 저장하지 못했습니다. 화면을 닫기 전에 저장을 다시 시도해 주세요."


def initialize():
    defaults = {"preventra_page": "홈", "preventra_session_id": None,
                "preventra_conversation_id": None, "preventra_turns": [],
                "preventra_pending": None, "preventra_consumed": set(),
                "preventra_input_notice": "", "preventra_history_notice": "",
                "preventra_recent": [], "preventra_unsaved": None}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    refresh_recent()


def refresh_recent():
    try:
        st.session_state.preventra_recent = get_store().list_recent()
        if st.session_state.preventra_history_notice.startswith("대화 목록"):
            st.session_state.preventra_history_notice = ""
    except Exception:
        st.session_state.preventra_history_notice = "대화 목록을 불러오지 못했습니다. 저장소 연결을 확인한 뒤 다시 시도해 주세요."


def navigate(page):
    if page not in PAGES and page not in ("관리자 대시보드", "작업 기록"):
        raise ValueError("Unknown Preventra page")
    st.session_state.preventra_page = page


def _select(identifier, turns, destination="안전 어시스턴트"):
    st.session_state.preventra_conversation_id = identifier
    st.session_state.preventra_session_id = identifier  # Existing request interface.
    st.session_state.preventra_turns = turns
    st.session_state.preventra_pending = None
    st.session_state.preventra_consumed = set()
    st.session_state.preventra_input_notice = ""
    st.session_state.preventra_history_notice = ""
    navigate(destination)


def new_chat():
    if st.session_state.preventra_unsaved:
        st.session_state.preventra_history_notice = SAVE_NOTICE
        return
    try:
        identifier = get_store().create()
        _select(identifier, [])
        refresh_recent()
    except Exception:
        st.session_state.preventra_history_notice = "새 대화를 저장하지 못했습니다. 저장소 연결을 확인해 주세요."


def open_conversation(identifier, destination="안전 어시스턴트"):
    if st.session_state.preventra_unsaved:
        st.session_state.preventra_history_notice = SAVE_NOTICE
        return
    try:
        turns = get_store().load(identifier, touch=True)
        _select(identifier, turns, destination)
        refresh_recent()
    except Exception:
        st.session_state.preventra_history_notice = "대화를 불러오지 못했습니다. 현재 대화는 유지됩니다."


def queue_question(question, *, context=None, destination="안전 어시스턴트"):
    question = question.strip()
    if not question:
        st.session_state.preventra_input_notice = "질문을 입력해 주세요."
        return
    if st.session_state.preventra_unsaved:
        st.session_state.preventra_history_notice = SAVE_NOTICE
        return
    if st.session_state.preventra_pending:
        return
    if not st.session_state.preventra_conversation_id:
        new_chat()
        if not st.session_state.preventra_conversation_id:
            st.session_state.preventra_input_notice = "대화를 생성하지 못해 질문을 보내지 않았습니다. 잠시 후 다시 시도해 주세요."
            return
    st.session_state.preventra_input_notice = ""
    st.session_state.preventra_pending = {"id": str(uuid4()), "question": question, "context": deepcopy(context)}
    navigate(destination)


def submit_home():
    queue_question(st.session_state.get("preventra_home_question", ""))


def submit_chat():
    queue_question(st.session_state.get("preventra_chat_question", "") or "")


def _turns_for_context(turns, context):
    selected_day = (context.get("work_plan") or {}).get("day")
    if selected_day:
        return [turn for turn in turns
                if (turn["request"].context.get("work_plan") or {}).get("day") == selected_day]
    return [turn for turn in turns if not turn["request"].context.get("work_plan")]


def retry_save():
    turn = st.session_state.preventra_unsaved
    if not turn:
        refresh_recent()
        return
    try:
        get_store().save_turn(turn["request"], turn["result"])
        st.session_state.preventra_unsaved = None
        st.session_state.preventra_history_notice = ""
        refresh_recent()
    except Exception:
        st.session_state.preventra_history_notice = SAVE_NOTICE


def consume_pending(*, request_context=None, dispatcher=None):
    pending = st.session_state.preventra_pending
    st.session_state.preventra_pending = None
    if not pending or pending["id"] in st.session_state.preventra_consumed:
        return
    st.session_state.preventra_consumed.add(pending["id"])
    try:
        turns = get_store().load(st.session_state.preventra_conversation_id)
    except Exception:
        st.session_state.preventra_input_notice = "이전 대화를 읽지 못해 질문을 실행하지 않았습니다. 다시 입력해 주세요."
        return
    st.session_state.preventra_turns = turns
    if any(t["request"].request_id == pending["id"] for t in turns):
        return
    request_context = deepcopy(pending.get("context") if pending.get("context") is not None
                               else request_context or {})
    history_turns = _turns_for_context(turns, request_context)
    request = gateway.AssistantRequest(
        pending["id"], st.session_state.preventra_conversation_id, pending["question"],
        context=request_context,
        previous_questions=tuple(t["request"].question for t in history_turns),
        history=tuple(gateway.ConversationTurn(t["request"].question,
                      t["result"].answer if t["result"].status == "ready" else "이전 답변을 완료하지 못했습니다.")
                      for t in history_turns))
    try:
        result = (dispatcher or gateway.dispatch)(request)
    except Exception:
        result = gateway.AssistantResult(status="error")
    turn = {"request": request, "result": result}
    st.session_state.preventra_turns.append(turn)
    st.session_state.preventra_unsaved = turn
    retry_save()
