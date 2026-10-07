"""Fast answers from the current field session, without external generation."""

from __future__ import annotations

from datetime import date, timedelta
import re
from uuid import uuid4

from shining_chatbot.action_data import FieldAction, action_attention_flags, action_due_kst
from shining_chatbot.business_time import now_korea, today_korea
from shining_chatbot.case_summary import summarize_cases
from shining_chatbot.plan_revision import PlanRevision, day_revision_token
from shining_chatbot.record_pattern import SEASONS, season_index
from shining_chatbot.tbm_data import TbmDelivery, TbmRecord, daily_actions, daily_items
from shining_chatbot.weather_data import WorkWindowSummary
from shining_chatbot.work_plan import (
    WorkPlan,
    coordination_candidates,
    is_plan_field_missing,
    missing_work_fields,
)


def _safe(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+!|>])", r"\\\1", value)


def field_intent(prompt: str) -> str | None:
    compact = re.sub(r"\s+", "", prompt).lower()
    exact = {
        "선택일작업요약": "선택일작업요약", "오늘작업요약": "오늘작업요약",
        "오늘주의사항": "오늘주의사항", "선택일주의사항": "선택일주의사항",
        "오늘날씨": "현장날씨", "현장날씨": "현장날씨",
        "남은조치": "남은조치",
        "TBM준비상태": "TBM준비상태", "최근계획변경": "최근계획변경",
        "오늘달라진점": "오늘달라진점",
    }
    if compact in exact:
        return exact[compact]
    if any(term in compact for term in ("안전교육", "브리핑", "작업전교육", "tbm")) and any(
        term in compact for term in ("오늘", "오전", "오후", "작업", "교육", "정리", "안내")
    ):
        return "안전교육브리핑"
    if any(term in compact for term in ("주의사항", "주의할점", "유의사항", "유의할점")) and "선택일" in compact:
        return "선택일주의사항"
    if any(term in compact for term in ("주의사항", "주의할점", "유의사항", "유의할점")) and "오늘" in compact:
        return "오늘주의사항"
    weather_terms = (
        "날씨", "기상", "기온", "강수", "풍속", "바람", "폭염", "한파",
        "강풍", "호우", "장마", "비와", "비오", "비예보", "눈와", "눈오", "눈올", "눈예보",
        "춥", "덥",
    )
    historical_terms = ("사고", "기록", "통계", "월별", "경향", "과거")
    if any(term in compact for term in weather_terms) and not any(term in compact for term in historical_terms):
        return "현장날씨"
    if any(term in compact for term in ("남은조치", "미완료조치", "미처리조치")):
        return "남은조치"
    if "tbm" in compact and any(term in compact for term in ("준비", "상태", "완료")):
        return "TBM준비상태"
    if any(term in compact for term in ("최근계획변경", "계획변경", "달라진점")):
        return "최근계획변경"
    if "작업" in compact and any(term in compact for term in ("요약", "목록", "몇건")) and not any(
        term in compact for term in ("사고", "위험", "예방", "사례", "안전수칙")
    ):
        return "오늘작업요약" if "오늘" in compact else "선택일작업요약"
    return None


def requested_weather_day(prompt: str) -> date:
    compact = re.sub(r"\s+", "", prompt).lower()
    today = today_korea()
    if "모레" in compact:
        return today + timedelta(days=2)
    if "내일" in compact:
        return today + timedelta(days=1)
    return today


def briefing_work_day(plan: WorkPlan, requested_day: date) -> date:
    """Use the requested plan day, or the next upcoming workday when it is empty."""
    if daily_items(plan, requested_day):
        return requested_day
    after = max(requested_day, today_korea())
    upcoming = sorted({item.day for item in plan.items if item.day > after})
    return upcoming[0] if upcoming else requested_day


def _field_response(
    content: str, command: str | None, day: date | None = None,
    action: FieldAction | None = None,
    briefing: dict | None = None,
) -> dict:
    if command == "남은조치":
        target = "actions"
        label = "미완료 조치 열기"
    elif command == "TBM준비상태":
        target = "tbm"
        label = "TBM 브리핑 열기"
    elif day is not None:
        target = "field"
        label = "해당 날짜 작업 열기"
    else:
        target = "field"
        label = "오늘의 작업 열기"
    cta = {"view": target, "label": label}
    if day is not None:
        cta["day"] = day.isoformat()
    if action is not None:
        cta["action_id"] = action.action_id
    response = {
        "role": "assistant", "status": "field", "content": content,
        "id": uuid4().hex,
    }
    if briefing is not None:
        response["briefing"] = briefing
    else:
        response["cta"] = cta
    return response


def _season_data(day: date) -> tuple[str, str]:
    month = day.month
    if month in (3, 4, 5):
        note = "강풍·건조·황사 가능성을 살피고, 비산·낙하 위험과 호흡기 보호구 상태를 확인하세요."
    elif month in (6, 7, 8):
        note = "폭염·강한 햇빛·소나기 가능성을 살피고, 체감온도와 휴식·물·그늘 및 낙뢰 시 작업 기준을 확인하세요."
    elif month in (9, 10, 11):
        note = "큰 일교차와 건조·강풍 가능성을 살피고, 작업복·비산물 고정·화재 예방 상태를 확인하세요."
    else:
        note = "결빙·강설·저온 가능성을 살피고, 통로 미끄럼·작업발판·방한 및 한랭질환 예방 조치를 확인하세요."
    return SEASONS[season_index(month)], note


def _season_guidance(day: date) -> str:
    season, note = _season_data(day)
    return f"**계절 확인 · {season}철** · {note}"


def field_quick_answer(
    prompt: str,
    plan: WorkPlan | None,
    day: date,
    reviews: dict,
    actions: tuple[FieldAction, ...],
    tbm_records: dict[str, tuple[TbmRecord, ...]],
    tbm_deliveries: dict[str, tuple[TbmDelivery, ...]],
    revisions: tuple[PlanRevision, ...] = (),
    weather_summary: str = "",
    weather_notes: tuple[str, ...] = (),
    weather_day: date | None = None,
    weather_windows: tuple[WorkWindowSummary, ...] = (),
) -> dict | None:
    command = field_intent(prompt)
    if command is None:
        return None
    if plan is None:
        return _field_response("연결된 작업계획이 없습니다. **오늘의 작업**에서 계획서를 올리거나 일회성 작업을 추가해 주세요.", None)
    if command in {"오늘작업요약", "오늘주의사항"}:
        day = today_korea()
    if command == "현장날씨":
        day = weather_day or today_korea()
    if command == "오늘달라진점":
        day = today_korea()
    if command in {"최근계획변경", "오늘달라진점"}:
        if not revisions:
            content = "아직 적용된 계획 변경 기록이 없습니다. 새 계획서를 적용하거나 일회성 작업을 추가하면 변경 내용을 볼 수 있습니다."
        else:
            relevant = [
                (revision, tuple(entry for entry in revision.entries if entry.day == day))
                for revision in revisions
            ]
            relevant = [(revision, entries) for revision, entries in relevant if entries]
            if relevant:
                latest, entries = relevant[-1]
                lines = [f"**{day:%Y.%m.%d} 최근 계획 반영 · {latest.at:%Y.%m.%d %H:%M} · {_safe(latest.source)}**"]
                labels = {"added": "추가", "changed": "변경", "removed": "제외"}
                lines.extend(f"- {labels[entry.kind]} · {_safe(entry.activity)} ({_safe(entry.work_id)})" for entry in entries)
            else:
                lines = [f"**{day:%Y.%m.%d} 작업의 계획 변경 기록이 없습니다.**"]
            lines.append("출처: 적용한 계획의 작업ID와 내용 비교. 현장 확인 기록은 변경된 작업에서 다시 확인하세요.")
            content = "\n".join(lines)
        return _field_response(content, command, day)
    briefing_requested_day = day
    if command == "안전교육브리핑":
        day = briefing_work_day(plan, day)
    items = daily_items(plan, day)
    related = daily_actions(plan, day, actions)
    visible = {action.action_id: action for action in related}
    for action in actions:
        if action.status == "open" and action_due_kst(action).date() <= day:
            visible[action.action_id] = action
    at = now_korea()
    open_actions = sorted(
        (action for action in visible.values() if action.status == "open"),
        key=action_due_kst,
    )
    if not items:
        lines = [f"**{day:%Y.%m.%d}에 등록된 작업이 없습니다.** 계획 누락이나 일정 변경 여부를 확인해 주세요."]
        confirmation = next(
            (entry for entry in reversed(plan.no_work_confirmations) if entry.day == day),
            None,
        )
        if confirmation is not None and confirmation.revision_token == day_revision_token(revisions, day):
            lines.append(
                f"계획표 작업 없음 확인: {_safe(confirmation.confirmed_by)} · "
                f"{confirmation.at:%Y.%m.%d %H:%M} KST · 실제 현장에 작업이 없다는 안전 승인은 아닙니다."
            )
        elif confirmation is not None:
            lines.append("작업 없음 확인은 있지만 이 날짜의 계획 변경 뒤 다시 확인하지 않았습니다.")
        else:
            lines.append("이 날짜의 계획표 작업 없음 확인 기록은 없습니다.")
        if open_actions:
            lines.append(f"기한이 되었거나 재확인이 필요한 미완료 조치 {len(open_actions)}건:")
            for action in open_actions[:5]:
                flags = action_attention_flags(action, at)
                prefix = " · ".join(flags) + " · " if flags else ""
                lines.append(f"- {_safe(prefix + action.description)} · {_safe(action.assignee)} · {action_due_kst(action):%m.%d %H:%M}")
        else:
            lines.append("기한이 된 미완료 조치는 없습니다.")
        if command in {"오늘주의사항", "선택일주의사항", "현장날씨", "안전교육브리핑"}:
            lines.append(f"현장 예보: {_safe(weather_summary) if weather_summary else '예보 확인 불가 · 오늘의 작업에서 현장 위치를 연결하거나 기상청 특보를 직접 확인'}")
            lines.extend(f"예보 관련 확인: {_safe(note)}" for note in weather_notes)
        lines.append("출처: 현재 적용한 작업계획·조치 기록·연결한 모델 예보. 작업 조건은 현장에서 확인하세요.")
        return _field_response("\n".join(lines), command, day, open_actions[0] if command == "남은조치" and open_actions else None)
    if command == "현장날씨":
        forecast_day = (
            "오늘" if day == today_korea()
            else "내일" if day == today_korea() + timedelta(days=1)
            else "모레" if day == today_korea() + timedelta(days=2)
            else "선택일 현장 예보"
        )
        lines = [f"**{forecast_day} · {day:%Y.%m.%d} 현장 예보**"]
        lines.append(_safe(weather_summary) if weather_summary else "예보 위치가 연결되지 않았거나 예보를 불러오지 못했습니다. 오늘의 작업에서 현장 위치를 연결하거나 기상청 특보를 직접 확인하세요.")
        lines.extend(f"작업 관련 확인: {_safe(note)}" for note in weather_notes)
        lines.append("모델 예보는 현장 측정이나 작업 허가 기준을 대신하지 않습니다.")
        return _field_response("\n".join(lines), command, day)
    if command == "안전교육브리핑":
        morning = tuple(sorted(
            (item for item in items if item.start.hour < 12),
            key=lambda item: (item.start, item.work_id),
        ))
        weekday = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")[day.weekday()]
        location = plan.site_location.strip() or "계획서 지역 미입력"
        lines = [f"**{day.year}년 {day.month}월 {day.day}일 {weekday} · {_safe(plan.site)} · {_safe(location)} 오전 안전교육 브리핑**"]
        if day != briefing_requested_day:
            lines.append(
                f"오늘({briefing_requested_day.year}년 {briefing_requested_day.month}월 {briefing_requested_day.day}일) 오전 계획 작업이 없어, "
                f"아래 내용은 계획서의 다음 작업일({day.year}년 {day.month}월 {day.day}일) 사전 브리핑입니다."
            )
        if not morning:
            lines.append("오늘 오전 계획 작업이 없습니다. 계획서의 날짜와 현장 일정을 확인해 주세요.")
            later = tuple(item for item in items if item.start.hour >= 12)
            if later:
                lines.append("오늘 계획된 다음 작업: " + " · ".join(
                    f"{item.start:%H:%M} {_safe(item.activity)}" for item in later[:3]
                ))
            lines.append("현장 예보: " + (_safe(weather_summary) if weather_summary else "연결된 예보가 없습니다. 기상청 특보와 현장 기상을 확인하세요."))
            lines.extend(f"예보 관련 확인: {_safe(note)}" for note in weather_notes)
            lines.append(_season_guidance(day))
        else:
            task_names = " · ".join(_safe(item.activity) for item in morning[:4])
            lines.append("**작업자에게 읽어줄 브리핑**")
            lines.append(
                f"오늘 {day.month}월 {day.day}일 {_safe(plan.site)} 현장 오전 작업은 {task_names}입니다. "
                "작업별 계획된 안전조치와 시작 전 확인사항을 함께 읽고, 계획서에 비어 있는 항목은 현장 책임자와 확인한 뒤 작업을 시작해 주세요."
            )
            lines.append("**오전 예정 작업**")
            for item in morning[:8]:
                equipment = f" · 장비 {_safe(item.equipment)}" if not is_plan_field_missing(item.equipment) else ""
                lines.append(f"- {item.start:%H:%M}–{item.end:%H:%M} · {_safe(item.area)} · {_safe(item.activity)}{equipment}")
                if not is_plan_field_missing(item.planned_controls):
                    lines.append(f"  계획 안전조치: {_safe(item.planned_controls)}")
                if not is_plan_field_missing(item.follow_up):
                    lines.append(f"  시작 전 확인: {_safe(item.follow_up)}")
                missing = missing_work_fields(item)
                if missing:
                    lines.append(f"  계획서 미기재: {_safe(', '.join(missing))} · 작업허가서/위험성평가와 현장 상태 확인")
            if len(morning) > 8:
                lines.append(f"- 그 밖의 오전 작업 {len(morning) - 8}건은 오늘의 작업 화면에서 확인하세요.")

            lines.append("**현장 날씨 · 시간대별 확인**")
            lines.append(_safe(weather_summary) if weather_summary else "현장 위치 예보를 불러오지 못했습니다. 작업 전 기상청 특보와 현장 기상을 확인하세요.")
            if weather_windows:
                for window in weather_windows:
                    checks = " · 작업 확인: " + " / ".join(window.checks) if window.checks else ""
                    lines.append(f"- {window.time_label} { _safe(window.activity)} · {_safe(window.detail)}{_safe(checks)}")
            elif weather_notes:
                lines.extend(f"- 작업 확인: {_safe(note)}" for note in weather_notes)
            else:
                lines.append("- 예보상 별도 기상 주의 신호가 확인되지 않아도 작업 전 현장 풍속·강수·바닥 상태를 확인하세요.")

            lines.append(_season_guidance(day))

            case_rows = []
            case_report = []
            for item in morning[:8]:
                try:
                    summary = summarize_cases(item)
                except (OSError, ValueError, ImportError):
                    summary = None
                if summary is None:
                    continue
                types = " · ".join(f"{_safe(name)} {count:,}건" for name, count in summary.counts[:3])
                case_rows.append(
                    f"- {_safe(item.activity)} · 공개 SIF에서 ‘{_safe(summary.keyword)}’ 키워드 {summary.total:,}건"
                    + (f" · 사고유형 상위 {types}" if types else "")
                )
                guide = summary.guides[0] if summary.guides else None
                case_report.append({
                    "activity": item.activity,
                    "keyword": summary.keyword,
                    "total": summary.total,
                    "counts": [{"name": name, "count": count} for name, count in summary.counts[:3]],
                    "controls": list(guide.controls[:1]) if guide else [],
                })
                for guide in summary.guides[:1]:
                    case_rows.append(f"  { _safe(guide.accident_type)} 사례 상황: {_safe(guide.situation)}")
                    if guide.controls:
                        case_rows.append(f"  교육 확인: {_safe(' / '.join(guide.controls[:2]))}")
            lines.append("**작업별 유사 사고 기록**")
            if case_rows:
                lines.extend(case_rows)
                lines.append("공개 SIF 자료의 작업 키워드 검색 건수로, 이 현장의 발생 건수나 사고 확률을 뜻하지 않습니다.")
            else:
                lines.append("연결 가능한 작업 키워드 통계가 없습니다. 통계 0건은 안전하다는 뜻이 아니므로 작업별 위험성평가와 현장 사고기록을 확인하세요.")
        lines.append("출처: 적용한 작업계획서, 연결된 Open-Meteo 시간대별 예보, SANUP-P 공개 SIF 사례. 기상 특보·작업허가·현장 측정값을 작업 전에 최종 확인하세요.")
        season, season_note = _season_data(day)
        morning_pairs = tuple(
            (left, right, reasons)
            for left, right, reasons in coordination_candidates(plan.items, day)
            if left.start.hour < 12 and right.start.hour < 12
        )
        if morning_pairs:
            left, right, _ = morning_pairs[0]
            summary_line = (
                f"{left.start:%H:%M}–{right.end:%H:%M} {left.area}에서 {left.activity}와 {right.activity} 일정이 겹칩니다. "
                "작업 구역과 하부 출입 동선을 먼저 조정해 주세요."
            )
        elif morning:
            first = morning[0]
            summary_line = (
                f"오전 작업 {len(morning)}건: "
                + " · ".join(item.activity for item in morning[:3])
                + ". 작업별 계획 조치와 시작 전 확인을 진행하세요."
            )
        else:
            summary_line = "오전 계획 작업이 없습니다. 일정 변경 여부를 확인하세요."
        weather_label = "미연결"
        if weather_summary and not weather_summary.startswith("예보 미연결"):
            weather_parts = weather_summary.split(" · ")
            weather_label = weather_parts[1] if len(weather_parts) > 1 else "연결됨"
        report = {
            "date": f"{day.year}.{day.month:02d}.{day.day:02d}",
            "weekday": weekday,
            "site": plan.site,
            "location": location,
            "preview": day != briefing_requested_day,
            "summary": summary_line,
            "weather": weather_summary,
            "weather_label": weather_label,
            "weather_windows": [
                {
                    "time": window.time_label,
                    "activity": window.activity,
                    "detail": window.detail,
                    "checks": list(window.checks),
                }
                for window in weather_windows
            ],
            "weather_notes": list(weather_notes),
            "season": season,
            "season_note": season_note,
            "tasks": [
                {
                    "time": f"{item.start:%H:%M}–{item.end:%H:%M}",
                    "area": item.area,
                    "activity": item.activity,
                    "equipment": "" if is_plan_field_missing(item.equipment) else item.equipment,
                    "check": "" if is_plan_field_missing(item.follow_up) else item.follow_up,
                    "controls": "" if is_plan_field_missing(item.planned_controls) else item.planned_controls,
                }
                for item in morning[:8]
            ],
            "cases": case_report,
        }
        return _field_response("\n".join(lines), command, day, briefing=report)
    if command in {"오늘주의사항", "선택일주의사항"}:
        pending = [item for item in items if reviews.get(item.work_id, {}).get("status") != "확인 완료"]
        pairs = coordination_candidates(plan.items, day)
        lines = [f"**{day:%Y.%m.%d} 작업 전 확인 · {len(items)}건**"]
        lines.append(f"- 현장 확인 대기 **{len(pending)}건** · 동시간 조정 후보 **{len(pairs)}쌍** · 연결된 미완료 조치 **{len(open_actions)}건**")
        for item in pending[:4]:
            details = []
            if not is_plan_field_missing(item.follow_up):
                details.append(f"시작 전 확인: {item.follow_up}")
            missing_fields = missing_work_fields(item)
            if missing_fields:
                details.append("계획서 미기재: " + ", ".join(missing_fields))
                if "계획 안전조치" in missing_fields:
                    details.append("작업허가서/위험성평가에서 안전조치 확인")
            lines.append(f"- {_safe(item.activity)}: {_safe(' / '.join(details) if details else '현장 조건 확인 대기')}")
        if len(pending) > 4:
            lines.append(f"- 그 밖의 확인 대기 작업 {len(pending) - 4}건은 오늘의 작업 화면에서 확인하세요.")
        for left, right, reasons in pairs[:3]:
            lines.append(
                f"- 조정 후보 {max(left.start, right.start):%H:%M}: "
                f"{_safe(left.activity)} ↔ {_safe(right.activity)} · {_safe(' / '.join(reasons))}"
            )
        if len(pairs) > 3:
            lines.append(f"- 추가 조정 후보 {len(pairs) - 3}쌍은 오늘의 작업 화면에서 확인하세요.")
        if pairs:
            lines.append("계획서 표기 기준의 조정 후보이며 위험도나 장비 공유 판정은 아닙니다.")
        lines.append(f"- 현장 예보: {_safe(weather_summary) if weather_summary else '예보 확인 불가 · 오늘의 작업에서 현장 위치를 연결하거나 기상청 특보를 직접 확인'}")
        lines.extend(f"- 예보 관련 확인: {_safe(note)}" for note in weather_notes)
        lines.append("출처: 현재 적용한 작업계획·현장 확인·조치 기록 및 연결한 모델 예보. 작업 허가나 중지 판단은 현장 기준에 따르세요.")
    elif command in {"선택일작업요약", "오늘작업요약"}:
        lines = [f"**{_safe(plan.site)} · {day:%Y.%m.%d} 작업 {len(items)}건**"]
        lines.extend(f"- {item.start:%H:%M}–{item.end:%H:%M} · {_safe(item.area)} · {_safe(item.activity)}" for item in items)
        pairs = coordination_candidates(plan.items, day)
        lines.append(f"같은 구역·시간 중복 후보 **{len(pairs)}쌍**, 미완료 조치 **{len(open_actions)}건**입니다.")
        for left, right, reasons in pairs[:3]:
            lines.append(
                f"- {max(left.start, right.start):%H:%M} · {_safe(left.activity)} ↔ "
                f"{_safe(right.activity)} · {_safe(' / '.join(reasons))}"
            )
        if len(pairs) > 3:
            lines.append(f"- 나머지 조정 후보 {len(pairs) - 3}쌍은 작업 화면에서 확인하세요.")
        lines.append("출처: 현재 적용한 작업계획서와 조치 기록. 작업 전 현장 상태를 확인하세요.")
    elif command == "남은조치":
        lines = [f"**{day:%Y.%m.%d} 연결 조치 · 미완료 {len(open_actions)}건**"]
        if open_actions:
            lines.extend(
                f"- {_safe(action.description)} · {_safe(action.assignee)} · 기한 {action_due_kst(action):%m.%d %H:%M}"
                + (f" · {_safe(' · '.join(action_attention_flags(action, at)))}" if action_attention_flags(action, at) else "")
                for action in open_actions
            )
        else:
            lines.append("등록된 미완료 조치가 없습니다.")
        lines.append("출처: 현재 적용한 조치 현황. 완료 판단은 담당자가 기록합니다.")
    else:
        pending = [item for item in items if reviews.get(item.work_id, {}).get("status") != "확인 완료"]
        changed = [action for action in related if action.needs_review]
        history = tbm_records.get(day.isoformat(), ())
        deliveries = tbm_deliveries.get(day.isoformat(), ())
        lines = [f"**{day:%Y.%m.%d} TBM 준비 상태**"]
        lines.append(f"- 현장 확인 필요: **{len(pending)}건**")
        lines.append(f"- 계획 변경 조치 재확인: **{len(changed)}건**")
        lines.append(f"- 관리자 확인 기록: **{len(history)}건**, 진행 기록: **{len(deliveries)}건**")
        lines.append("계획·조치·예보가 바뀌었는지 TBM 브리핑 화면에서 최종 확인하세요.")
    return _field_response(
        "\n".join(lines), command, day,
        open_actions[0] if command == "남은조치" and open_actions else None,
    )
