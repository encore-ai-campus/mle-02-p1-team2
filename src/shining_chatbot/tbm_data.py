"""Deterministic TBM briefing snapshots built from reviewed work and actions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256
from html import escape

from shining_chatbot.action_data import FieldAction, action_attention_flags, action_due_kst
from shining_chatbot.business_time import now_korea
from shining_chatbot.work_plan import (
    WorkItem,
    WorkPlan,
    coordination_candidates,
    missing_work_fields,
)


@dataclass(frozen=True)
class TbmRecord:
    day: date
    fingerprint: str
    confirmed_by: str
    audience: str
    confirmed_at: datetime
    note: str
    weather_summary: str = ""


@dataclass(frozen=True)
class TbmDelivery:
    day: date
    fingerprint: str
    confirmation_at: datetime
    delivered_by: str
    attendee_count: int
    delivered_at: datetime
    note: str


def record_delivery(record: TbmRecord, delivered_by: str, attendee_count: int, note: str) -> TbmDelivery:
    if not isinstance(delivered_by, str) or not delivered_by.strip():
        raise ValueError("TBM 진행자와 참석 인원을 확인하세요.")
    if len(delivered_by.strip()) > 100:
        raise ValueError("TBM 진행자는 100자 이내로 입력하세요.")
    if isinstance(attendee_count, bool) or not isinstance(attendee_count, int) or not 1 <= attendee_count <= 10000:
        raise ValueError("실제 참석 인원은 1명 이상 10,000명 이하의 정수로 입력하세요.")
    if not isinstance(note, str):
        raise ValueError("질문·변경 사항을 확인하세요.")
    if len(note.strip()) > 2000:
        raise ValueError("질문·변경 사항은 2,000자 이내로 입력하세요.")
    return TbmDelivery(
        record.day, record.fingerprint, record.confirmed_at,
        delivered_by.strip(), attendee_count, now_korea(), note.strip(),
    )


def daily_items(plan: WorkPlan, day: date) -> tuple[WorkItem, ...]:
    return tuple(item for item in plan.items if item.day == day)


def daily_actions(plan: WorkPlan, day: date, actions: tuple[FieldAction, ...]) -> tuple[FieldAction, ...]:
    ids = {item.work_id for item in daily_items(plan, day)}
    all_ids = {item.work_id for item in plan.items}
    return tuple(
        action for action in actions
        if action.work_id in ids or (
            action.needs_review and action.work_id not in all_ids
            and (action.work_day == day or action.work_day is None)
        )
    )


def handover_actions(plan: WorkPlan, day: date, actions: tuple[FieldAction, ...]) -> tuple[FieldAction, ...]:
    """Open actions carried forward from earlier plan days, without guessing risk."""
    work_days = {item.work_id: item.day for item in plan.items}
    carried = []
    for action in actions:
        if action.status != "open":
            continue
        origin_day = action.work_day or work_days.get(action.work_id) or action_due_kst(action).date()
        if origin_day < day:
            carried.append(action)
    return tuple(sorted(carried, key=lambda action: (action_due_kst(action), action.action_id)))


def _case_briefings(items: tuple[WorkItem, ...]) -> tuple[tuple[WorkItem, object], ...]:
    """Return local SIF summaries without letting an optional archive block TBM."""
    try:
        from shining_chatbot.case_summary import summarize_cases
        summaries = []
        for item in items[:12]:
            summary = summarize_cases(item)
            if summary is not None:
                summaries.append((item, summary))
        return tuple(summaries)
    except (OSError, ValueError, ImportError):
        return ()


def _briefing_lines(items: tuple[WorkItem, ...]) -> tuple[str, ...]:
    matches = _case_briefings(items)
    if not matches:
        return ("- 연결 가능한 작업 키워드 사례가 없거나 로컬 SIF 자료를 읽지 못했습니다. 사례 0건은 안전함을 뜻하지 않습니다.",)
    lines = []
    for item, summary in matches:
        types = " · ".join(f"{name} {count}건" for name, count in summary.counts[:3])
        categories = " · ".join(f"{name} {count}건" for name, count in summary.category_counts[:3])
        lines.append(
            f"- {item.start:%H:%M} {item.activity} · 검색어 ‘{summary.keyword}’ {summary.total}건 · {types}"
        )
        if categories:
            lines.append(f"  원문 작업 분류 상위: {categories}")
        for guide in summary.guides[:2]:
            lines.append(f"  {guide.accident_type} 사례 상황: {guide.situation}")
            if guide.controls:
                lines.extend(f"  교육 때 확인: {control}" for control in guide.controls[:2])
            else:
                lines.append("  사례 원문에 이용 가능한 예방대책이 없습니다. 작업허가서·위험성평가를 확인하세요.")
            if guide.record_ids:
                lines.append(f"  사례 ID: {', '.join(guide.record_ids)}")
    if len(items) > 12:
        lines.append(f"- 나머지 {len(items) - 12}개 작업의 키워드 통계는 오늘의 작업 화면에서 확인하세요.")
    lines.append("과거 공개 SIF 키워드 검색 건수이며 현장 발생 건수·사고 확률이 아닙니다. 작업계획과 현장 기준을 관리자와 함께 확인하세요.")
    return tuple(lines)


def worker_briefing_summary(
    plan: WorkPlan, day: date, actions: tuple[FieldAction, ...],
    reviews: dict, weather_summary: str = "",
) -> tuple[str, ...]:
    """Build five short, source-bound messages for the start-of-shift share."""
    items = tuple(sorted(daily_items(plan, day), key=lambda item: (item.start, item.work_id)))
    pending = [
        item for item in items
        if reviews.get(item.work_id, {}).get("status") != "확인 완료"
    ]
    pending_work = " · ".join(
        f"{item.start:%H:%M} {item.activity}" for item in pending[:2]
    )
    if len(pending) > 2:
        pending_work += f" 외 {len(pending) - 2}건"
    if not items:
        check_line = "계획에 등록된 작업 없음 · 실제 현장 일정과 대조"
    elif pending:
        check_line = f"현장 확인 대기 {len(pending)}건 · {pending_work}"
    else:
        check_line = "계획에 등록된 작업의 현장 확인 기록 대기 없음"
    lines = [
        f"작업일 {day:%Y.%m.%d} · 예정 작업 {len(items)}건 · {check_line}",
    ]

    weather = " ".join(weather_summary.split())
    if weather:
        lines.append(f"현장 예보 확인 · {weather[:150]}{'…' if len(weather) > 150 else ''}")
    else:
        lines.append("현장 예보 미연결 · 작업 전 현장 기상과 기상청 특보 확인")

    overlaps = coordination_candidates(tuple(plan.items), day)
    if overlaps:
        pairs = " · ".join(
            f"{left.start:%H:%M} {left.activity} / {right.activity}"
            for left, right, _ in overlaps[:2]
        )
        if len(overlaps) > 2:
            pairs += f" 외 {len(overlaps) - 2}쌍"
        lines.append(f"계획 표기 조정 후보 {len(overlaps)}쌍 · 실제 동선·장비 사용을 현장에서 확인 · {pairs}")
    else:
        lines.append("계획 표기 기준 같은 시간대 조정 후보 없음 · 현장 동선은 별도 확인")

    open_actions = sorted(
        (action for action in daily_actions(plan, day, actions) if action.status == "open"),
        key=action_due_kst,
    )
    if open_actions:
        action_text = " · ".join(
            f"{action.description} ({action.assignee}, {action_due_kst(action):%m.%d %H:%M})"
            for action in open_actions[:2]
        )
        if len(open_actions) > 2:
            action_text += f" 외 {len(open_actions) - 2}건"
        lines.append(f"미완료 조치 {len(open_actions)}건 · {action_text}")
    else:
        lines.append("계획에 등록된 미완료 조치 없음")

    case_matches = _case_briefings(items)
    if case_matches:
        item, summary = case_matches[0]
        if summary.counts:
            top_type, count = summary.counts[0]
            lines.append(
                f"과거 공개 SIF 키워드 참고 · {item.start:%H:%M} ‘{summary.keyword}’ 검색 "
                f"{summary.total}건, 최다 {top_type} {count}건 · 현장 위험도나 사고 확률 아님"
            )
        else:
            lines.append("과거 SIF 키워드 통계 없음 · 작업허가서와 현장 위험성평가 확인")
    else:
        try:
            from shining_chatbot.case_summary import local_cases_available
            case_source = "연결 검색 결과 없음" if local_cases_available() else "자료 미연결"
        except (OSError, ImportError):
            case_source = "자료 확인 불가"
        lines.append(f"과거 SIF 사례 {case_source} · 건수 없음은 안전하다는 뜻이 아님")
    return tuple(lines[:5])


def brief_fingerprint(
    plan: WorkPlan, day: date, actions: tuple[FieldAction, ...], reviews: dict,
    weather_summary: str = "", revision_token: str = "",
) -> str:
    items = daily_items(plan, day)
    ids = {item.work_id for item in items}
    payload = {
        "site": plan.site,
        "day": day,
        "items": [asdict(item) for item in items],
        "actions": [asdict(action) for action in daily_actions(plan, day, actions)],
        "handover_actions": [asdict(action) for action in handover_actions(plan, day, actions)],
        "reviews": {work_id: reviews.get(work_id, {}) for work_id in sorted(ids)},
        "weather": weather_summary,
        "case_briefings": [(item.work_id, asdict(summary)) for item, summary in _case_briefings(items)],
        "revision": revision_token,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=lambda value: value.isoformat()).encode("utf-8")
    return sha256(encoded).hexdigest()


def confirm_brief(
    plan: WorkPlan, day: date, actions: tuple[FieldAction, ...], reviews: dict,
    confirmed_by: str, audience: str, note: str, weather_summary: str = "",
    revision_token: str = "",
) -> TbmRecord:
    if not daily_items(plan, day):
        raise ValueError("선택한 날짜에 등록된 작업이 없습니다.")
    if not isinstance(confirmed_by, str) or not confirmed_by.strip() or not isinstance(audience, str) or not audience.strip():
        raise ValueError("진행자와 공유 대상을 입력하세요.")
    if len(confirmed_by.strip()) > 100 or len(audience.strip()) > 200:
        raise ValueError("진행자는 100자, 공유 대상은 200자 이내로 입력하세요.")
    if not isinstance(note, str) or len(note.strip()) > 2000:
        raise ValueError("전달 사항은 2,000자 이내로 입력하세요.")
    if not isinstance(weather_summary, str) or len(weather_summary) > 1000:
        raise ValueError("예보 요약이 입력 한도를 넘었습니다.")
    if not isinstance(revision_token, str) or len(revision_token) > 40:
        raise ValueError("계획 변경 식별자를 확인하세요.")
    pending = [item for item in daily_items(plan, day) if reviews.get(item.work_id, {}).get("status") != "확인 완료"]
    if pending:
        raise ValueError(f"현장 확인이 끝나지 않은 작업 {len(pending)}건을 먼저 확인하세요.")
    if any(action.needs_review for action in daily_actions(plan, day, actions)):
        raise ValueError("계획 변경으로 재확인이 필요한 조치를 먼저 확인하세요.")
    return TbmRecord(
        day, brief_fingerprint(plan, day, actions, reviews, weather_summary, revision_token),
        confirmed_by.strip(), audience.strip(), now_korea(), note.strip(), weather_summary,
    )


def briefing_text(
    plan: WorkPlan, day: date, actions: tuple[FieldAction, ...],
    record: TbmRecord | None, reviews: dict, weather_summary: str = "",
    delivery: TbmDelivery | None = None,
) -> str:
    """Plain text that a manager can paste into the team's existing channel."""
    items = daily_items(plan, day)
    candidates = coordination_candidates(tuple(plan.items), day)
    carried = handover_actions(plan, day, actions)
    shown_weather = (record.weather_summary if record else weather_summary) or "미연결 · 현장 기상과 기상청 특보 확인"
    lines = [
        f"[{'TBM 확인본' if record else 'TBM 초안 · 현장 확인 전'}] {plan.site}",
        f"작업일 {day:%Y.%m.%d} · 예정 작업 {len(items)}건",
        "",
        "■ 작업자에게 먼저 공유할 핵심 안내",
        *(f"- {line}" for line in worker_briefing_summary(plan, day, actions, reviews, (record.weather_summary if record else weather_summary))),
        f"현장 예보: {shown_weather}",
        f"이전 작업일 이월 조치: {len(carried)}건",
        "",
        "■ 이전 작업일에서 이어받은 미완료 조치",
    ]
    if carried:
        for action in carried:
            lines.append(f"- {action.description} · {action.assignee} · 기한 {action_due_kst(action):%m.%d %H:%M}")
    else:
        lines.append("- 계획에 기록된 이월 미완료 조치 없음")
    lines.extend((
        "",
        "■ 오늘의 작업",
    ))
    for item in items:
        missing_fields = missing_work_fields(item)
        controls = (
            "미기재 · 작업허가서/위험성평가 확인"
            if "계획 안전조치" in missing_fields else item.planned_controls
        )
        start_checks = (
            "미기재 · 작업 전 현장 확인 항목 지정"
            if "시작 전 확인" in missing_fields else item.follow_up
        )
        lines.append(f"{item.start:%H:%M}–{item.end:%H:%M} · {item.area} · {item.activity}")
        lines.append(f"  계획 조치: {controls}")
        lines.append(f"  시작 전 확인: {start_checks}")
        if missing_fields:
            lines.append(f"  계획서 입력 확인: {' / '.join(missing_fields)}")
        review = reviews.get(item.work_id, {})
        if review.get("status") == "확인 완료" and review.get("note"):
            lines.append(f"  현장 확인: {review['note']}")
    lines.extend(("", "■ 작업별 과거 사고 기록과 안전교육 확인", *_briefing_lines(items)))
    lines.extend(("", f"■ 작업 간 조정 후보 {len(candidates)}쌍"))
    lines.extend(
        f"- {a.activity} / {b.activity} · {max(a.start, b.start):%H:%M}–{min(a.end, b.end):%H:%M} · "
        f"{', '.join(reasons)} · 실제 조정 필요 여부 확인"
        for a, b, reasons in candidates
    )
    if not candidates:
        lines.append("- 계획 표기 기준 같은 시간대 조정 후보 없음")
    at = now_korea()
    open_actions = sorted(
        (action for action in daily_actions(plan, day, actions) if action.status == "open"),
        key=action_due_kst,
    )
    lines.extend(("", f"■ 미완료 조치 {len(open_actions)}건"))
    for action in open_actions:
        flags = action_attention_flags(action, at)
        prefix = " · ".join(flags) + " · " if flags else ""
        lines.append(f"- {prefix}{action.description} · {action.assignee} · {action_due_kst(action):%m.%d %H:%M}")
    if record:
        lines.extend(("", f"관리자 확인: {record.confirmed_by} · {record.confirmed_at:%Y.%m.%d %H:%M}", f"공유 대상: {record.audience}"))
        if record.note:
            lines.append(f"전달 사항: {record.note}")
    if record and delivery and delivery.fingerprint == record.fingerprint and delivery.confirmation_at == record.confirmed_at:
        lines.append(f"TBM 진행: {delivery.delivered_by} · 참석 {delivery.attendee_count}명 · {delivery.delivered_at:%Y.%m.%d %H:%M}")
        if delivery.note:
            lines.append(f"질문·변경: {delivery.note}")
    lines.extend(("", "계획서와 모델 예보를 정리한 자료입니다. 작업 조건과 조치는 현장에서 확인하세요."))
    return "\n".join(lines)


def briefing_html(
    plan: WorkPlan, day: date, actions: tuple[FieldAction, ...],
    record: TbmRecord | None, reviews: dict, weather_summary: str = "",
    delivery: TbmDelivery | None = None,
) -> bytes:
    items = daily_items(plan, day)
    related_actions = sorted(
        (action for action in daily_actions(plan, day, actions) if action.status == "open"),
        key=action_due_kst,
    )
    candidates = coordination_candidates(tuple(plan.items), day)
    carried = handover_actions(plan, day, actions)
    def render_work(item: WorkItem) -> str:
        missing_fields = missing_work_fields(item)
        controls = (
            "미기재 · 작업허가서/위험성평가 확인"
            if "계획 안전조치" in missing_fields else item.planned_controls
        )
        start_checks = (
            "미기재 · 작업 전 현장 확인 항목 지정"
            if "시작 전 확인" in missing_fields else item.follow_up
        )
        missing_row = (
            f'<p class="missing"><b>계획서 입력 확인</b> {escape(" / ".join(missing_fields))}</p>'
            if missing_fields else ""
        )
        review_row = (
            f'<p><b>현장 확인</b> {escape(reviews[item.work_id]["note"])}</p>'
            if reviews.get(item.work_id, {}).get("note") else ""
        )
        return (
            '<section class="work"><div class="time">'
            f'{item.start:%H:%M}<span>– {item.end:%H:%M}</span></div>'
            f'<div><h2>{escape(item.activity)}</h2><p class="meta">{escape(item.area)} · '
            f'{escape(item.location or "세부 위치 미입력")} · {escape(item.contractor or "업체 미입력")}</p>'
            f'<p><b>계획된 조치</b> {escape(controls)}</p>'
            f'<p><b>시작 전 확인</b> {escape(start_checks)}</p>'
            f'{missing_row}{review_row}</div></section>'
        )

    work_rows = "".join(render_work(item) for item in items)
    case_cards = []
    case_matches = _case_briefings(items)
    for item, summary in case_matches:
        types = " · ".join(f"{name} {count}건" for name, count in summary.counts[:3])
        categories = " · ".join(f"{name} {count}건" for name, count in summary.category_counts[:3])
        guide_rows = []
        for guide in summary.guides[:2]:
            controls = "".join(f"<li>{escape(control)}</li>" for control in guide.controls[:2])
            if not controls:
                controls = "<li>사례 원문에 이용 가능한 예방대책이 없습니다. 작업허가서·위험성평가를 확인하세요.</li>"
            guide_rows.append(
                '<div class="case-type"><b>'
                f'{escape(guide.accident_type)} · {guide.count:,}건</b>'
                f'<p>{escape(guide.situation)}</p><ul>{controls}</ul>'
                + (f'<small>사례 ID · {escape(" · ".join(guide.record_ids))}</small>' if guide.record_ids else '')
                + '</div>'
            )
        case_cards.append(
            '<article class="case-brief"><h4>'
            f'{item.start:%H:%M} · {escape(item.activity)}</h4>'
            f'<p>작업 키워드 “{escape(summary.keyword)}” 검색 결과 {summary.total:,}건 · {escape(types)}</p>'
            + (f'<p class="case-scope">원문 작업 분류 상위 · {escape(categories)}</p>' if categories else '')
            + "".join(guide_rows) + '</article>'
        )
    if not case_cards:
        case_cards.append('<p class="case-empty">연결 가능한 작업 키워드 사례가 없거나 로컬 SIF 자료를 읽지 못했습니다. 사례 0건은 안전함을 뜻하지 않습니다.</p>')
    if len(items) > 12:
        case_cards.append(f'<p class="case-empty">나머지 {len(items) - 12}개 작업의 키워드 통계는 오늘의 작업 화면에서 확인하세요.</p>')
    case_cards.append('<p class="case-limit">과거 공개 SIF 키워드 검색 건수이며 현장 발생 건수·사고 확률이 아닙니다. 작업계획과 현장 기준을 관리자와 함께 확인하세요.</p>')
    coordination_rows = "".join(
        f'<li>{escape(a.activity)} / {escape(b.activity)} · {max(a.start, b.start):%H:%M}–{min(a.end, b.end):%H:%M}'
        f'<br>{escape(" · ".join(reasons))} · 현장에서 실제 조정 필요 여부 확인</li>'
        for a, b, reasons in candidates
    ) or '<li>계획 표기 기준 같은 시간대 조정 후보 없음</li>'
    handover_rows = "".join(
        f'<li>{escape(action.description)} <span>{escape(action.assignee)} · 기한 {action_due_kst(action):%m.%d %H:%M}</span></li>'
        for action in carried
    ) or '<li>계획에 기록된 이월 미완료 조치 없음</li>'
    action_rows_list = []
    at = now_korea()
    for action in related_actions:
        due_at = action_due_kst(action)
        flags = action_attention_flags(action, at)
        flag_html = (
            f'<strong class="action-flags">{escape(" · ".join(flags))} · </strong>'
            if flags else ""
        )
        action_rows_list.append(
            f'<li>{flag_html}{escape(action.description)} '
            f'<span>{escape(action.assignee)} · {due_at:%m.%d %H:%M}</span></li>'
        )
    action_rows = "".join(action_rows_list) or '<li>등록된 미완료 조치 없음</li>'
    state = "관리자 확인본" if record else "확인 전 초안"
    footer = (
        f'진행자 {escape(record.confirmed_by)} · 공유 대상 {escape(record.audience)} · '
        f'확인 시각 {record.confirmed_at:%Y.%m.%d %H:%M}'
        + (f'<div class="manager-note">관리자 전달 사항 · {escape(record.note)}</div>' if record.note else '')
        if record else "현장 관리자가 작업 내용과 실제 조치를 확인한 뒤 공유하세요."
    )
    if record and delivery and delivery.fingerprint == record.fingerprint and delivery.confirmation_at == record.confirmed_at:
        footer += (
            f'<div class="manager-note">TBM 진행 · {escape(delivery.delivered_by)} · '
            f'참석 {delivery.attendee_count}명 · {delivery.delivered_at:%Y.%m.%d %H:%M}'
            + (f'<br>질문·변경 기록 · {escape(delivery.note)}' if delivery.note else '')
            + '</div>'
        )
    shown_weather = record.weather_summary if record else weather_summary
    weather_row = (
        f'<h3>현장 예보</h3><div class="weather">{escape(shown_weather)}<small>모델 예보 · Open-Meteo. 현장 측정과 기상청 특보를 별도로 확인 · '
        '<a href="https://www.kosha.or.kr/safety1team/tr/reference.do?articleNo=456837&attachNo=263892&mode=download">안전보건공단 폭염 예방수칙</a> · '
        '<a href="https://www.moel.go.kr/news/cardinfo/view.do?bbs_seq=20251200063">고용노동부 한파 안전 안내</a></small></div>'
        if shown_weather else '<h3>현장 예보</h3><div class="weather">예보 미연결 · 현장 기상과 기상청 특보를 별도로 확인</div>'
    )
    summary_rows = "".join(
        f"<li>{escape(line)}</li>"
        for line in worker_briefing_summary(plan, day, actions, reviews, (record.weather_summary if record else weather_summary))
    )
    summary_html = (
        '<section class="share-summary" aria-labelledby="share-title">'
        '<div class="share-head"><h2 id="share-title">작업자에게 먼저 공유할 내용</h2>'
        '<span>현장 확인 후 전달</span></div>'
        f'<ol>{summary_rows}</ol>'
        '<p>공개 사례 숫자는 키워드 검색 건수이며 현장 사고율·위험 점수·예측값이 아닙니다.</p>'
        '</section>'
    )
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>TBM 브리핑 · {escape(plan.site)}</title>
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
*{{box-sizing:border-box}}body{{margin:0;background:#E7ECE7;color:#253129;font-family:'Pretendard Variable','Malgun Gothic',sans-serif;font-size:13px;line-height:1.65}}
main{{width:min(840px,calc(100% - 32px));margin:32px auto;background:#fff;border:1px solid #D9E2D9;border-radius:12px;padding:36px 42px;box-shadow:0 16px 42px #273E2C16}}
.top{{display:flex;justify-content:space-between;gap:18px;border-bottom:1px solid #E4EAE3;padding-bottom:20px;margin-bottom:24px}}
.kicker{{font-size:10px;letter-spacing:.12em;color:#4F7357;font-weight:650}}h1{{font-size:30px;letter-spacing:-.04em;line-height:1.2;margin:8px 0}}.site{{color:#5D6F61;margin:0}}
.badge{{border:1px solid #C9D9CB;border-radius:6px;padding:5px 9px;color:#46674F;font-size:11px;height:max-content;white-space:nowrap}}
.summary{{display:flex;gap:20px;flex-wrap:wrap;padding:14px 17px;background:#F5F8F4;border-radius:7px;margin-bottom:28px;color:#48604D}}
h2{{font-size:15px;letter-spacing:-.02em;margin:0 0 3px}}h3{{font-size:13px;margin:27px 0 10px}}
.share-summary{{padding:17px 19px;background:#F8FAF7;border:1px solid #DDE7DC;border-radius:9px;margin:18px 0 20px}}.share-head{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:8px}}.share-head h2{{margin:0;color:#2F4935}}.share-head span{{font-size:10px;color:#68756A}}.share-summary ol{{margin:0;padding-left:20px;color:#4A5B4D;font-size:11px;line-height:1.75}}.share-summary li{{border:0;padding:3px 0 3px 2px}}.share-summary li::marker{{color:#628268;font-weight:650}}.share-summary>p{{font-size:10px;color:#68756A;line-height:1.55;margin:9px 0 0}}.work{{display:grid;grid-template-columns:80px 1fr;gap:18px;border-top:1px solid #E8EEE8;padding:17px 0}}.time{{color:#4F7257;font-weight:650}}.time span{{display:block;font-weight:400;color:#626D64}}
.work p{{margin:5px 0;color:#536057;overflow-wrap:anywhere}}.work p.meta{{font-size:11px;color:#626D64;margin-bottom:10px}}.work p.missing{{color:#806642;background:#F8F3EA;border-radius:4px;padding:6px 8px}}b{{color:#354B3A;font-weight:600}}
ul{{margin:0;padding:0;list-style:none}}li{{border-top:1px solid #E8EEE8;padding:9px 0}}li span{{float:right;color:#586B5C;font-size:11px}}
.action-flags{{color:#8A673E;font-size:10px;font-weight:600}}
footer{{border-top:1px solid #DFE7DF;margin-top:30px;padding-top:14px;color:#626D64;font-size:11px}}.note{{margin-top:7px;color:#626D64}}
.manager-note{{margin-top:8px;color:#354B3A;font-size:13px;white-space:pre-wrap}}
.weather{{padding:12px 15px;border-radius:6px;background:#F5F8F4;color:#3F5945;font-size:12px;white-space:pre-line}}
.weather a{{color:#456A4E;text-decoration:underline;text-underline-offset:2px}}
.weather small{{display:block;color:#626D64;font-size:10px;margin-top:4px}}
.case-brief{{border:1px solid #E2E9E1;border-radius:7px;background:#FAFBF9;padding:12px 14px;margin:8px 0}}
.case-brief h4{{font-size:12px;line-height:1.45;margin:0 0 4px;color:#354B3A}}
.case-brief>p,.case-type p{{font-size:10px;line-height:1.6;color:#626D64;margin:0 0 6px}}
.case-brief>p.case-scope{{color:#536A59;font-size:10px}}
.case-type{{border-top:1px solid #E7ECE6;padding-top:7px;margin-top:7px}}
.case-type>b{{font-size:10px;color:#48634E}}
.case-type ul{{list-style:disc;padding-left:16px;color:#536057;font-size:10px;line-height:1.55}}
.case-type li{{border:0;padding:2px 0}}
.case-type small,.case-empty,.case-limit{{font-size:9px;line-height:1.55;color:#68756B}}
.case-type small{{display:block;margin-top:5px}}
.case-empty,.case-limit{{margin:5px 0}}
@media(max-width:600px){{main{{margin:0;width:100%;border:0;border-radius:0;padding:25px 20px}}.work{{grid-template-columns:60px 1fr;gap:10px}}li span{{float:none;display:block}}}}
@media print{{body{{background:#fff}}main{{width:100%;margin:0;border:0;border-radius:0;box-shadow:none;padding:18mm 15mm}}.work{{break-inside:avoid}}}}
</style></head><body><main><header class="top"><div><div class="kicker">SAFETY ATLAS / TOOLBOX MEETING</div><h1>작업 전 TBM 브리핑</h1><p class="site">{escape(plan.site)} · {day:%Y.%m.%d}</p></div><span class="badge">{state}</span></header>
<div class="summary"><span>예정 작업 <b>{len(items)}건</b></span><span>작업 조정 후보 <b>{len(candidates)}쌍</b></span><span>이월 조치 <b>{len(carried)}건</b></span><span>당일 미완료 조치 <b>{len(related_actions)}건</b></span></div>
{summary_html}{weather_row}<h3>이전 작업일에서 이어받은 미완료 조치</h3><ul>{handover_rows}</ul><h3>오늘의 작업과 계획된 조치</h3>{work_rows}<h3>작업별 과거 사고 기록과 안전교육 확인</h3>{''.join(case_cards)}<h3>작업 간 조정 후보</h3><ul>{coordination_rows}</ul><h3>오늘의 미완료 조치</h3><ul>{action_rows}</ul>
<footer>{footer}<div class="note">계획서 내용을 정리한 자료입니다. 실제 작업 조건과 조치 내용을 현장에서 확인하세요.</div></footer></main></body></html>'''
    return html.encode("utf-8-sig")
