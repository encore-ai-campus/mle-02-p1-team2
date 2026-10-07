"""Separate Streamlit page for the SANUP-P source-grounded chatbot."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import date
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from shining_chatbot.chat_data import answer_data_question, chart_frame, markdown_label
from shining_chatbot.business_time import now_korea, today_korea
from shining_chatbot.briefing_report import safety_briefing_html
from shining_chatbot.field_chat import briefing_work_day, field_intent, field_quick_answer, requested_weather_day
from shining_chatbot.field_session import clear_site_context
from shining_chatbot.incident_data import read_incidents_csv, sample_incidents
from shining_chatbot.infographics import monthly_infographic
from shining_chatbot.plan_revision import make_revision
from shining_chatbot.tbm_data import daily_items
from shining_chatbot.weather_data import forecast_summary, summarize_work_window, work_weather_notes
from shining_chatbot.weather_panel import resolve_plan_weather_location, weather_for_day
from shining_chatbot.work_plan import WorkPlan, read_work_plan, work_selection_label


DEFAULT_ROOT = Path(r"C:\SANUP-P")
SAMPLE_WORK_PLAN = Path(__file__).parent / "static" / "sample_work_plan.xlsx"
SOURCE_OPTIONS = {
    "전체 자료": "all",
    "SIF 사고사례": "sif",
    "사고조사보고서": "moel_report",
    "KOSHA GUIDE": "kosha_guide",
}
SEARCH_OPTIONS = {
    "의미 검색": "semantic",
    "문자·의미 혼합": "hybrid_rrf",
    "문자 검색": "lexical",
}


def _selected_search_mode(has_key: bool, saved_mode: object = None) -> str:
    """Choose a retrieval mode from configuration, while respecting old session settings."""
    if isinstance(saved_mode, str) and saved_mode in SEARCH_OPTIONS:
        return SEARCH_OPTIONS[saved_mode]
    if isinstance(saved_mode, str) and saved_mode in SEARCH_OPTIONS.values():
        return saved_mode
    return "hybrid_rrf" if has_key else "lexical"
ERROR_MESSAGES = {
    "index_readonly": "SANUP-P 검색 색인의 쓰기 권한이 없어 열지 못했습니다. 앱을 색인에 접근할 수 있는 사용자 계정으로 실행해 주세요.",
    "index_invalid": "SANUP-P 검색 색인과 문서 데이터가 일치하지 않습니다. SANUP-P에서 색인 상태를 확인해 주세요.",
    "semantic_key_missing": "의미 검색에 사용할 OpenAI API 키를 찾지 못했습니다. 키를 설정하거나 문자 검색을 선택해 주세요.",
    "AuthenticationError": "OpenAI API 키 인증에 실패했습니다. SANUP-P의 API 키를 확인해 주세요.",
    "PermissionDeniedError": "설정된 OpenAI 모델에 접근할 수 없습니다. SANUP-P의 OPENAI_MODEL 설정을 확인해 주세요.",
    "NotFoundError": "설정된 OpenAI 모델을 찾지 못했습니다. SANUP-P의 OPENAI_MODEL 설정을 확인해 주세요.",
    "RateLimitError": "OpenAI API 요청 한도에 도달했습니다. 계정 사용량과 결제 설정을 확인한 뒤 다시 시도해 주세요.",
    "APIConnectionError": "OpenAI API에 연결하지 못했습니다. 네트워크 연결을 확인한 뒤 다시 시도해 주세요.",
    "APITimeoutError": "OpenAI API 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.",
    "Timeout": "검색 또는 답변 시간이 초과됐습니다. 검색 조건을 좁혀 다시 시도해 주세요.",
    "RuntimeUnavailable": "SANUP-P 가상환경을 실행하지 못했습니다. 연결 경로와 가상환경을 확인해 주세요.",
    "InvalidResponse": "챗봇 실행 결과를 읽지 못했습니다. SANUP-P 실행 환경을 확인해 주세요.",
}


def _safe_external_url(value: object) -> str | None:
    """Keep malformed or non-web source links from breaking the chat page."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if (
        not candidate or len(candidate) > 2048
        or any(ord(char) < 32 or char.isspace() or char == "\\" for char in candidate)
    ):
        return None
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    try:
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return None
    except ValueError:
        return None
    return candidate


def _root() -> Path:
    return Path(os.getenv("SANUP_P_ROOT", str(DEFAULT_ROOT))).expanduser()


def _has_api_key(root: Path) -> bool:
    if os.getenv("OPENAI_API_KEY", "").strip():
        return True
    try:
        for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "OPENAI_API_KEY" and value.strip().strip("\"'"):
                return True
    except OSError:
        pass
    return False


def _missing_files(root: Path) -> list[str]:
    required = (
        ".venv/Scripts/python.exe",
        "src/retriever.py",
        "src/rag_chain.py",
        "data/personal/corpus/chunks.jsonl",
        "data/personal/corpus/index_meta.json",
        "data/personal/corpus/index_meta_semantic.json",
        "chroma_db/personal/chroma.sqlite3",
    )
    return [item for item in required if not (root / item).is_file()]


def ask_sanup(root: Path, request: dict) -> dict:
    bridge = Path(__file__).with_name("rag_bridge.py")
    command = [str(root / ".venv/Scripts/python.exe"), "-X", "utf8", str(bridge), str(root)]
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=150,
            cwd=root,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "code": "Timeout", "answer": "", "sources": []}
    except OSError:
        return {"status": "error", "code": "RuntimeUnavailable", "answer": "", "sources": []}
    try:
        result = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError, RecursionError):
        return {"status": "error", "code": "InvalidResponse", "answer": "", "sources": []}
    if not isinstance(result, dict):
        return {"status": "error", "code": "InvalidResponse", "answer": "", "sources": []}
    if not isinstance(result.get("status"), str):
        return {"status": "error", "code": "InvalidResponse", "answer": "", "sources": []}
    if result["status"] == "answered" and not isinstance(result.get("answer"), str):
        return {"status": "error", "code": "InvalidResponse", "answer": "", "sources": []}
    sources = result.get("sources") or []
    if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
        return {"status": "error", "code": "InvalidResponse", "answer": "", "sources": []}
    result["sources"] = sources
    return result


def _show_sources(sources: list[dict], *, verified: bool = True) -> None:
    if not sources:
        return
    label = "근거 문서" if verified else "검색된 문서"
    with st.expander(f"{label} {len(sources)}건", expanded=True):
        for source in sources:
            number = source.get("number", "")
            title = source.get("title") or "제목 없음"
            organization = str(source.get("organization") or "")
            page = source.get("page")
            detail = " · ".join(
                item for item in (organization, f"{page}쪽" if page else "") if item
            )
            with st.container(border=True):
                st.markdown(f"**[{markdown_label(number)}] {markdown_label(title)}**")
                if detail:
                    st.caption(markdown_label(detail))
                if source.get("ocr_review_required"):
                    st.caption("OCR 자동 인식 · PDF 원문 대조 필요")
                url = _safe_external_url(source.get("url"))
                if url:
                    st.link_button("원문 보기 ↗", url)


def _show_message(message: dict, incidents: pd.DataFrame) -> None:
    avatar = ":material/person:" if message["role"] == "user" else ":material/auto_awesome:"
    with st.chat_message(message["role"], avatar=avatar):
        briefing = message.get("briefing") if message["role"] == "assistant" else None
        if isinstance(briefing, dict):
            st.markdown(safety_briefing_html(briefing), unsafe_allow_html=True)
        else:
            content = message["content"] if message.get("tbm") else message["content"].replace("- [ ] ", "- ")
            st.markdown(content)
        if message["role"] == "assistant":
            if chart := message.get("chart"):
                try:
                    if not isinstance(chart, dict):
                        raise ValueError("invalid chart")
                    chart_data, start, end = chart_frame(incidents, chart)
                    infographic = monthly_infographic(chart_data, start, end, chart.get("id", "chat-chart"))
                except (KeyError, TypeError, ValueError, OverflowError):
                    st.info("저장된 그래프 조건을 현재 자료에서 읽지 못했습니다. 월별 사고 그래프를 다시 요청해 주세요.")
                else:
                    st.markdown(infographic, unsafe_allow_html=True)
            _show_sources(message.get("sources") or [], verified=message.get("status") == "answered")
            cta = message.get("cta")
            if isinstance(cta, dict) and cta.get("view") in {"field", "actions", "tbm"}:
                if st.button(
                    cta.get("label", "관련 화면 열기"),
                    key=f"field_answer_cta_{message.get('id', 'latest')}",
                ):
                    target_day = None
                    if isinstance(cta.get("day"), str):
                        try:
                            target_day = date.fromisoformat(cta["day"])
                        except ValueError:
                            target_day = None
                    if target_day is not None:
                        st.session_state["field_day"] = target_day
                    target_view = cta["view"]
                    if target_view == "field" and target_day is not None:
                        plan: WorkPlan | None = st.session_state.get("field_plan")
                        target_item = next(
                            (item for item in plan.items if item.day == target_day), None,
                        ) if plan else None
                        if target_item is not None:
                            st.session_state["field_item_choice"] = target_item.work_id
                    if target_view == "tbm" and target_day is not None:
                        st.session_state["tbm_day"] = target_day
                    elif target_view == "actions":
                        st.session_state["field_action_filter"] = "미완료"
                        st.session_state["field_action_query"] = ""
                        action_id = cta.get("action_id")
                        action = next(
                            (entry for entry in st.session_state.get("field_actions", ()) if entry.action_id == action_id),
                            None,
                        )
                        if action is not None:
                            st.session_state["field_selected_action"] = action.action_id
                    st.session_state["view"] = target_view
                    st.query_params["page"] = target_view
                    st.rerun()


def _clear_chat_context() -> None:
    for key in ("rag_context", "rag_equipment", "rag_industry"):
        st.session_state.pop(key, None)


def _render_chat_landing(has_conversation: bool = False) -> None:
    """Keep the start screen focused on the single-line safety prompt."""
    if has_conversation:
        st.markdown(
            '<div class="chat-conversation-active" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        '<section class="chat-landing-welcome" aria-label="안전 브리핑 시작">'
        '<div class="welcome-blue-haze"></div>'
        '<div class="welcome-window-edges"></div>'
        '<div class="safety-intro-scene" aria-hidden="true">'
        '<div class="safety-intro-pane"><span class="safety-intro-overline">FIELD NOTE / 01</span>'
        '<span class="safety-intro-title">&#xC624;&#xB298;&#xC758; &#xD604;&#xC7A5;&#xC744;<br>&#xC548;&#xC804;&#xD558;&#xAC8C; &#xBE0C;&#xB9AC;&#xD551;</span>'
        '<span class="safety-intro-rule"></span></div>'
        '<div class="safety-intro-sheen"></div>'
        '<div class="safety-intro-worker"><img src="/app/static/intro_safety_worker.png" alt=""></div>'
        '<div class="safety-intro-brand"><span class="safety-intro-mark"><svg viewBox="0 0 40 40"><path d="M20 3.5 34 9v9.2c0 8.4-5.7 14.8-14 18.3C11.7 33 6 26.6 6 18.2V9l14-5.5Z"/><path d="m13.5 20 4.2 4.2 9-9"/></svg></span>'
        '<span><strong>Safety Atlas</strong><small>&#xD604;&#xC7A5; &#xC548;&#xC804; &#xBE0C;&#xB9AC;&#xD551;</small></span></div>'
        '</div>'
        '<div class="chat-stage-intro">'
        '<span class="chat-stage-kicker"><i></i> FIELD SAFETY · DAILY BRIEFING</span>'
        '<h1>오늘 현장의 안전,<br><em>한눈에 브리핑</em></h1>'
        '<p>작업계획서를 올리고 질문하면 일정과 유사 사고, 날씨를 정리해 드려요.</p>'
        '</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def show_chatbot(incidents: pd.DataFrame, source_name: str, is_sample: bool, data_token: str) -> None:
    root = _root()
    missing = _missing_files(root)
    has_key = _has_api_key(root)
    ready = not missing
    field_plan: WorkPlan | None = st.session_state.get("field_plan")
    field_day = st.session_state.get("field_day")
    if not isinstance(field_day, date):
        field_day = today_korea()

    briefing_prompt = st.session_state.pop("_daily_briefing_requested", None)
    has_conversation = any(
        isinstance(message, dict) and message.get("role") == "user"
        for message in st.session_state.get("rag_messages", ())
    ) or isinstance(briefing_prompt, str)
    _render_chat_landing(has_conversation)
    st.html(
        """<script>
(() => {
  if (window.__safetyAtlasPointerGlass) return;
  window.__safetyAtlasPointerGlass = true;
  let releaseTimer = 0;
  const alignTopLink = () => {
    const stage = document.querySelector('body:has(.chat-landing-welcome) .block-container, body:has(.chat-conversation-active) .block-container');
    const link = document.querySelector('.scroll-top-link');
    if (!stage || !link) return;
    const rect = stage.getBoundingClientRect();
    link.style.setProperty('position', 'fixed', 'important');
    link.style.setProperty('right', `${Math.max(14, window.innerWidth - rect.right + 20)}px`, 'important');
    link.style.setProperty('top', `${Math.max(12, rect.top + 12)}px`, 'important');
  };
  const scheduleAlign = () => window.requestAnimationFrame(alignTopLink);
  window.addEventListener('resize', scheduleAlign, {passive:true});
  window.addEventListener('scroll', scheduleAlign, {capture:true, passive:true});
  new MutationObserver(scheduleAlign).observe(document.body, {childList:true, subtree:true});
  scheduleAlign();
  document.addEventListener('pointermove', (event) => {
    const stage = document.querySelector('body:has(.chat-landing-welcome) .block-container, body:has(.chat-conversation-active) .block-container');
    if (!stage) return;
    const surfaces = [stage, document.querySelector('[data-testid="stApp"]')].filter(Boolean);
    const setDrift = (x, y) => surfaces.forEach((surface) => {
      surface.style.setProperty('--stage-drift-x', x);
      surface.style.setProperty('--stage-drift-y', y);
    });
    const overComposer = event.target.closest?.('[data-testid="stChatInput"], .st-key-daily_briefing_upload');
    if (overComposer) {
      window.clearTimeout(releaseTimer);
      stage.classList.remove('pointer-glass-active');
      setDrift('0px', '0px');
      return;
    }
    window.clearTimeout(releaseTimer);
    const x = event.clientX / Math.max(1, window.innerWidth);
    const y = event.clientY / Math.max(1, window.innerHeight);
    // Shift the broad background/reflection plane across the whole landing view.
    // The pointer never gets its own light, glow, or graphic.
    setDrift(`${((.5 - x) * 58).toFixed(1)}px`, `${((.5 - y) * 40).toFixed(1)}px`);
    stage.classList.add('pointer-glass-active');
  }, {capture:true, passive:true});
  document.addEventListener('pointerout', (event) => {
    if (event.relatedTarget) return;
    const stage = document.querySelector('body:has(.chat-landing-welcome) .block-container, body:has(.chat-conversation-active) .block-container');
    if (!stage) return;
    stage.style.setProperty('--stage-drift-x', '0px');
    stage.style.setProperty('--stage-drift-y', '0px');
    const canvas = document.querySelector('[data-testid="stApp"]');
    canvas?.style.setProperty('--stage-drift-x', '0px');
    canvas?.style.setProperty('--stage-drift-y', '0px');
    stage.classList.remove('pointer-glass-active');
  }, {capture:true, passive:true});
})();
</script>""",
        unsafe_allow_javascript=True,
    )
    if missing:
        st.info(
            f"현장 작업·조치·TBM 질문과 CSV 조회는 사용할 수 있습니다. "
            f"SANUP-P 문서 검색은 {root}의 필요 파일 {len(missing)}개가 없어 연결되지 않았습니다."
        )
    elif not has_key:
        st.info("OpenAI API 키가 없어 문자 검색으로 근거 문서만 보여줍니다. 답변 생성은 SANUP-P의 .env에 키를 설정하면 사용할 수 있습니다.")

    if "_chat_openai_default_initialized" not in st.session_state:
        st.session_state["chat_openai_consent"] = has_key
        st.session_state["_chat_openai_default_initialized"] = True

    show_plan_upload = True
    if show_plan_upload:
        attached = None
        work_file = None
        upload_label = "작업계획서 교체" if field_plan is not None else "작업계획서 첨부"
        with st.popover(
            upload_label,
            icon=":material/attach_file:",
            key="daily_briefing_upload",
            width="content",
        ):
            st.markdown(
                '<div class="chat-upload-title"><h3>작업계획서</h3>'
                '<p>엑셀을 첨부하면 일정과 현장 지역을 읽어 브리핑을 준비합니다.</p></div>',
                unsafe_allow_html=True,
            )
            work_file = st.file_uploader(
                "엑셀 계획서", type="xlsx", key="chat_work_file", max_upload_size=10,
            )
            st.download_button(
                "샘플 계획서 다운로드",
                data=SAMPLE_WORK_PLAN.read_bytes(),
                file_name="가상_아파트_주간작업계획서.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="chat_plan_sample_download",
                width="stretch",
            )
            if work_file is not None:
                try:
                    attached = read_work_plan(work_file.getvalue())
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    if attached.issues:
                        st.warning(f"읽지 못한 행 {len(attached.issues)}건이 있습니다. 원본 계획서를 확인해 주세요.")
                    if attached.site_location:
                        st.markdown(
                            f'<div class="chat-plan-location"><span>예보 위치</span>'
                            f'<strong>{escape(attached.site_location)}</strong></div>',
                            unsafe_allow_html=True,
                        )
                    plan_days = sorted({item.day for item in attached.items})
                    if plan_days:
                        default_day = today_korea() if today_korea() in plan_days else plan_days[0]
                        selected_day = st.selectbox(
                            "브리핑 날짜", plan_days, index=plan_days.index(default_day), key="daily_briefing_day",
                            format_func=lambda value: f"{value:%Y년 %m월 %d일}" + (" · 오늘" if value == today_korea() else ""),
                        )
                        daily = [item for item in attached.items if item.day == selected_day]
                        st.markdown(
                            f'<div class="chat-plan-preview-head"><strong>{escape(attached.site)}</strong>'
                            f'<span>{selected_day:%m.%d} · 작업 {len(daily)}건</span></div>',
                            unsafe_allow_html=True,
                        )
                        for item in daily[:4]:
                            st.markdown(f"`{item.start:%H:%M}–{item.end:%H:%M}`　{markdown_label(item.activity)}")
                        if len(daily) > 4:
                            st.caption(f"외 {len(daily) - 4}개 작업")
                        briefing_label = "오늘" if selected_day == today_korea() else f"{selected_day:%m.%d}"
                        if st.button(f"{briefing_label} 안전 브리핑 보기", type="primary", key="daily_briefing_apply", width="stretch"):
                            previous: WorkPlan | None = st.session_state.get("field_plan")
                            st.session_state["field_plan"] = attached
                            st.session_state["chat_change_plan_open"] = False
                            st.session_state["field_plan_name"] = work_file.name
                            st.session_state["field_plan_applied_at"] = now_korea().isoformat(timespec="seconds")
                            st.session_state["field_day"] = selected_day
                            with st.spinner("계획서 지역으로 날씨 예보 위치를 연결하는 중..."):
                                weather_location, weather_status = resolve_plan_weather_location(attached.site_location)
                            st.session_state["field_weather_location"] = weather_location
                            st.session_state["field_weather_plan_status"] = weather_status
                            st.session_state.pop("field_location_candidates", None)
                            st.session_state.pop("field_weather_error", None)
                            st.session_state["field_revisions"] = (*st.session_state.get("field_revisions", ()), make_revision(previous, attached, work_file.name))
                            st.session_state["rag_context"] = " / ".join(item.activity for item in daily)
                            st.session_state["rag_industry"] = "건설업"
                            st.session_state["_daily_briefing_requested"] = (
                                "오늘 주의사항" if selected_day == today_korea() else "선택일 주의사항"
                            )
                            st.rerun()
                    else:
                        st.warning("작업계획서에서 일정 행을 찾지 못했습니다. 날짜와 작업명 열을 확인해 주세요.")

    chat_col = st.container()
    with st.expander("사고 통계·답변 설정", expanded=False):
            incident_file = st.file_uploader("사고 기록 CSV", type="csv", key="chat_incident_csv", max_upload_size=25)
            st.download_button(
                "CSV 샘플 받기",
                data=sample_incidents().to_csv(index=False).encode("utf-8-sig"),
                file_name="산업재해_샘플.csv",
                mime="text/csv",
                key="chat_incident_sample_download",
            )
            if incident_file is not None:
                try:
                    uploaded_incidents = read_incidents_csv(incident_file.getvalue())
                except ValueError as exc:
                    st.warning(f"사고 CSV를 읽지 못해 기존 자료를 사용합니다. {markdown_label(exc)}")
                else:
                    if not is_sample:
                        incident_scope = st.selectbox(
                            "통계 범위", ("현장 기록", "전체 CSV"), key="chat_incident_source",
                        )
                    else:
                        incident_scope = "전체 CSV"
                    if incident_scope == "전체 CSV":
                        incidents = uploaded_incidents
                        source_name = incident_file.name
                        is_sample = False
                        data_token = f"uploaded:{sha256(incident_file.getvalue()).hexdigest()}"
            st.caption("업로드한 CSV는 사고 통계 질문에 사용됩니다. 파일을 올리지 않으면 현재 연결된 자료를 사용합니다.")
            if st.session_state.get("_chat_data_token") != data_token:
                st.session_state.rag_messages = []
                st.session_state["_chat_data_token"] = data_token
                st.session_state["chat_openai_consent"] = has_key
            source_label = st.selectbox("자료 종류", list(SOURCE_OPTIONS), key="rag_source")
            preferred_mode = _selected_search_mode(has_key, st.session_state.get("rag_mode"))
            st.session_state["rag_mode"] = preferred_mode
            allow_openai = False
            if has_key:
                allow_openai = st.toggle(
                    "OpenAI API로 답변 생성 허용",
                    key="chat_openai_consent",
                    help="켜면 질문, 작업 맥락, 선택한 검색 조건, 최근 대화 일부와 검색된 근거 문서 일부를 OpenAI API에 보냅니다.",
                )
                st.caption(
                    "전송 범위: 질문·작업 맥락·업종/장비·최근 대화 일부·검색 근거 일부. "
                    "현장명, 작업자 이름, 연락처 등 민감정보는 입력하지 마세요. "
                    "자료 외부 전송이 허용되는 조직 정책인지 확인한 뒤 켜세요. "
                    "작업 상태와 CSV 통계 질문은 로컬에서 처리합니다. "
                    "끄면 근거 문서도 로컬 문자 검색과 출처 확인만 합니다."
                )
            mode_code = preferred_mode if allow_openai else "lexical"
            work_context = st.text_area(
                "현재 작업",
                key="rag_context",
                placeholder="예: 건설현장 이동식 사다리 점검",
                height=86,
                max_chars=1000,
            )
            if work_context.strip():
                st.caption("선택한 작업 맥락이 아래 문서 검색 질문에 함께 적용됩니다.")
                st.button(
                    "작업 조건 초기화", key="chat_clear_context",
                    on_click=_clear_chat_context,
                )
            industry = st.text_input("업종", key="rag_industry", placeholder="예: 건설업", max_chars=100)
            equipment = st.text_input("장비·기인물", key="rag_equipment", placeholder="예: 사다리", max_chars=200)
            st.caption("이 조건은 근거 문서 검색에 적용됩니다. 지역·월별 질문은 표시된 통계 자료를 사용하며, 자료를 바꾸면 대화가 초기화됩니다.")

    with chat_col:
        if st.session_state.rag_messages:
            clear_col, _ = st.columns([1, 5])
            with clear_col:
                if st.button("대화 지우기", key="chat_clear_messages", help="현재 대화만 지웁니다."):
                    st.session_state.rag_messages = []
                    st.rerun()
            for message in st.session_state.rag_messages:
                _show_message(message, incidents)

        field_prompt = briefing_prompt if isinstance(briefing_prompt, str) else None
        prompt = st.chat_input("예: 오늘 오전 작업자에게 공유할 안전 브리핑을 정리해줘", max_chars=2000)
        if field_prompt:
            prompt = field_prompt
        if not prompt:
            return

        history = st.session_state.rag_messages[-6:]
        user_message = {"role": "user", "content": prompt}
        st.session_state.rag_messages.append(user_message)
        weather_text = ""
        weather_notes = ()
        weather_windows = ()
        answer_intent = field_intent(prompt)
        weather_day = None
        if field_plan and answer_intent in {"오늘주의사항", "선택일주의사항", "현장날씨", "안전교육브리핑"}:
            location = st.session_state.get("field_weather_location")
            weather_day = (
                requested_weather_day(prompt) if answer_intent == "현장날씨"
                else today_korea() if answer_intent == "오늘주의사항"
                else briefing_work_day(field_plan, field_day) if answer_intent == "안전교육브리핑"
                else field_day
            )
            if location is None and answer_intent == "안전교육브리핑" and field_plan.site_location:
                with st.spinner("작업계획서의 현장 지역으로 예보 위치를 찾는 중..."):
                    location, weather_status = resolve_plan_weather_location(field_plan.site_location)
                if location is not None:
                    st.session_state["field_weather_location"] = location
                st.session_state["field_weather_plan_status"] = weather_status
            if location is None and answer_intent == "안전교육브리핑":
                weather_status = st.session_state.get("field_weather_plan_status")
                weather_text = (
                    f"예보 미연결 · {weather_status}"
                    if weather_status else
                    "예보 미연결 · 계획서에 현장 지역(시·군·구)을 입력하면 해당 지역 예보를 연결할 수 있습니다."
                )
            forecast = weather_for_day(weather_day) if location else None
            if forecast is not None:
                weather_text = forecast_summary(location, forecast)
                briefing_items = daily_items(field_plan, weather_day)
                weather_notes = work_weather_notes(
                    tuple(item.activity for item in briefing_items), forecast,
                )
                if answer_intent == "안전교육브리핑":
                    weather_windows = tuple(
                        summarize_work_window(item, forecast)
                        for item in briefing_items if item.start.hour < 12
                    )
        field_answer = field_quick_answer(
            prompt, field_plan, field_day,
            st.session_state.get("field_reviews", {}),
            tuple(st.session_state.get("field_actions", ())),
            st.session_state.get("field_tbm_records", {}),
            st.session_state.get("field_tbm_deliveries", {}),
            tuple(st.session_state.get("field_revisions", ())),
            weather_text, weather_notes, weather_day,
            weather_windows,
        )
        if field_answer is not None:
            st.session_state.rag_messages.append(field_answer)
            st.rerun()
        local_answer = answer_data_question(
            prompt, incidents, is_sample=is_sample, history=history,
            source_label=source_name,
        )
        if local_answer is not None:
            st.session_state.rag_messages.append(local_answer)
            st.rerun()
        _show_message(user_message, incidents)
        if not ready:
            st.session_state.rag_messages.append({
                "role": "assistant",
                "status": "error",
                "content": "SANUP-P 문서 색인에 연결할 수 없습니다. 왼쪽 CSV 관리에서 지역·월별 사고 질문은 계속 사용할 수 있습니다.",
            })
            st.rerun()
        request = {
            "question": prompt,
            "source": SOURCE_OPTIONS[source_label],
            "mode": mode_code,
            "generate": allow_openai,
            "work_context": work_context,
            "industry_major": industry,
            "equipment": equipment,
            "history": history,
            "tbm": "TBM" in prompt.upper(),
        }
        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
            with st.spinner("근거 문서를 검색하고 인용을 확인하는 중..."):
                result = ask_sanup(root, request)
            status = result.get("status")
            if status not in {
                "answered", "insufficient_evidence", "llm_key_missing", "generation_disabled", "unsupported_citation",
                "malformed_quantity", "empty_response", "error",
            }:
                status = markdown_label(status or "unknown")
            if status == "answered":
                answer = result.get("answer") or "답변을 받지 못했습니다."
            elif status == "insufficient_evidence":
                answer = "제공된 근거 자료에서 답을 확인할 수 없습니다. 작업·장비·사고 유형을 더 구체적으로 적어 주세요."
            elif status == "llm_key_missing":
                answer = "관련 문서는 찾았습니다. 답변 생성을 사용하려면 SANUP-P의 OpenAI API 키를 설정해 주세요."
            elif status == "generation_disabled":
                answer = "외부 AI 답변 생성이 꺼져 있어 검색된 근거 문서만 표시합니다. 답변 생성이 필요하면 질문 설정에서 OpenAI 전송을 켜세요."
            elif status in {"unsupported_citation", "malformed_quantity", "empty_response"}:
                answer = "관련 문서는 찾았지만 생성된 답변의 인용을 검증하지 못했습니다. 아래 검색 문서를 직접 확인하거나 질문을 더 구체적으로 적어 주세요."
            elif status == "error":
                code = markdown_label(str(result.get("code") or "UnknownError"))
                answer = ERROR_MESSAGES.get(code, f"검색 실행 중 오류가 발생했습니다. 오류 코드: {code}. 이 코드를 알려주시면 원인을 확인하겠습니다.")
            else:
                answer = f"답변 상태를 확인할 수 없습니다. 상태 코드: {status or 'unknown'}."
            st.markdown(answer)
            sources = (result.get("sources") or []) if status in {
                "answered", "insufficient_evidence", "llm_key_missing",
                "generation_disabled", "unsupported_citation", "malformed_quantity", "empty_response",
            } else []
            _show_sources(sources, verified=status == "answered")
        st.session_state.rag_messages.append(
            {"role": "assistant", "content": answer, "sources": sources, "tbm": "TBM" in prompt.upper(), "status": status}
        )
        st.rerun()
