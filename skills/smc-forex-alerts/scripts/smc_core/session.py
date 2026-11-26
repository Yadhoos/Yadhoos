"""Killzones, paper/alert mode resolution and candle alignment (New York time)."""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from .config import Config

NY = ZoneInfo("America/New_York")

# (name, start inclusive, end exclusive) in New York wall-clock time
KILLZONES = (
    ("London", time(2, 0), time(5, 0)),
    ("NY", time(7, 0), time(10, 0)),
)


def _to_ny(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(NY)


def killzone_at(now: datetime) -> str | None:
    local = _to_ny(now)
    if local.weekday() >= 5:  # Saturday, Sunday
        return None
    t = local.time()
    for name, start, end in KILLZONES:
        if start <= t < end:
            return name
    return None


def effective_mode(cfg: Config, now: datetime) -> str:
    if cfg.mode == "paper" and cfg.paper_until is not None and _to_ny(now).date() <= cfg.paper_until:
        return "paper"
    return "alert"


def report_due(cfg: Config, now: datetime, report_exists: bool) -> bool:
    return (
        cfg.mode == "paper"
        and cfg.paper_until is not None
        and _to_ny(now).date() > cfg.paper_until
        and not report_exists
    )


def seconds_to_next_candle(now: datetime, settle_s: int = 60) -> int:
    local = _to_ny(now)
    into = (local.minute % 15) * 60 + local.second
    return (900 - into) + settle_s
