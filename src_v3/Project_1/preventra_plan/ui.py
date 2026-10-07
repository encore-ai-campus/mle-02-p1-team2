"""Small plan UI; durable conversations and result rendering belong to Preventra."""
from datetime import date
from hashlib import sha256
from html import escape
import streamlit as st
from preventra_ui import state
from preventra_ui.history import get_store
from preventra_plan import domain
from preventra_plan.storage import get_plan_store, SavedPlan, PlanConflict


def initialize():
    defaults = {"plus_loaded_id": None, "plus_saved": SavedPlan(), "plus_load_failed": False,
                "plus_notice": "", "plus_candidate": None, "plus_candidate_token": None,
                "plus_upload_generation": 0, "plus_selected_record_id": None,
                "plus_selected_record_day": None, "plus_expanded_records": set(),
                "plus_history_migrated": False}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if not st.session_state.plus_history_migrated:
        try:
            get_plan_store()
            state.refresh_recent()
            st.session_state.plus_history_migrated = True
        except Exception:
            # The main page can still explain the history connection failure.
            pass
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
                preferred_day = st.session_state.get("plus_selected_record_day") if st.session_state.get("plus_selected_record_id") == identifier else None
                snapshot = st.session_state.plus_saved.snapshot
                if snapshot:
                    plan = domain.decode_plan(snapshot["plan"])
                    days = {item.day for item in plan.items}
                    selected_day = preferred_day or date.fromisoformat(snapshot["day"])
                    st.session_state.plus_day = selected_day if selected_day in days else min(days)
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
            "work_id": st.session_state.get("plus_work", value.get('work_id')) or None}}


def select_day():
    previous = st.session_state.plus_saved.snapshot
    if previous and save({**previous, 'day': st.session_state.plus_day.isoformat(), 'work_id': None}):
        st.session_state.plus_work = ''
        st.session_state.plus_brief_scope = "day"
    elif previous:
        st.session_state.plus_day = date.fromisoformat(previous['day'])


def select_work():
    previous = st.session_state.plus_saved.snapshot
    if previous and not save({**previous, 'work_id': st.session_state.plus_work or None}):
        st.session_state.plus_work = previous.get('work_id') or ''


def is_manager():
    return bool(st.session_state.plus_saved.snapshot or st.session_state.plus_load_failed or
                any(turn['request'].context.get('work_plan') for turn in st.session_state.preventra_turns))


def new_workspace_chat():
    manager_home = (st.session_state.get("preventra_plus_mode") and
                    st.session_state.get("plus_home_role", "관리자") == "관리자")
    state.new_chat()
    if manager_home and st.session_state.get("preventra_conversation_id"):
        state.navigate("홈")


def _switch_home_role(role):
    st.session_state.plus_home_role = role
    st.session_state.plus_home_tabs = role  # legacy key retained for restored sessions


def render_home():
    from preventra_ui_v2 import views
    current_role = st.session_state.get('plus_home_role', '관리자')
    legacy_role = st.session_state.get('plus_home_tabs')
    if legacy_role in ('작업자', '관리자') and legacy_role != current_role:
        current_role = legacy_role
    st.session_state.plus_home_role = current_role
    st.session_state.plus_home_tabs = current_role
    with st.container(key='plus_role_switch', horizontal=True,
                      horizontal_alignment='distribute', vertical_alignment='center'):
        st.html('<div class="plus-workspace-label"><span>PREVENTRA</span>  작업공간</div>')
        with st.container(horizontal=True, width='content', gap='small'):
            st.button('작업자', key='plus_role_worker', type='primary' if current_role == '작업자' else 'tertiary',
                      on_click=_switch_home_role, args=('작업자',))
            st.button('관리자', key='plus_role_manager', type='primary' if current_role == '관리자' else 'tertiary',
                      on_click=_switch_home_role, args=('관리자',))
    if current_role == '작업자':
        views.render_home(show_statistics=False)
        return
    with st.container(key='plus_manager_home'):
        _render_manager_home()


def _render_manager_home():
    snapshot = st.session_state.plus_saved.snapshot
    plan = domain.decode_plan(snapshot['plan']) if snapshot else None
    day = st.session_state.get('plus_day', date.fromisoformat(snapshot['day']) if snapshot else domain.today_korea())
    count = len(domain.daily_rows(plan, day)) if plan else 0
    site = plan.site if plan else "작업계획서 미연결"
    date_label = day.strftime('%m.%d')
    site_label = escape(site)

    hero_left, hero_right = st.columns([0.98, 1.02], gap="large", vertical_alignment="center")
    with hero_left:
        st.html(f'''<section class="plus-home-copy">
          <div class="plus-home-eyebrow"><i></i> 현장 안전관리</div>
          <h1>오늘 현장,<br><span>안전하게 시작해요</span></h1>
          <p class="plus-home-description">작업계획서를 첨부하거나 질문을 입력하면, 현장에 필요한 안전 정보를 모아드려요.</p>
          <div class="plus-site-pill"><i></i><strong>{site_label}</strong><span>{'연결됨' if plan else '계획서 필요'}</span></div>
          </section>''')
    with hero_right:
        st.html(f'''<section class="plus-brief-art" aria-label="오늘의 작업 브리핑 미리보기">
          <div class="plus-orbit plus-orbit-one"></div><div class="plus-orbit plus-orbit-two"></div>
          <div class="plus-float plus-float-top"><b>01</b> 작업 분석</div>
          <div class="plus-preview-card">
            <div class="plus-preview-head"><span>FIELD BRIEFING</span><i></i></div>
            <div class="plus-preview-date">{date_label} · {site_label}</div>
            <div class="plus-preview-number"><strong>{count:02d}</strong><span>예정 작업</span></div>
            <div class="plus-preview-empty">{'선택한 날짜에 등록된 작업이 없어요' if plan and count == 0 else '작업계획서를 연결하면 일정이 표시돼요' if not plan else f'{count}개 작업의 현장 브리핑을 준비했어요'}</div>
            <div class="plus-preview-link"><i></i> 일정 기준 미리보기</div>
          </div>
          <div class="plus-float plus-float-bottom"><b>02</b> 현장 브리핑</div>
        </section>''')

    conversation = st.session_state.get('plus_loaded_id')
    if st.session_state.get('plus_home_upload_for') != conversation:
        st.session_state.plus_home_upload_for = conversation
        st.session_state.plus_home_upload_open = False
    else:
        st.session_state.setdefault('plus_home_upload_open', False)
    upload_open = st.session_state.plus_home_upload_open
    with st.container(key='plus_home_upload_row', horizontal=True,
                      horizontal_alignment='left', vertical_alignment='center'):
        st.button('작업계획서 교체' if snapshot else '작업계획서 업로드',
                  key='plus_home_upload_toggle', type='secondary',
                  on_click=lambda: st.session_state.update(
                      plus_home_upload_open=not st.session_state.plus_home_upload_open))
        if snapshot:
            st.markdown('<span class="plus-upload-connected">계획서 연결됨</span>', unsafe_allow_html=True)
    if upload_open:
        render_plan(show_context=False)

    has_active_work = bool(snapshot and st.session_state.get("plus_loaded_id") == st.session_state.get("preventra_conversation_id"))
    if has_active_work:
        from preventra_plan.report import render_manager_dashboard
        st.markdown('<div class="plus-inline-report-kicker">오늘의 현장 브리핑</div>', unsafe_allow_html=True)
        with st.container(key="plus_dashboard"):
            render_manager_dashboard(show_controls=False, show_heading=True, show_plan_change=False)
        st.markdown('<div class="plus-divider"></div>', unsafe_allow_html=True)
        from preventra_ui_v2 import views
        active_day = st.session_state.get("plus_day", date.fromisoformat(snapshot["day"]))
        views.render_assistant(consume=consume_pending, turn_context_renderer=render_turn_context,
                               title=f"{active_day:%m월 %d일} 작업 대화", examples=())

    with st.container(key='plus_home_question'):
        with st.form('plus_manager_question_form', clear_on_submit=True, border=False):
            question_col, submit_col = st.columns([1, .08], gap='small', vertical_alignment='center')
            with question_col:
                st.text_input('안전 관련 질문', key='plus_manager_home_question',
                              label_visibility='collapsed',
                              placeholder='안전 관련 질문을 입력하세요')
            with submit_col:
                st.form_submit_button('↑', type='primary', on_click=submit_manager_home,
                                      disabled=blocked(), help='질문 보내기')
    st.html('<a class="plus-scroll-top" href="#" aria-label="맨 위로 이동"><span aria-hidden="true">↑</span> 맨 위로</a>')


def submit_manager_home():
    if blocked():
        return
    question = (st.session_state.get('plus_manager_home_question') or '').strip()
    if not question:
        st.session_state.plus_notice = '질문을 입력해 주세요.'
        return
    has_active_work = bool(st.session_state.plus_saved.snapshot and
                           st.session_state.get("plus_loaded_id") == st.session_state.get("preventra_conversation_id"))
    state.queue_question(question, context=current_context(), destination="홈" if has_active_work else "안전 어시스턴트")
    st.session_state.plus_notice = ''
    if not has_active_work:
        state.navigate('안전 어시스턴트')


def submit_chat():
    if blocked():
        return
    state.queue_question(st.session_state.get("preventra_chat_question", "") or "",
                         context=current_context())


def work_record_title(plan):
    site = (plan.site or "").strip()
    if site and site != "현장명 미입력":
        return site
    activities = list(dict.fromkeys(item.activity.strip() for item in plan.items if item.activity.strip()))
    if not activities:
        return site or "작업 기록"
    return activities[0] if len(activities) == 1 else f"{activities[0]} 외 {len(activities) - 1}건"


def open_work_record(identifier):
    state.open_conversation(identifier, destination="홈")
    st.session_state.plus_selected_record_id = identifier
    st.session_state.plus_expanded_records = set(st.session_state.get("plus_expanded_records", set())) | {identifier}
    st.session_state.plus_selected_record_day = None
    st.session_state.plus_brief_scope = "day"


def open_workday(identifier, day):
    state.open_conversation(identifier, destination="홈")
    st.session_state.plus_selected_record_id = identifier
    st.session_state.plus_selected_record_day = date.fromisoformat(day)
    st.session_state.plus_day = date.fromisoformat(day)
    st.session_state.plus_brief_scope = "day"
    try:
        st.session_state.plus_saved = get_plan_store().load(identifier)
        st.session_state.plus_loaded_id = identifier
        snapshot = st.session_state.plus_saved.snapshot
        if snapshot:
            save({**snapshot, "day": day, "work_id": None})
    except Exception:
        st.session_state.plus_notice = "선택한 날짜를 저장하지 못했습니다. 보고서는 계속 볼 수 있습니다."
    st.session_state.plus_expanded_records = set(st.session_state.get("plus_expanded_records", set())) | {identifier}


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
    origin_page = st.session_state.preventra_page
    home = origin_page == "홈"
    title = work_record_title(candidate)
    current = next((row for row in st.session_state.preventra_recent
                    if row.conversation_id == st.session_state.preventra_conversation_id), None)
    current_is_matching_work = (
        current is not None
        and getattr(current, "record_type", "chat") == "work"
        and "".join(current.title.casefold().split()) == "".join(title.casefold().split())
    )
    target_id = st.session_state.preventra_conversation_id if current_is_matching_work else None
    if target_id is None:
        try:
            target_id = get_store().find_work_by_title(title)
        except Exception:
            st.session_state.plus_notice = "기존 작업 목록을 확인하지 못했습니다. 저장소 연결을 확인한 뒤 다시 시도해 주세요."
            st.warning(st.session_state.plus_notice)
            return
    if target_id and target_id != st.session_state.preventra_conversation_id:
        state.open_conversation(target_id, destination="홈")
        try:
            st.session_state.plus_saved = get_plan_store().load(target_id)
            st.session_state.plus_loaded_id = target_id
        except Exception:
            st.session_state.plus_notice = "기존 작업 기록을 불러오지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요."
            st.warning(st.session_state.plus_notice)
            return
    elif target_id is None:
        needs_new_record = current is not None and (
            getattr(current, "record_type", "chat") == "work" or getattr(current, "has_messages", False))
        is_other_work = (current is not None and getattr(current, "record_type", "chat") == "work"
                         and not current_is_matching_work)
        if is_other_work or (home and needs_new_record) or not st.session_state.preventra_conversation_id:
            old = st.session_state.preventra_conversation_id
            state.new_chat()
            if old == st.session_state.preventra_conversation_id:
                return
            st.session_state.plus_loaded_id = st.session_state.preventra_conversation_id
            st.session_state.plus_saved = SavedPlan()
    previous_snapshot = st.session_state.plus_saved.snapshot
    if previous_snapshot:
        previous_plan = domain.decode_plan(previous_snapshot["plan"])
        merged_plan = domain.merge_site_plans(previous_plan, candidate)
    else:
        merged_plan = candidate
    work_days = sorted({item.day for item in candidate.items})
    value = domain.snapshot(merged_plan, work_days[0])
    if save(value):
        try:
            get_store().set_work_title(st.session_state.preventra_conversation_id,
                                       title, sorted({item.day for item in merged_plan.items}))
        except Exception:
            st.session_state.plus_notice = "작업계획서는 저장했지만 기록 이름을 저장하지 못했습니다. 기록 저장소 연결을 확인해 주세요."
        state.refresh_recent()
        st.session_state.plus_home_upload_open = False
        st.session_state.plus_home_upload_for = st.session_state.preventra_conversation_id
        for key in ("plus_day", "plus_work"):
            st.session_state.pop(key, None)
        st.session_state.plus_brief_scope = "day"
        st.session_state.plus_selected_record_id = st.session_state.preventra_conversation_id
        st.session_state.plus_selected_record_day = work_days[0]
        st.session_state.plus_day = work_days[0]
        st.session_state.plus_expanded_records = set(st.session_state.get("plus_expanded_records", set())) | {st.session_state.preventra_conversation_id}
        st.session_state.plus_candidate = None
        st.session_state.plus_candidate_token = None
        st.session_state.plus_upload_generation += 1
        state.navigate("홈")
        st.rerun()


def _table(items):
    return [{"시간": f"{i.start:%H:%M}–{i.end:%H:%M}", "구역": i.area,
             "작업": i.activity, "장비": i.equipment or "미입력",
             "출처": f"{i.sheet} {i.row}행"} for i in items]


def render_plan(*, show_upload=True, show_context=True):
    if st.session_state.plus_notice:
        st.warning(st.session_state.plus_notice)
    if st.session_state.plus_load_failed:
        st.button("계획 다시 불러오기", key="plus_reload")
        return
    if show_upload:
        with st.container(key="plus_plan_upload"):
            st.html('''<div class="plus-upload-heading"><span class="plus-upload-step">01</span>
              <div><h2>작업계획서 업로드</h2><p>Excel 계획서를 불러오면 날짜와 작업 정보를 읽어 오늘의 브리핑을 준비합니다.</p></div></div>''')
            st.caption(".xlsx 파일 · 10MB 이하 · 원본 파일은 저장하지 않습니다.")
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
                from preventra_plan.report import _render_plan_brief, plan_timeline
                days = sorted({item.day for item in candidate.items})
                preview_day = st.selectbox("미리볼 작업일", days, key="plus_preview_" + st.session_state.plus_candidate_token)
                preview_items = domain.daily_rows(candidate, preview_day)
                st.caption("적용 전 보고서 미리보기 · 계획서 적용 후 이력에 저장되고 후속 질문에 연결됩니다.")
                with st.container(key="plus_upload_preview"):
                    _render_plan_brief(candidate, preview_day, preview_items, "하루 전체")
                    st.plotly_chart(plan_timeline(preview_items, preview_day), width="stretch",
                                    config={"displayModeBar": False}, key="plus_preview_timeline")
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
    if not value or not show_context:
        return
    plan = domain.decode_plan(value["plan"])
    st.markdown("### 작업계획 요약")
    st.text(plan.site)
    st.session_state.setdefault("plus_day", date.fromisoformat(value["day"]))
    day_column, work_column = st.columns([1, 2])
    with day_column:
        day = st.date_input("계획 기준일", key="plus_day", disabled=blocked(), on_change=select_day)
    items = domain.daily_rows(plan, day)
    options = [""] + [i.work_id for i in items]
    st.session_state.setdefault('plus_work', value.get('work_id') or '')
    if st.session_state.get("plus_work") not in options:
        st.session_state.plus_work = ""
    labels = {i.work_id: domain.work_selection_label(i) for i in items}
    with work_column:
        selected = st.selectbox("질문할 작업", options, format_func=lambda value: labels.get(value, "해당 날짜 전체"),
                                key="plus_work", disabled=blocked(), on_change=select_work)
    st.caption(f"계획서 질문의 ‘오늘·오전·오후’는 선택한 {day:%Y-%m-%d} 기준입니다. 다른 날짜는 질문에 적어 주세요.")
    if not items:
        st.info(f"{day:%Y-%m-%d}에 등록된 작업이 없습니다. 계획서의 작업일을 선택해 주세요.")
        st.caption("수록 날짜: " + ", ".join(d.isoformat() for d in sorted({i.day for i in plan.items})))
    else:
        shown = [i for i in items if not selected or i.work_id == selected]
        with st.expander(f'계획 내용 확인 · 작업 {len(shown)}개', expanded=False):
            st.dataframe(_table(shown), hide_index=True, width="stretch")
            for item in shown[:20]:
                st.markdown('**' + domain.work_selection_label(item) + '**')
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
