"""Portable session backup for the single-user field dashboard pilot."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, time

from shining_chatbot.action_data import FieldAction
from shining_chatbot.plan_revision import PlanRevision, RevisionEntry
from shining_chatbot.tbm_data import TbmDelivery, TbmRecord
from shining_chatbot.weather_data import WeatherLocation
from shining_chatbot.work_plan import NoWorkConfirmation, WorkItem, WorkPlan


BACKUP_VERSION = 7
MAX_BACKUP_BYTES = 10 * 1024 * 1024
REVIEW_STATUSES = {"확인 중", "조치 필요", "확인 완료"}


def export_backup(
    plan: WorkPlan, reviews: dict, plan_name: str, applied_at: str,
    actions: tuple[FieldAction, ...] = (),
    tbm_records: dict[str, tuple[TbmRecord, ...]] | None = None,
    weather_location: WeatherLocation | None = None,
    tbm_deliveries: dict[str, tuple[TbmDelivery, ...]] | None = None,
    revisions: tuple[PlanRevision, ...] = (),
) -> bytes:
    if len(plan.no_work_confirmations) > 1000:
        raise ValueError("계획표의 작업 없음 확인 기록이 1,000건을 넘었습니다.")
    work_ids = {item.work_id for item in plan.items}
    payload = {
        "version": BACKUP_VERSION,
        "site": plan.site,
        "site_location": plan.site_location,
        "plan_name": plan_name,
        "applied_at": applied_at,
        "items": [asdict(item) for item in plan.items],
        "issues": list(plan.issues),
        "no_work_confirmations": [asdict(record) for record in plan.no_work_confirmations],
        "reviews": {key: value for key, value in reviews.items() if key in work_ids},
        "actions": [asdict(action) for action in actions],
        "tbm_records": {
            day: [asdict(record) for record in records]
            for day, records in (tbm_records or {}).items()
        },
        "weather_location": asdict(weather_location) if weather_location else None,
        "tbm_deliveries": {
            day: [asdict(delivery) for delivery in history]
            for day, history in (tbm_deliveries or {}).items()
        },
        "revisions": [asdict(revision) for revision in revisions],
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=lambda value: value.isoformat()).encode("utf-8-sig")
    if len(encoded) > MAX_BACKUP_BYTES:
        raise ValueError("백업 데이터가 10MB를 넘었습니다. 오래된 변경 이력을 정리해야 합니다.")
    return encoded


def import_backup(content: bytes) -> tuple[WorkPlan, dict, tuple[FieldAction, ...], dict[str, tuple[TbmRecord, ...]], dict[str, tuple[TbmDelivery, ...]], tuple[PlanRevision, ...], WeatherLocation | None, str, str]:
    if len(content) > MAX_BACKUP_BYTES:
        raise ValueError("백업 파일은 10MB 이하여야 합니다.")
    try:
        payload = json.loads(content.decode("utf-8-sig"))
        version = payload.get("version") if isinstance(payload, dict) else None
        if type(version) is not int or version not in (1, 2, 3, 4, 5, 6, BACKUP_VERSION):
            raise ValueError("지원하지 않는 백업 버전입니다.")
        site = payload["site"]
        site_location = payload.get("site_location", "")
        raw_items = payload["items"]
        if (
            not isinstance(site, str) or not site.strip() or len(site) > 200
            or not isinstance(site_location, str) or len(site_location) > 200
            or not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 500
        ):
            raise ValueError("현장명 또는 작업 목록을 확인하세요.")
        items = []
        seen = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise ValueError("작업 형식을 확인하세요.")
            item = WorkItem(
                **{**raw, "day": date.fromisoformat(raw["day"]),
                   "start": time.fromisoformat(raw["start"]), "end": time.fromisoformat(raw["end"])}
            )
            text_fields = (
                "work_id", "area", "location", "trade", "activity", "equipment", "contractor",
                "owner", "planned_controls", "follow_up", "review_status", "change_note", "sheet",
            )
            if not all(isinstance(getattr(item, key), str) for key in text_fields):
                raise ValueError("작업 텍스트 형식을 확인하세요.")
            text_limits = {
                "work_id": 100, "area": 150, "location": 300, "trade": 120,
                "activity": 300, "equipment": 200, "contractor": 150, "owner": 100,
                "planned_controls": 2000, "follow_up": 2000,
                "review_status": 100, "change_note": 2000, "sheet": 100,
            }
            if any(len(getattr(item, key)) > maximum for key, maximum in text_limits.items()):
                raise ValueError("작업 텍스트 길이를 확인하세요.")
            if item.people is not None and (not isinstance(item.people, int) or isinstance(item.people, bool) or item.people < 0):
                raise ValueError("인원 형식을 확인하세요.")
            if not isinstance(item.row, int) or item.row < 0:
                raise ValueError("원문 행 번호를 확인하세요.")
            if not item.work_id or item.work_id in seen or not item.area or not item.activity or item.end <= item.start:
                raise ValueError("작업ID·날짜·시간·장소를 확인하세요.")
            seen.add(item.work_id)
            items.append(item)
        issues = payload.get("issues", [])
        if not isinstance(issues, list) or any(not isinstance(issue, str) for issue in issues):
            raise ValueError("검토 항목 형식을 확인하세요.")
        raw_reviews = payload.get("reviews", {})
        if not isinstance(raw_reviews, dict):
            raise ValueError("현장 확인 기록 형식을 확인하세요.")
        reviews = {}
        for work_id, review in raw_reviews.items():
            if work_id not in seen or not isinstance(review, dict):
                continue
            status, reviewer, note, at = (review.get(key) for key in ("status", "reviewer", "note", "at"))
            if (
                status in REVIEW_STATUSES
                and all(isinstance(value, str) for value in (reviewer, note, at))
                and reviewer.strip()
                and (status == "확인 중" or note.strip())
            ):
                reviews[work_id] = {"status": status, "reviewer": reviewer[:100], "note": note[:2000], "at": at[:30]}
        raw_actions = payload.get("actions", [])
        if not isinstance(raw_actions, list) or len(raw_actions) > 1000:
            raise ValueError("조치 기록 형식을 확인하세요.")
        actions = []
        action_ids = set()
        for raw in raw_actions:
            if not isinstance(raw, dict):
                raise ValueError("조치 기록 형식을 확인하세요.")
            events = raw.get("events", [])
            if not isinstance(events, list) or len(events) > 200 or any(
                not isinstance(event, dict) or
                any(not isinstance(event.get(key), str) for key in ("type", "at", "actor", "note"))
                for event in events
            ):
                raise ValueError("조치 변경 이력 형식을 확인하세요.")
            action = FieldAction(
                action_id=raw["action_id"], work_id=raw["work_id"],
                description=raw["description"], assignee=raw["assignee"],
                due_at=datetime.fromisoformat(raw["due_at"]),
                created_at=datetime.fromisoformat(raw["created_at"]),
                status=raw["status"], needs_review=raw["needs_review"],
                events=tuple({key: event[key][:2000] for key in ("type", "at", "actor", "note")} for event in events),
                work_day=date.fromisoformat(raw["work_day"]) if raw.get("work_day") else None,
            )
            if (
                not all(isinstance(value, str) and value.strip() for value in (
                    action.action_id, action.work_id, action.description, action.assignee,
                )) or any(len(value) > maximum for value, maximum in (
                    (action.action_id, 100), (action.work_id, 100),
                    (action.description, 300), (action.assignee, 100),
                )) or action.action_id in action_ids or action.status not in {"open", "done"}
                or not isinstance(action.needs_review, bool)
            ):
                raise ValueError("조치 필수 항목을 확인하세요.")
            action_ids.add(action.action_id)
            actions.append(action)
        raw_tbm = payload.get("tbm_records", {})
        if not isinstance(raw_tbm, dict) or len(raw_tbm) > 366:
            raise ValueError("TBM 확인 기록 형식을 확인하세요.")
        tbm_records = {}
        for day_text, raw_records in raw_tbm.items():
            day = date.fromisoformat(day_text)
            if not isinstance(raw_records, list) or len(raw_records) > 100:
                raise ValueError("TBM 확인 기록 형식을 확인하세요.")
            history = []
            for raw in raw_records:
                if not isinstance(raw, dict):
                    raise ValueError("TBM 확인 기록 형식을 확인하세요.")
                record = TbmRecord(
                    day=date.fromisoformat(raw["day"]),
                    fingerprint=raw["fingerprint"],
                    confirmed_by=raw["confirmed_by"],
                    audience=raw["audience"],
                    confirmed_at=datetime.fromisoformat(raw["confirmed_at"]),
                    note=raw["note"],
                    weather_summary=raw.get("weather_summary", ""),
                )
                if (
                    record.day != day or len(record.fingerprint) != 64
                    or any(char not in "0123456789abcdef" for char in record.fingerprint)
                    or not all(isinstance(value, str) for value in (record.confirmed_by, record.audience, record.note, record.weather_summary))
                    or not record.confirmed_by.strip() or not record.audience.strip()
                    or len(record.confirmed_by) > 100 or len(record.audience) > 200
                    or len(record.note) > 2000 or len(record.weather_summary) > 1000
                ):
                    raise ValueError("TBM 확인 기록 형식을 확인하세요.")
                history.append(record)
            tbm_records[day_text] = tuple(history)
        raw_deliveries = payload.get("tbm_deliveries", {})
        if not isinstance(raw_deliveries, dict) or len(raw_deliveries) > 366:
            raise ValueError("TBM 진행 기록 형식을 확인하세요.")
        tbm_deliveries = {}
        for day_text, raw_history in raw_deliveries.items():
            day = date.fromisoformat(day_text)
            if not isinstance(raw_history, list) or len(raw_history) > 100:
                raise ValueError("TBM 진행 기록 형식을 확인하세요.")
            history = []
            confirmations = {(record.fingerprint, record.confirmed_at) for record in tbm_records.get(day_text, ())}
            for raw in raw_history:
                if not isinstance(raw, dict):
                    raise ValueError("TBM 진행 기록 형식을 확인하세요.")
                delivery = TbmDelivery(
                    day=date.fromisoformat(raw["day"]),
                    fingerprint=raw["fingerprint"],
                    confirmation_at=datetime.fromisoformat(raw["confirmation_at"]),
                    delivered_by=raw["delivered_by"],
                    attendee_count=raw["attendee_count"],
                    delivered_at=datetime.fromisoformat(raw["delivered_at"]),
                    note=raw["note"],
                )
                if (
                    delivery.day != day or (delivery.fingerprint, delivery.confirmation_at) not in confirmations
                    or not isinstance(delivery.delivered_by, str) or not delivery.delivered_by.strip()
                    or len(delivery.delivered_by) > 100 or not isinstance(delivery.note, str)
                    or len(delivery.note) > 2000
                    or not isinstance(delivery.attendee_count, int) or isinstance(delivery.attendee_count, bool)
                    or not 1 <= delivery.attendee_count <= 10000
                ):
                    raise ValueError("TBM 진행 기록 형식을 확인하세요.")
                history.append(delivery)
            tbm_deliveries[day_text] = tuple(history)
        raw_revisions = payload.get("revisions", [])
        if not isinstance(raw_revisions, list) or len(raw_revisions) > 1000:
            raise ValueError("계획 변경 이력 형식을 확인하세요.")
        revisions = []
        for raw in raw_revisions:
            if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list) or len(raw["entries"]) > 500:
                raise ValueError("계획 변경 이력 형식을 확인하세요.")
            entries = []
            for item in raw["entries"]:
                if not isinstance(item, dict):
                    raise ValueError("계획 변경 이력 형식을 확인하세요.")
                entry = RevisionEntry(item["work_id"], item["activity"], date.fromisoformat(item["day"]), item["kind"])
                if (
                    not isinstance(entry.work_id, str) or not entry.work_id.strip() or len(entry.work_id) > 100
                    or not isinstance(entry.activity, str) or len(entry.activity) > 300
                    or entry.kind not in {"added", "changed", "removed"}
                ):
                    raise ValueError("계획 변경 이력 형식을 확인하세요.")
                entries.append(entry)
            revision = PlanRevision(datetime.fromisoformat(raw["at"]), raw["source"], tuple(entries))
            if not isinstance(revision.source, str) or len(revision.source) > 200:
                raise ValueError("계획 변경 이력 형식을 확인하세요.")
            revisions.append(revision)
        raw_confirmations = payload.get("no_work_confirmations", [])
        if not isinstance(raw_confirmations, list) or len(raw_confirmations) > 1000:
            raise ValueError("계획표 확인 기록 형식을 확인하세요.")
        confirmations = []
        confirmation_days = set()
        for raw in raw_confirmations:
            if not isinstance(raw, dict):
                raise ValueError("계획표 확인 기록 형식을 확인하세요.")
            confirmation = NoWorkConfirmation(
                day=date.fromisoformat(raw["day"]),
                confirmed_by=raw["confirmed_by"],
                note=raw["note"],
                at=datetime.fromisoformat(raw["at"]),
                revision_token=raw["revision_token"],
            )
            if (
                not isinstance(confirmation.confirmed_by, str) or not confirmation.confirmed_by.strip()
                or len(confirmation.confirmed_by) > 100 or not isinstance(confirmation.note, str)
                or len(confirmation.note) > 1000 or not isinstance(confirmation.revision_token, str)
                or len(confirmation.revision_token) > 40 or confirmation.day in confirmation_days
            ):
                raise ValueError("계획표 확인 기록 항목을 확인하세요.")
            confirmation_days.add(confirmation.day)
            confirmations.append(confirmation)
        raw_location = payload.get("weather_location")
        weather_location = None
        if raw_location is not None:
            if not isinstance(raw_location, dict):
                raise ValueError("현장 예보 위치 형식을 확인하세요.")
            weather_location = WeatherLocation(
                name=raw_location["name"], region=raw_location["region"],
                latitude=float(raw_location["latitude"]), longitude=float(raw_location["longitude"]),
            )
            if (
                not isinstance(weather_location.name, str) or not isinstance(weather_location.region, str)
                or not weather_location.name.strip() or len(weather_location.name) > 100
                or len(weather_location.region) > 100
                or not (33 <= weather_location.latitude <= 39.5 and 124 <= weather_location.longitude <= 132)
            ):
                raise ValueError("현장 예보 위치 형식을 확인하세요.")
        plan_name = str(payload.get("plan_name") or "복원한 작업계획")[:200]
        applied_at = str(payload.get("applied_at") or "")[:30]
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        if isinstance(exc, ValueError) and (
            str(exc).endswith("합니다.") or str(exc) == "지원하지 않는 백업 버전입니다."
        ):
            raise
        raise ValueError("백업 파일 형식을 확인하세요.") from exc
    return (
        WorkPlan(
            site.strip(), tuple(sorted(items, key=lambda item: (item.day, item.start, item.work_id))),
            tuple(issues), tuple(confirmations), site_location.strip(),
        ),
        reviews, tuple(actions), tbm_records, tbm_deliveries, tuple(revisions), weather_location, plan_name, applied_at,
    )
