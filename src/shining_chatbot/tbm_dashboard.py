"""Daily manager briefing assembled from the reviewed work plan."""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from shining_chatbot.action_data import FieldAction, action_attention_flags, action_due_kst
from shining_chatbot.business_time import now_korea, today_korea
from shining_chatbot.chat_data import markdown_label
from shining_chatbot.field_dashboard import _styles
from shining_chatbot.plan_revision import day_revision_token
from shining_chatbot.tbm_data import TbmDelivery, TbmRecord, brief_fingerprint, briefing_html, briefing_text, confirm_brief, daily_actions, daily_items, handover_actions, record_delivery, worker_briefing_summary
from shining_chatbot.weather_data import forecast_summary, summarize_work_window, work_weather_notes
from shining_chatbot.weather_panel import show_weather_refresh_button, weather_for_day
from shining_chatbot.work_plan import WorkPlan, coordination_candidates, missing_work_fields


def _go_field() -> None:
    st.session_state["view"] = "field"
    st.query_params["page"] = "field"
    st.rerun()


def _brief_styles() -> None:
    st.markdown("""<style>
.tbm-intro{max-width:680px;color:#617166;font-size:13px;line-height:1.7;margin:0 0 24px}
.tbm-section{margin:26px 0 11px;display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.tbm-section h2{font-size:16px;letter-spacing:-.025em;font-weight:620;margin:0;color:#293C30}
.tbm-section span{font-size:11px;color:#5F6D62}
.tbm-work{display:grid;grid-template-columns:74px minmax(0,1fr) auto;gap:17px;align-items:start;padding:16px 4px;border-top:1px solid #E5ECE5}.tbm-work>div{min-width:0}
.tbm-work-time{color:#50765A;font-size:12px;font-weight:620}.tbm-work-time small{display:block;color:#5F6D62;font-size:11px;font-weight:400}
.tbm-work h3{margin:0 0 5px;font-size:13px;font-weight:600;letter-spacing:-.015em;color:#29372D;line-height:1.55;overflow-wrap:anywhere;word-break:keep-all}
.tbm-work p{margin:0;font-size:11px;line-height:1.7;color:#5F6D62;overflow-wrap:anywhere;word-break:keep-all}.tbm-work-control{margin-top:5px!important;color:#4C6152!important}
.tbm-work-control b{font-weight:600;color:#3D5842}.tbm-state-stack{display:flex;flex-direction:column;align-items:flex-end;gap:5px}.tbm-state.gap{background:#F8F3EA;border:1px solid #EADFCB;color:#806642;white-space:normal;max-width:170px;text-align:right;line-height:1.35}
.tbm-state{font-size:10px;padding:4px 8px;border-radius:5px;background:#F8F1E5;color:#75572D;white-space:nowrap}.tbm-state.ok{background:#E9F2E9;color:#477651}
.tbm-callout{padding:15px 17px;background:#F3F7F2;border:1px solid #E2EAE0;border-radius:7px;color:#405B47;font-size:12px;line-height:1.65;margin-top:14px}
.tbm-callout strong{font-weight:600;color:#2A4632}
.tbm-action-flag{color:#8A673E!important;font-weight:620!important}
.tbm-callout ul{margin:7px 0 0;padding-left:18px}.tbm-callout li{margin:3px 0}
.tbm-share-summary{padding:17px 19px;background:#F8FAF7;border:1px solid #DDE7DC;border-radius:9px;margin:18px 0 20px}
.tbm-share-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:8px}
.tbm-share-head strong{font-size:13px;font-weight:650;color:#2F4935}.tbm-share-head span{font-size:10px;color:#68756A}
.tbm-share-summary ol{margin:0;padding-left:20px;color:#4A5B4D;font-size:11px;line-height:1.75}
.tbm-share-summary li{padding:3px 0 3px 2px}.tbm-share-summary li::marker{color:#628268;font-weight:650}
.tbm-share-note{font-size:10px;color:#68756A;line-height:1.55;margin:9px 0 0}
.tbm-ready{display:flex;align-items:center;gap:12px;border:1px solid #CADFCB;background:#F4F9F3;padding:14px 17px;border-radius:8px;margin:20px 0 10px}
.tbm-ready b{font-weight:620;color:#31563B}.tbm-ready span{color:#5F6D62;font-size:11px}
.handover-card{border:1px solid #DDE6DC;border-radius:10px;background:linear-gradient(130deg,#FBFCFA,#F5F8F4);padding:17px 19px;margin:15px 0 19px}
.handover-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding-bottom:11px;border-bottom:1px solid #E6ECE5}
.handover-head strong{font-size:13px;font-weight:620;color:#334539}.handover-head span{font-size:10px;color:#5F6D62}
.handover-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:12px 0}
.handover-metric{border:1px solid #E6ECE5;border-radius:7px;background:white;padding:10px 11px}
.handover-metric span{display:block;color:#5F6D62;font-size:10px;margin-bottom:5px}
.handover-metric strong{color:#34493A;font:600 17px/1.2 var(--font-ui);letter-spacing:-.03em}
.handover-metric small{display:block;margin-top:4px;color:#5F6D62;font-size:10px;line-height:1.4}
.handover-lines{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.handover-list{padding:10px 12px;border:1px solid #E8EDE7;border-radius:7px;background:#FFFFFFB8}
.handover-list b{display:block;color:#55665A;font-size:10px;font-weight:600;margin-bottom:5px}
.handover-list span{display:block;color:#69776B;font-size:10px;line-height:1.55;padding:3px 0}
.handover-note{margin:11px 0 0;color:#5F6D62;font-size:10px;line-height:1.5}
.tbm-muted{font-size:11px;color:#5F6D62;line-height:1.65}
@media(max-width:640px){.tbm-work{grid-template-columns:54px minmax(0,1fr);gap:10px}.tbm-state-stack{grid-column:2;align-items:flex-start}.tbm-state{width:max-content}.tbm-section{display:block}.tbm-section span{display:block;margin-top:3px}.handover-head{align-items:flex-start;flex-direction:column;gap:4px}.handover-metrics{grid-template-columns:1fr}.handover-lines{grid-template-columns:1fr}}
</style>""", unsafe_allow_html=True)


def show_tbm_dashboard() -> None:
    if st.session_state.pop("_tbm_delivery_form_clear_pending", False):
        for key in ("tbm_delivery_actor", "tbm_attendee_count", "tbm_delivery_note", "tbm_delivery_ack"):
            st.session_state.pop(key, None)
    _styles()
    _brief_styles()
    plan: WorkPlan | None = st.session_state.get("field_plan")
    st.markdown(
        '<div class="field-hero"><div><div class="field-kicker">SAFETY ATLAS / TOOLBOX MEETING</div>'
        '<h1>TBM 브리핑</h1>'
        f'<p class="field-hero-site">{escape(plan.site) if plan else "현장 계획을 연결하세요"}</p>'
        '<p>확인한 작업과 남은 조치를 한 장으로 정리해 작업자에게 전달하세요.</p></div>'
        f'<span class="field-date"><small>오늘 기준</small>{today_korea():%Y.%m.%d}</span></div>',
        unsafe_allow_html=True,
    )
    if plan is None:
        st.info("작업계획을 등록하면 날짜별 브리핑 초안이 자동으로 생성됩니다.")
        if st.button("오늘의 작업에서 계획 등록", type="primary", key="tbm_open_plan"):
            _go_field()
        return

    days = sorted({item.day for item in plan.items})
    if st.session_state.get("tbm_available_days") != tuple(days):
        st.session_state["tbm_available_days"] = tuple(days)
        if st.session_state.get("tbm_day") not in days:
            today = today_korea()
            st.session_state["tbm_day"] = st.session_state.get("field_day") if st.session_state.get("field_day") in days else (today if today in days else days[0])
    day = st.selectbox("브리핑 날짜", days, format_func=lambda value: f"{value:%Y.%m.%d} ({'월화수목금토일'[value.weekday()]})", key="tbm_day")
    today = today_korea()
    if day != today:
        st.caption(f"실제 오늘은 {today:%Y.%m.%d} · 현재 {day:%Y.%m.%d} 작업 브리핑을 보고 있습니다.")
    items = daily_items(plan, day)
    actions: tuple[FieldAction, ...] = tuple(st.session_state.get("field_actions", ()))
    reviews: dict = st.session_state.get("field_reviews", {})
    related = daily_actions(plan, day, actions)
    open_actions = sorted(
        (action for action in related if action.status == "open"),
        key=action_due_kst,
    )
    prior_days = [planned_day for planned_day in days if planned_day < day]
    prior_day = prior_days[-1] if prior_days else None
    carried = handover_actions(plan, day, actions)
    prior_items = daily_items(plan, prior_day) if prior_day else ()
    prior_unconfirmed = [
        item for item in prior_items
        if reviews.get(item.work_id, {}).get("status") != "확인 완료"
    ]
    pending = [item for item in items if reviews.get(item.work_id, {}).get("status") != "확인 완료"]
    changed = [action for action in related if action.needs_review]
    overlaps = coordination_candidates(tuple(plan.items), day)
    weather_location = st.session_state.get("field_weather_location")
    forecast = weather_for_day(day) if weather_location else None
    weather_text = ""
    if forecast is not None:
        weather_text = forecast_summary(weather_location, forecast)
        weather_notes = work_weather_notes(tuple(item.activity for item in items), forecast)
        if weather_notes:
            weather_text += " · 확인: " + " / ".join(weather_notes)
        window_lines = []
        for item in items:
            window = summarize_work_window(item, forecast)
            line = f"{window.time_label} {window.activity} · {window.detail}"
            if window.checks:
                line += " · 확인: " + " / ".join(window.checks)
            window_lines.append(line)
        if window_lines:
            weather_text += "\n작업 시간대별 모델 예보"
            for index, line in enumerate(window_lines):
                if len(weather_text) + len(line) + 2 > 900:
                    remaining = len(window_lines) - index
                    weather_text += f"\n그 밖의 {remaining}개 작업 시간대는 대시보드에서 확인"
                    break
                weather_text += "\n" + line
    elif weather_location:
        weather_text = (
            f"{weather_location.region} {weather_location.name} · {day:%m.%d} 예보 확인 불가 · "
            "현장 기상과 기상청 특보 직접 확인"
        )
    else:
        weather_text = "예보 위치 미연결 · 현장 기상과 기상청 특보 직접 확인"
    records: dict[str, tuple[TbmRecord, ...]] = st.session_state.setdefault("field_tbm_records", {})
    history = records.get(day.isoformat(), ())
    deliveries: dict[str, tuple[TbmDelivery, ...]] = st.session_state.setdefault("field_tbm_deliveries", {})
    delivery_history = deliveries.get(day.isoformat(), ())
    revisions = tuple(st.session_state.get("field_revisions", ()))
    revision_token = day_revision_token(revisions, day)
    fingerprint = brief_fingerprint(plan, day, actions, reviews, weather_text, revision_token)
    current = history[-1] if history and history[-1].fingerprint == fingerprint else None
    current_delivery = next((entry for entry in reversed(delivery_history) if current and entry.confirmation_at == current.confirmed_at and entry.fingerprint == current.fingerprint), None)
    stale = bool(history and current is None)

    st.markdown(
        '<div class="field-metrics action-metrics">'
        f'<div class="field-metric"><span>예정 작업</span><strong>{len(items)}</strong><small>건</small></div>'
        f'<div class="field-metric"><span>현장 확인 필요</span><strong>{len(pending)}</strong><small>건</small></div>'
        f'<div class="field-metric"><span>작업 조정 후보</span><strong>{len(overlaps)}</strong><small>쌍</small></div>'
        f'<div class="field-metric"><span>미완료 조치</span><strong>{len(open_actions)}</strong><small>건</small></div>'
        '</div>', unsafe_allow_html=True,
    )
    if current:
        st.markdown(
            f'<div class="tbm-ready"><b>{"TBM 진행 기록 완료" if current_delivery else "관리자 확인 완료"}</b>'
            f'<span>{escape(current.confirmed_by)} · {current.confirmed_at:%Y.%m.%d %H:%M} · 공유 대상 {escape(current.audience)}</span></div>',
            unsafe_allow_html=True,
        )
    elif stale:
        st.warning("확인 이후 계획·조치·검토 기록이 바뀌었습니다. 현재 내용을 다시 확인하고 브리핑을 갱신하세요.")
    else:
        st.caption("현재 상태: 확인 전 초안 · 작업별 현장 확인을 마치면 브리핑을 확정할 수 있습니다.")
    share_lines = worker_briefing_summary(plan, day, actions, reviews, weather_text)
    share_items = "".join(f"<li>{escape(line)}</li>" for line in share_lines)
    st.markdown(
        '<section class="tbm-share-summary" aria-labelledby="tbm-share-title">'
        '<div class="tbm-share-head"><strong id="tbm-share-title">작업자에게 먼저 공유할 내용</strong>'
        '<span>현장 확인 후 전달</span></div>'
        f'<ol>{share_items}</ol>'
        '<p class="tbm-share-note">사고 사례 숫자는 공개 자료의 키워드 검색 건수입니다. 현장 사고율·위험 점수·예측값이 아닙니다.</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    weather_lines = "<br>".join(escape(line) for line in weather_text.splitlines())
    st.markdown(f'<div class="tbm-callout"><strong>현장 기상 확인</strong><br>{weather_lines}</div>', unsafe_allow_html=True)
    if weather_location:
        show_weather_refresh_button(f"tbm_weather_refresh_{day:%Y%m%d}")

    first_work = min(items, key=lambda item: item.start) if items else None
    carried_lines = "".join(
        f'<span>{escape(action.description)} · {escape(action.assignee)} · 기한 {action_due_kst(action):%m.%d %H:%M}</span>'
        for action in carried[:3]
    ) or "<span>이전 작업일에서 넘어온 미완료 조치 기록이 없습니다.</span>"
    if len(carried) > 3:
        carried_lines += f'<span>외 {len(carried) - 3}건 · 조치 현황에서 전체 목록 확인</span>'
    prior_lines = "".join(
        f'<span>{item.start:%H:%M} · {escape(item.activity)} · '
        f'{escape(reviews.get(item.work_id, {}).get("status", "미확인"))}</span>'
        for item in prior_unconfirmed[:3]
    ) or "<span>직전 작업일의 미완료 현장 확인 기록이 없습니다.</span>"
    if len(prior_unconfirmed) > 3:
        prior_lines += f'<span>외 {len(prior_unconfirmed) - 3}건 · 직전 작업일 화면에서 확인</span>'
    st.markdown(
        '<div class="handover-card"><div class="handover-head"><strong>직전 작업일에서 이어받기</strong>'
        f'<span>{f"{prior_day:%Y.%m.%d} → " if prior_day else "이전 계획 없음 · "}{day:%Y.%m.%d}</span></div>'
        '<div class="handover-metrics">'
        f'<div class="handover-metric"><span>이월 미완료 조치</span><strong>{len(carried)}건</strong></div>'
        f'<div class="handover-metric"><span>직전 작업일 확인 미완료</span><strong>{len(prior_unconfirmed)}건</strong></div>'
        f'<div class="handover-metric"><span>오늘 첫 작업</span><strong>{f"{first_work.start:%H:%M}" if first_work else "없음"}</strong>'
        f'{f"<small>{escape(first_work.activity)}</small>" if first_work else ""}</div>'
        '</div><div class="handover-lines">'
        f'<div class="handover-list"><b>남은 조치</b>{carried_lines}</div>'
        f'<div class="handover-list"><b>{f"{prior_day:%m.%d} 확인 기록" if prior_day else "현장 확인 기록"}</b>{prior_lines}</div>'
        '</div><p class="handover-note">계획서와 이 세션에 작성한 확인·조치 기록을 요약합니다. 실제 교대 인계 완료 여부를 대신하지 않습니다.</p></div>',
        unsafe_allow_html=True,
    )
    action_col, review_col = st.columns(2, gap="small")
    with action_col:
        if carried:
            target = carried[0]
            if st.button("이월 조치 열기", key="tbm_open_handover_action", width="stretch"):
                st.session_state["field_action_filter"] = "미완료"
                st.session_state["field_action_query"] = ""
                st.session_state["field_selected_action"] = target.action_id
                st.session_state["view"] = "actions"
                st.query_params["page"] = "actions"
                st.rerun()
    with review_col:
        if prior_unconfirmed:
            target_work = prior_unconfirmed[0]
            if st.button("직전 작업 확인 열기", key="tbm_open_prior_review", width="stretch"):
                st.session_state["field_day"] = prior_day
                st.session_state["field_item_choice"] = target_work.work_id
                st.session_state["view"] = "field"
                st.query_params["page"] = "field"
                st.rerun()

    st.markdown('<div class="tbm-section"><h2>작업 순서와 시작 전 확인</h2><span>PLAN / REVIEW</span></div>', unsafe_allow_html=True)
    work_rows = []
    missing_items = []
    for item in items:
        review = reviews.get(item.work_id, {})
        done = review.get("status") == "확인 완료"
        missing_fields = missing_work_fields(item)
        if missing_fields:
            missing_items.append(item)
        missing_badge = (
            f'<span class="tbm-state gap">계획서 입력 확인 · {escape(" / ".join(missing_fields))}</span>'
            if missing_fields else ""
        )
        work_rows.append(
            '<div class="tbm-work">'
            f'<div class="tbm-work-time">{item.start:%H:%M}<small>{item.end:%H:%M}</small></div>'
            f'<div><h3>{escape(item.activity)}</h3>'
            f'<p>{escape(item.area)} · {escape(item.location or "세부 위치 미입력")} · {escape(item.contractor or "업체 미입력")}</p>'
            f'<p class="tbm-work-control"><b>계획 조치</b> {escape(item.planned_controls or "미기재 · 작업허가서/위험성평가 확인")}</p>'
            f'<p class="tbm-work-control"><b>시작 전 확인</b> {escape(item.follow_up or "미기재 · 작업 전 현장 확인 항목 지정")}</p></div>'
            f'<div class="tbm-state-stack"><span class="tbm-state {"ok" if done else ""}">{"확인 완료" if done else "현장 확인 필요"}</span>{missing_badge}</div>'
            '</div>'
        )
    st.markdown("".join(work_rows), unsafe_allow_html=True)
    if missing_items:
        st.caption("계획서 미기재 항목은 위험도 판정이 아닙니다. 작업허가서와 현장 상태를 확인해 주세요.")
        if st.button(
            f"누락된 작업 상세 확인 · {len(missing_items)}건",
            key=f"tbm_open_plan_gap_{day:%Y%m%d}",
            icon=":material/open_in_new:", width="stretch",
        ):
            target = missing_items[0]
            st.session_state["field_day"] = day
            st.session_state["field_item_choice"] = target.work_id
            _go_field()

    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown('<div class="tbm-section"><h2>작업 간 조정 후보</h2><span>COORDINATION</span></div>', unsafe_allow_html=True)
        if overlaps:
            lines = "".join(
                f'<li><strong>{escape(a.activity)} / {escape(b.activity)}</strong> · '
                f'{max(a.start, b.start):%H:%M}–{min(a.end, b.end):%H:%M}<br>'
                f'<span>{escape(" · ".join(reasons))}</span></li>'
                for a, b, reasons in overlaps[:5]
            )
            st.markdown(f'<div class="tbm-callout"><strong>작업계획 표기에서 조정 후보 {len(overlaps)}쌍을 찾았습니다</strong><ul>{lines}</ul><div>실제 장비 사용·동선·책임 범위를 작업 전에 확인하세요. 위험 판정은 아닙니다.</div></div>', unsafe_allow_html=True)
            if len(overlaps) > 5:
                with st.expander(f"추가 조정 후보 {len(overlaps) - 5}쌍"):
                    extra_lines = "".join(
                        f'<li><strong>{escape(a.activity)} / {escape(b.activity)}</strong> · '
                        f'{max(a.start, b.start):%H:%M}–{min(a.end, b.end):%H:%M}<br>'
                        f'<span>{escape(" · ".join(reasons))}</span></li>'
                        for a, b, reasons in overlaps[5:]
                    )
                    st.markdown(f'<div class="tbm-callout"><ul>{extra_lines}</ul></div>', unsafe_allow_html=True)
            first = overlaps[0][0]
            if st.button("오늘의 작업에서 후보 확인", key="tbm_open_coordination"):
                st.session_state["field_day"] = day
                st.session_state["field_item_choice"] = first.work_id
                _go_field()
        else:
            st.markdown('<div class="tbm-callout">등록된 같은 시간대 조정 후보가 없습니다.</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="tbm-section"><h2>남은 조치</h2><span>OPEN ACTIONS</span></div>', unsafe_allow_html=True)
        if open_actions:
            at = now_korea()
            rows = []
            for action in open_actions:
                due_at = action_due_kst(action)
                flags = action_attention_flags(action, at)
                prefix = (
                    f'<strong class="tbm-action-flag">{escape(" · ".join(flags))} · </strong>'
                    if flags else ""
                )
                rows.append(
                    f'<li>{prefix}{escape(action.description)} · '
                    f'{escape(action.assignee)} · {due_at:%m.%d %H:%M}</li>'
                )
            lines = "".join(rows)
            st.markdown(f'<div class="tbm-callout"><strong>담당자와 기한 확인</strong><ul>{lines}</ul></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="tbm-callout">등록된 미완료 조치가 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="tbm-section"><h2>관리자 확인과 공유</h2><span>CONFIRM / EXPORT</span></div>', unsafe_allow_html=True)
    if pending or changed:
        reasons = []
        if pending:
            reasons.append(f"현장 확인이 끝나지 않은 작업 {len(pending)}건")
        if changed:
            reasons.append(f"계획 변경으로 재확인이 필요한 조치 {len(changed)}건")
        st.info(" · ".join(reasons) + "을 확인한 뒤 브리핑을 확정하세요.")
        if st.button("오늘의 작업에서 확인", key="tbm_review_work"):
            st.session_state["field_day"] = day
            target = pending[0] if pending else next(
                (item for item in items if any(action.work_id == item.work_id for action in changed)),
                None,
            )
            if target is not None:
                st.session_state["field_item_choice"] = target.work_id
            _go_field()
    with st.form("tbm_confirm_form"):
        form_left, form_right = st.columns(2)
        with form_left:
            confirmed_by = st.text_input("진행자 *", value=current.confirmed_by if current else "", max_chars=100)
        with form_right:
            audience = st.text_input("공유 대상 *", value=current.audience if current else "", placeholder="예: A동 오전 작업자", max_chars=200)
        note = st.text_area("전달 사항", value=current.note if current else "", placeholder="현장에서 추가로 확인한 사항을 적으세요.", max_chars=2000)
        submitted = st.form_submit_button("현재 내용 확인 완료", type="primary", disabled=bool(pending or changed))
    if submitted:
        try:
            record = confirm_brief(plan, day, actions, reviews, confirmed_by, audience, note, weather_text, revision_token)
        except ValueError as exc:
            st.error(str(exc))
        else:
            records[day.isoformat()] = (*history, record)
            st.rerun()

    if current:
        with st.expander("TBM 진행 기록 남기기", expanded=current_delivery is None):
            if current_delivery:
                st.caption(f"진행 {markdown_label(current_delivery.delivered_by)} · 참석 {current_delivery.attendee_count}명 · {current_delivery.delivered_at:%Y.%m.%d %H:%M}")
            with st.form(f"tbm_delivery_{current.confirmed_at.isoformat()}"):
                delivered_by = st.text_input("실제 진행자 *", value=current.confirmed_by, max_chars=100, key="tbm_delivery_actor")
                attendee_count = st.number_input(
                    "실제 참석 인원 *", min_value=0, max_value=10000,
                    value=0, step=1, key="tbm_attendee_count",
                )
                delivery_note = st.text_area("질문·변경 사항", placeholder="없으면 비워둘 수 있습니다.", max_chars=2000, key="tbm_delivery_note")
                acknowledged = st.checkbox("작업자에게 확인 사항을 전달하고 질문을 확인했습니다.", key="tbm_delivery_ack")
                delivery_submitted = st.form_submit_button("TBM 진행 기록 저장", type="primary")
            if delivery_submitted:
                if not acknowledged:
                    st.error("전달과 질문 확인 후 기록하세요.")
                elif int(attendee_count) < 1:
                    st.error("실제 참석 인원을 1명 이상 입력하세요.")
                else:
                    try:
                        delivery = record_delivery(current, delivered_by, int(attendee_count), delivery_note)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        deliveries[day.isoformat()] = (*delivery_history, delivery)
                        st.session_state["_tbm_delivery_form_clear_pending"] = True
                        st.rerun()

    st.download_button(
        "확인본 내려받기 (.html)" if current else "확인 전 초안 내려받기 (.html)",
        data=briefing_html(plan, day, actions, current, reviews, weather_text, current_delivery),
        file_name=f"TBM_{'확인본' if current else '초안'}_{day:%Y%m%d}.html",
        mime="text/html",
        key="tbm_download",
        width="stretch",
    )
    share_text = briefing_text(plan, day, actions, current, reviews, weather_text, current_delivery)
    with st.expander("작업자 공유용 텍스트", expanded=False):
        st.caption("확인본인지 초안인지 첫 줄에 표시됩니다. 현장 확인 후 필요한 내용을 복사해 공유하세요.")
        st.code(share_text, language=None)
        st.download_button(
            "텍스트 파일 받기", share_text.encode("utf-8-sig"),
            file_name=f"TBM_{'확인본' if current else '초안'}_{day:%Y%m%d}.txt",
            mime="text/plain", key="tbm_download_text",
        )
    st.markdown('<div class="tbm-muted">HTML 파일을 열어 인쇄하거나 PDF로 저장할 수 있습니다. 공유 전 실제 작업 조건을 다시 확인하세요.</div>', unsafe_allow_html=True)
    if history:
        with st.expander(f"이 날짜의 확인 기록 {len(history)}건"):
            for record in reversed(history):
                label = "현재 확인" if current and record.confirmed_at == current.confirmed_at else "이전 확인 내용"
                delivered = any(entry.confirmation_at == record.confirmed_at and entry.fingerprint == record.fingerprint for entry in delivery_history)
                st.text(f"{record.confirmed_at:%Y.%m.%d %H:%M} · {record.confirmed_by} · {label} · {'전달 기록 있음' if delivered else '전달 기록 없음'}")
                st.caption(f"공유 대상 {markdown_label(record.audience)}" + (f" · {markdown_label(record.note)}" if record.note else ""))
    st.caption("브리핑 확인 기록은 현재 브라우저 세션에 보관됩니다. 기록 백업에서 JSON 파일로 내려받을 수 있습니다.")
