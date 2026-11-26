"""Korean local calendar and wall-clock helpers for field operations."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


_KST = timezone(timedelta(hours=9), name="KST")


def now_korea() -> datetime:
    """Return a naive KST wall time for existing local datetime fields."""
    return datetime.now(_KST).replace(tzinfo=None)


def today_korea() -> date:
    """Return today's date in the dashboard's Korean business timezone."""
    return datetime.now(_KST).date()
