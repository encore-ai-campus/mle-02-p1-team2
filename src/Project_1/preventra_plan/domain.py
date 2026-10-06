"""Plan contracts around the team's unchanged Excel parser."""
from dataclasses import asdict
from datetime import date, time
from io import BytesIO
import json

from openpyxl import Workbook
from preventra_plan.vendor.work_plan import (
    HEADERS, WorkItem, WorkPlan, read_work_plan, missing_work_fields,
    coordination_candidates, compare_plans, work_selection_label,
)
from preventra_plan.vendor.business_time import today_korea


def encode_plan(plan):
    return {"version": 1, "site": plan.site, "site_location": plan.site_location,
            "issues": list(plan.issues), "items": [
                {**asdict(item), "day": item.day.isoformat(),
                 "start": item.start.isoformat(), "end": item.end.isoformat()}
                for item in plan.items]}


def decode_plan(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("저장된 작업계획 형식을 확인할 수 없습니다.")
    raw = payload.get("items")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
        raise ValueError("저장된 작업 개수를 확인해 주세요.")
    items, ids = [], set()
    for row in raw:
        item = WorkItem(**{**row, "day": date.fromisoformat(row["day"]),
                          "start": time.fromisoformat(row["start"]),
                          "end": time.fromisoformat(row["end"])})
        if item.work_id in ids or item.end <= item.start:
            raise ValueError("저장된 작업 ID 또는 시간을 확인해 주세요.")
        ids.add(item.work_id)
        items.append(item)
    return WorkPlan(payload["site"], tuple(items), tuple(payload.get("issues", [])),
                    site_location=payload.get("site_location", ""))


def snapshot(plan, day, work_id=None):
    return {"plan": encode_plan(plan), "day": day.isoformat(), "work_id": work_id}


def daily_rows(plan, day):
    return [item for item in plan.items if item.day == day]


def model_rows(plan, day, work_id=None):
    items = daily_rows(plan, day)
    if work_id:
        items = [item for item in items if item.work_id == work_id]
    # Keep names, contractors and the site address out of model/trace payloads.
    return [{"work_id": item.work_id, "day": item.day.isoformat(),
             "time": f"{item.start:%H:%M}–{item.end:%H:%M}",
             "area": item.area, "activity": item.activity, "equipment": item.equipment,
             "planned_controls": item.planned_controls, "follow_up": item.follow_up,
             "missing_fields": list(missing_work_fields(item)),
             "source": f"{item.sheet} {item.row}행"} for item in items]


def blank_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "작업계획"
    sheet.append(["현장명", ""])
    sheet.append(["현장지역", ""])
    sheet.append(list(HEADERS))
    sheet.freeze_panes = "A4"
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def validate_snapshot(value):
    if value is None:
        return
    if len(json.dumps(value, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
        raise ValueError("저장할 계획 내용이 너무 큽니다.")
    plan = decode_plan(value["plan"])
    day = date.fromisoformat(value["day"])
    selected = value.get("work_id")
    if selected and not any(i.work_id == selected and i.day == day for i in plan.items):
        raise ValueError("선택한 날짜의 작업을 다시 확인해 주세요.")
