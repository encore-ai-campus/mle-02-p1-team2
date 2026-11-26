"""Manager-facing follow-up register linked to planned work."""

from __future__ import annotations

from datetime import date, datetime
from html import escape

import pandas as pd
import streamlit as st

from shining_chatbot.action_data import (
    FieldAction,
    action_attention_flags,
    action_due_kst,
    action_selection_label,
    finish_action,
    is_action_overdue,
    reopen_action,
)
from shining_chatbot.business_time import now_korea, today_korea
from shining_chatbot.chat_data import markdown_label
from shining_chatbot.csv_safety import safe_spreadsheet_cell as _csv_cell
from shining_chatbot.field_dashboard import _styles
from shining_chatbot.work_plan import WorkPlan


def _save_action(updated: FieldAction, notice: str) -> None:
    st.session_state["field_actions"] = tuple(
        updated if action.action_id == updated.action_id else action
        for action in st.session_state.get("field_actions", ())
    )
    st.session_state["field_action_notice"] = notice
    st.session_state["_action_form_clear_pending"] = updated.action_id


def _reset_action_selection() -> None:
    st.session_state.pop("field_selected_action", None)


def _show_completed_actions() -> None:
    st.session_state["field_action_filter"] = "완료"
    st.session_state["field_action_query"] = ""
    st.session_state.pop("field_selected_action", None)


def show_action_dashboard() -> None:
    action_to_clear = st.session_state.pop("_action_form_clear_pending", None)
    if isinstance(action_to_clear, str):
        for key in (
            f"complete_actor_{action_to_clear}", f"complete_note_{action_to_clear}",
            f"reopen_actor_{action_to_clear}", f"reopen_reason_{action_to_clear}",
        ):
            st.session_state.pop(key, None)
    _styles()
    plan: WorkPlan | None = st.session_state.get("field_plan")
    site = escape(plan.site) if plan else "현장 계획을 연결하세요"
    st.markdown(
        '<div class="field-hero"><div><div class="field-kicker">SAFETY ATLAS / ACTION REGISTER</div>'
        f'<h1>조치 현황</h1><p class="field-hero-site">{site}</p>'
        '<p>담당자와 기한을 확인하고 남은 조치를 마무리하세요.</p></div>'
        f'<span class="field-date"><small>오늘 기준</small>{today_korea():%Y.%m.%d}</span></div>',
        unsafe_allow_html=True,
    )
    if plan is None:
        st.info("작업계획을 먼저 등록하면 작업별 조치를 지정할 수 있습니다.")
        if st.button("오늘의 작업으로 이동"):
            st.session_state["view"] = "field"
            st.query_params["page"] = "field"
            st.rerun()
        return
    actions: tuple[FieldAction, ...] = tuple(st.session_state.get("field_actions", ()))
    now = now_korea()
    open_actions = [action for action in actions if action.status == "open"]
    overdue = [action for action in open_actions if is_action_overdue(action, now)]
    due_today = [action for action in open_actions if action_due_kst(action).date() == now.date()]
    completed = [action for action in actions if action.status == "done"]
    st.markdown(
        '<div class="field-metrics action-metrics">'
        f'<div class="field-metric"><span>미완료 조치</span><strong>{len(open_actions)}</strong><small>건</small></div>'
        f'<div class="field-metric"><span>기한 지남</span><strong>{len(overdue)}</strong><small>건</small></div>'
        f'<div class="field-metric"><span>오늘 기한</span><strong>{len(due_today)}</strong><small>건</small></div>'
        f'<div class="field-metric"><span>완료 기록</span><strong>{len(completed)}</strong><small>건</small></div>'
        '</div>', unsafe_allow_html=True,
    )
    if notice := st.session_state.pop("field_action_notice", None):
        st.success(notice)
    if not actions:
        st.markdown(
            '<div class="field-panel"><div class="field-panel-title">등록된 조치가 없습니다</div>'
            '<p class="field-sub">오늘의 작업에서 작업을 선택해 담당자와 완료 기한이 있는 조치를 등록하세요.</p></div>',
            unsafe_allow_html=True,
        )
        return

    work_by_id = {item.work_id: item for item in plan.items}
    filter_label = st.radio(
        "조회 상태", ["미완료", "기한 지남", "재확인", "전체", "완료"],
        horizontal=True, key="field_action_filter", on_change=_reset_action_selection,
    )
    query = st.text_input(
        "조치 검색", placeholder="조치 내용, 담당자, 작업명 또는 ID",
        key="field_action_query", label_visibility="collapsed", on_change=_reset_action_selection,
    ).strip().casefold()
    if filter_label == "미완료":
        visible = open_actions
    elif filter_label == "기한 지남":
        visible = [action for action in open_actions if is_action_overdue(action, now)]
    elif filter_label == "재확인":
        visible = [action for action in open_actions if action.needs_review]
    elif filter_label == "완료":
        visible = completed
    else:
        visible = list(actions)
    if query:
        visible = [
            action for action in visible
            if query in " ".join((
                action.description, action.assignee, action.action_id, action.work_id,
                work_by_id[action.work_id].activity if action.work_id in work_by_id else "",
            )).casefold()
        ]
    visible.sort(key=lambda action: (action.status == "done", action_due_kst(action), action.action_id))
    if not visible:
        if filter_label == "미완료" and completed and not query:
            st.info(f"미완료 조치가 없습니다. 완료 기록 {len(completed)}건은 아래 버튼에서 확인할 수 있습니다.")
            st.button(
                "완료 기록 보기", key="field_action_show_completed",
                on_click=_show_completed_actions,
            )
        else:
            st.info("조건에 맞는 조치가 없습니다. 검색어를 지우거나 다른 상태를 선택해 보세요.")
        return
    rows = []
    for action in visible:
        work = work_by_id.get(action.work_id)
        name = work.activity if work else "계획에서 제외된 작업"
        due_at = action_due_kst(action)
        late = is_action_overdue(action, now)
        flags = action_attention_flags(action, now)
        status = " · ".join(flag.replace("계획 변경 ", "") for flag in flags) or (
            "완료" if action.status == "done" else "대기"
        )
        rows.append(
            '<div class="action-row">'
            f'<span class="action-due">{due_at:%m.%d}<small>{due_at:%H:%M}</small></span>'
            f'<div><div class="action-name">{escape(action.description)}</div>'
            f'<div class="action-context">{escape(name)} · {escape(action.assignee)}</div></div>'
            f'<span class="action-state {"late" if late or action.needs_review else "done" if action.status == "done" else ""}">{status}</span>'
            '</div>'
        )
    st.markdown(
        '<div class="action-list"><div class="field-panel-title">조치 목록</div>' + "".join(rows) + '</div>',
        unsafe_allow_html=True,
    )
    export_rows = []
    for entry in visible:
        linked_work = work_by_id.get(entry.work_id)
        is_late = is_action_overdue(entry, now)
        export_rows.append({
            "현장": plan.site,
            "조치 ID": entry.action_id,
            "작업 ID": entry.work_id,
            "작업명": linked_work.activity if linked_work else "계획에서 제외된 작업",
            "조치 내용": entry.description,
            "담당자": entry.assignee,
            "기한": action_due_kst(entry).isoformat(timespec="minutes"),
            "상태": "완료" if entry.status == "done" else "재확인" if entry.needs_review else "기한 지남" if is_late else "미완료",
            "계획 재확인 필요": "예" if entry.needs_review else "아니오",
            "기한 경과": "예" if is_late else "아니오",
            "등록 시각": entry.created_at.isoformat(timespec="minutes"),
            "변경 이력 수": len(entry.events),
        })
    export_frame = pd.DataFrame(export_rows)
    for column in ("현장", "조치 ID", "작업 ID", "작업명", "조치 내용", "담당자", "상태", "계획 재확인 필요"):
        export_frame[column] = export_frame[column].map(_csv_cell)
    st.download_button(
        "현재 조치 목록 CSV 받기",
        data=export_frame.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"조치목록_{today_korea():%Y%m%d}.csv",
        mime="text/csv",
        key="field_action_export",
    )
    actions_by_id = {action.action_id: action for action in visible}
    previous_selection = st.session_state.get("field_selected_action")
    if previous_selection not in actions_by_id:
        legacy_action = next(
            (
                entry for entry in visible
                if previous_selection == (
                    f"{action_due_kst(entry):%m.%d %H:%M} · "
                    f"{entry.description} ({entry.action_id})"
                )
            ),
            None,
        )
        if legacy_action:
            st.session_state["field_selected_action"] = legacy_action.action_id
        elif previous_selection is not None:
            st.session_state.pop("field_selected_action", None)
    selected_id = st.selectbox(
        "자세히 볼 조치",
        list(actions_by_id),
        key="field_selected_action",
        format_func=lambda action_id: action_selection_label(actions_by_id[action_id]),
    )
    action = actions_by_id[selected_id]
    work = work_by_id.get(action.work_id)
    with st.container(border=True):
        st.markdown('<div class="field-kicker">ACTION DETAIL / ' + escape(action.action_id) + '</div>', unsafe_allow_html=True)
        st.subheader(markdown_label(action.description))
        st.caption(
            f"연결 작업: {markdown_label(work.activity if work else '계획에서 제외된 작업')} · "
            f"담당 {markdown_label(action.assignee)} · 기한 {action_due_kst(action):%Y.%m.%d %H:%M}"
        )
        if work is not None and st.button("연결된 작업 상세 열기", key=f"open_action_work_{action.action_id}"):
            st.session_state["field_day"] = work.day
            st.session_state["field_item_choice"] = work.work_id
            st.session_state["view"] = "field"
            st.query_params["page"] = "field"
            st.rerun()
        if action.needs_review:
            st.warning("연결된 작업계획이 바뀌거나 제외됐습니다. 현재 조치 내용을 다시 확인하세요.")
        if action.status == "open":
            with st.form(f"complete_{action.action_id}"):
                actor = st.text_input("완료 확인자 *", max_chars=100, key=f"complete_actor_{action.action_id}")
                note = st.text_area("실제 완료 내용 *", max_chars=2000, key=f"complete_note_{action.action_id}")
                completed_click = st.form_submit_button("완료 기록", type="primary")
            if completed_click:
                try:
                    _save_action(finish_action(action, actor, note), "완료자와 실제 완료 내용을 조치 이력에 저장했습니다.")
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()
        else:
            with st.form(f"reopen_{action.action_id}"):
                actor = st.text_input("변경자 *", max_chars=100, key=f"reopen_actor_{action.action_id}")
                reason = st.text_area("다시 연 이유 *", max_chars=2000, key=f"reopen_reason_{action.action_id}")
                reopened_click = st.form_submit_button("완료 취소 · 재개")
            if reopened_click:
                try:
                    _save_action(reopen_action(action, actor, reason), "조치를 다시 열고 변경 이유를 이력에 저장했습니다.")
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()
        with st.expander(f"변경 기록 {len(action.events)}건"):
            for event in reversed(action.events):
                st.text(f"{event.get('at', '')} · {event.get('actor', '')}")
                st.caption(markdown_label(event.get("note", "")))
    st.caption("조치와 변경 이력은 현재 브라우저 세션에 보관됩니다. 운영 기록으로 사용하려면 접근 권한이 있는 영구 저장소가 필요합니다.")
