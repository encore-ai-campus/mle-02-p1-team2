"""Compact applied-plan revision history for manager handover."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from shining_chatbot.business_time import now_korea
from shining_chatbot.work_plan import WorkPlan, compare_plans


@dataclass(frozen=True)
class RevisionEntry:
    work_id: str
    activity: str
    day: date
    kind: str


@dataclass(frozen=True)
class PlanRevision:
    at: datetime
    source: str
    entries: tuple[RevisionEntry, ...]


def make_revision(previous: WorkPlan | None, updated: WorkPlan, source: str) -> PlanRevision:
    now = now_korea()
    old = {item.work_id: item for item in previous.items} if previous and previous.site == updated.site else {}
    new = {item.work_id: item for item in updated.items}
    if previous is None or previous.site != updated.site:
        kinds = {"added": tuple(new), "changed": (), "removed": ()}
    else:
        changes = compare_plans(previous, updated)
        kinds = {"added": changes.added, "changed": changes.changed, "removed": changes.removed}
    entries = tuple(
        RevisionEntry(work_id, (new.get(work_id) or old[work_id]).activity,
                      (new.get(work_id) or old[work_id]).day, kind)
        for kind, ids in kinds.items()
        for work_id in ids
    )
    return PlanRevision(now, source[:200], entries)


def day_revision_token(revisions: tuple[PlanRevision, ...], day: date) -> str:
    """Identify the latest applied change that affected one workday."""
    latest = next(
        (revision for revision in reversed(revisions) if any(entry.day == day for entry in revision.entries)),
        None,
    )
    return latest.at.isoformat() if latest else ""
