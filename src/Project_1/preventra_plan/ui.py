"""Small plan UI; durable conversations and result rendering belong to Preventra."""
from datetime import date
from hashlib import sha256
import streamlit as st
from preventra_ui import state
from preventra_plan import domain
from preventra_plan.storage import get_plan_store, SavedPlan, PlanConflict


def initialize():
    defaults = {"plus_loaded_id": None, "plus_saved": SavedPlan(), "plus_load_failed": False,
                "plus_notice": "", "plus_candidate": None, "plus_candidate_token": None,
                "plus_upload_generation": 0}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    identifier = st.session_state.preventra_conversation_id
    if identifier != st.session_state.plus_loaded_id or st.session_state.plus_load_failed:
        # Clear the previous conversation's context before attempting any remote load.
        st.session_state.plus_saved = SavedPlan()
        st.session_state.plus_load_failed = False
        st.session_state.plus_candidate = None
        st.session_state.plus_candidate_token = None
        st.session_state.plus_upload_generation += 1
        for key in ("plus_day", "plus_work"):
            st.session_state.pop(key, None)
        try:
            if identifier:
                st.session_state.plus_saved = get_plan_store().load(identifier)
            st.session_state.plus_loaded_id = identifier
        except Exception:
            st.session_state.plus_load_failed = True
            st.session_state.plus_notice = "작업계획서를 불러오지 못했습니다. 연결을 확인하고 다시 시도해 주세요."


def blocked():
    return bool(st.session_state.preventra_unsaved or st.session_state.preventra_pending
                or st.session_state.plus_load_failed)


def current_context():
    value = st.session_state.plus_saved.snapshot
    if not value or st.session_state.plus_load_failed:
        return {}
    return {"work_plan": {**value,
            "day": st.session_state.get("plus_day", date.fromisoformat(value["day"])).isoformat(),
            "work_id": st.session_state.get("plus_work") or None}}


def submit_chat():
    if blocked():
        return
    state.queue_question(st.session_state.get("preventra_chat_question", "") or "",
                         context=current_context())


def save(value):
    try:
        saved = get_plan_store().save(st.session_state.preventra_conversation_id, value,
                                      st.session_state.plus_saved.revision)
    except PlanConflict as exc:
        st.session_state.plus_load_failed = True
        st.session_state.plus_notice = str(exc)
        st.warning(st.session_state.plus_notice)
        return False
    except Exception:
        st.session_state.plus_notice = "계획을 저장하지 못했습니다. 적용 중인 계획은 유지됩니다. 다시 시도해 주세요."
        st.warning(st.session_state.plus_notice)
        return False
    st.session_state.plus_saved = saved
    st.session_state.plus_notice = ""
    return True


def apply_candidate():
    if blocked() or st.session_state.plus_candidate is None:
        return
    candidate = st.session_state.plus_candidate
    home = st.session_state.preventra_page == "홈"
    if home or not st.session_state.preventra_conversation_id:
        old = st.session_state.preventra_conversation_id
        state.new_chat()
        if old == st.session_state.preventra_conversation_id:
            return
        st.session_state.plus_loaded_id = st.session_state.preventra_conversation_id
        st.session_state.plus_saved = SavedPlan()
    value = domain.snapshot(candidate, domain.today_korea())
    if save(value):
        for key in ("plus_day", "plus_work"):
            st.session_state.pop(key, None)
        st.session_state.plus_candidate = None
        st.session_state.plus_candidate_token = None
        st.session_state.plus_upload_generation += 1
        state.navigate("안전 어시스턴트")
        st.rerun()


def _table(items):
    return [{"시간": f"{i.start:%H:%M}–{i.end:%H:%M}", "구역": i.area,
             "작업": i.activity, "장비": i.equipment or "미입력",
             "출처": f"{i.sheet} {i.row}행"} for i in items]


def render_plan():
    if st.session_state.plus_notice:
        st.warning(st.session_state.plus_notice)
    if st.session_state.plus_load_failed:
        st.button("계획 다시 불러오기", key="plus_reload")
        return
    with st.expander("작업계획서 연결 · Excel", expanded=not bool(st.session_state.plus_saved.snapshot)):
        st.caption("내용을 확인한 뒤 적용하면 이 대화에 저장됩니다. 원본 Excel 파일은 저장하지 않습니다.")
        st.download_button("빈 작업계획서 양식", domain.blank_template(), "preventra_work_plan.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        upload = st.file_uploader("작업계획서", type=["xlsx"], max_upload_size=10,
                                  key=f"plus_upload_{st.session_state.plus_upload_generation}", disabled=blocked())
        if upload is not None:
            content = upload.getvalue()
            token = sha256(content).hexdigest()
            if token != st.session_state.plus_candidate_token:
                st.session_state.plus_candidate = None
                st.session_state.plus_candidate_token = token
                try:
                    st.session_state.plus_candidate = domain.read_work_plan(content)
                except Exception:
                    st.error("계획서를 읽지 못했습니다. 10MB 이하의 .xlsx 파일과 양식의 날짜·시간·필수 열을 확인해 주세요.")
        candidate = st.session_state.plus_candidate
        if candidate:
            st.text(f"{candidate.site} · 작업 {len(candidate.items)}개")
            st.dataframe(_table(candidate.items), hide_index=True, width="stretch")
            for issue in candidate.issues:
                st.warning(issue)
            previous = st.session_state.plus_saved.snapshot
            if previous:
                changes = domain.compare_plans(domain.decode_plan(previous["plan"]), candidate)
                st.caption(f"이전 계획 대비 추가 {len(changes.added)} · 변경 {len(changes.changed)} · 제외 {len(changes.removed)}")
            acknowledge = not candidate.issues or st.checkbox("제외된 행을 확인했습니다", key="plus_ack_" + st.session_state.plus_candidate_token)
            if st.button("이 계획서 적용", key="plus_apply", type="primary", disabled=blocked() or not acknowledge):
                apply_candidate()
    value = st.session_state.plus_saved.snapshot
    if not value:
        return
    plan = domain.decode_plan(value["plan"])
    st.markdown("### 작업계획 요약")
    st.text(plan.site)
    st.session_state.setdefault("plus_day", date.fromisoformat(value["day"]))
    day = st.date_input("확인할 날짜", key="plus_day", disabled=blocked())
    items = domain.daily_rows(plan, day)
    options = [""] + [i.work_id for i in items]
    if st.session_state.get("plus_work") not in options:
        st.session_state.plus_work = ""
    labels = {i.work_id: domain.work_selection_label(i) for i in items}
    selected = st.selectbox("질문할 작업", options, format_func=lambda value: labels.get(value, "해당 날짜 전체"),
                            key="plus_work", disabled=blocked())
    if not items:
        st.info(f"{day:%Y-%m-%d}에 등록된 작업이 없습니다. 계획서의 작업일을 선택해 주세요.")
        st.caption("수록 날짜: " + ", ".join(d.isoformat() for d in sorted({i.day for i in plan.items})))
    else:
        shown = [i for i in items if not selected or i.work_id == selected]
        st.dataframe(_table(shown), hide_index=True, width="stretch")
        for item in shown[:20]:
            with st.expander(domain.work_selection_label(item), expanded=bool(selected)):
                st.caption("계획서에 적힌 내용 · 현장 이행 여부는 별도 확인")
                st.text("계획된 안전조치: " + (item.planned_controls or "미입력"))
                st.text("추가 확인: " + (item.follow_up or "미입력"))
                missing = domain.missing_work_fields(item)
                if missing:
                    st.warning("확인할 누락 항목: " + ", ".join(missing))
        if len(shown) > 20:
            st.caption("상세는 앞 20개만 표시합니다. 위에서 작업을 선택하면 해당 작업을 볼 수 있습니다.")
        pairs = domain.coordination_candidates(plan.items, day)
        if pairs:
            st.info(f"시간이 겹쳐 조정을 확인할 작업 조합 {len(pairs)}개가 있습니다. 계획만으로 위험 여부를 판정하지 않습니다.")
            with st.expander("동시 작업 확인 후보"):
                for a,b,reasons in pairs[:20]:
                    st.text(f"{a.work_id} / {b.work_id}: " + ", ".join(reasons))
        if st.button("선택한 작업의 주의점 질문", key="plus_ask", disabled=blocked()):
            state.queue_question("선택한 날짜와 작업의 계획 안전조치·누락 항목을 요약하고, 작업 전 주의점을 근거와 함께 알려줘.",
                                 context=current_context())
            st.rerun()
    if st.button("이 대화에서 계획 연결 해제", key="plus_detach", disabled=blocked()):
        if save(None):
            st.rerun()


def render_turn_context(turn):
    value = (turn["request"].context or {}).get("work_plan")
    if not value:
        return
    with st.expander("이 답변 당시의 작업계획서"):
        plan = domain.decode_plan(value["plan"])
        st.caption(f"기준 날짜 {value['day']} · " + (value.get("work_id") or "해당 날짜 전체"))
        rows = domain.daily_rows(plan, date.fromisoformat(value["day"]))
        if value.get("work_id"):
            rows = [i for i in rows if i.work_id == value["work_id"]]
        st.dataframe(_table(rows), hide_index=True, width="stretch")
        for item in turn["result"].plan_sources:
            st.caption(item.title + " · " + item.source.get("source", "작업계획서"))


def consume_pending():
    if st.session_state.plus_load_failed:
        st.session_state.preventra_pending = None
        st.session_state.preventra_input_notice = "계획을 불러온 뒤 질문을 다시 보내 주세요."
        return
    from preventra_plan.agent import dispatch
    state.consume_pending(request_context=current_context(), dispatcher=dispatch)
