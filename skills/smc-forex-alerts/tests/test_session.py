from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from smc_core.config import load_config
from smc_core.session import effective_mode, killzone_at, report_due, seconds_to_next_candle

NY = ZoneInfo("America/New_York")
CFG = load_config(Path(__file__).resolve().parents[1] / "config.example.json")


def ny(y, m, d, h, mi=0, s=0):
    return datetime(y, m, d, h, mi, s, tzinfo=NY)


def test_london_window():
    assert killzone_at(ny(2026, 11, 25, 2, 0)) == "London"
    assert killzone_at(ny(2026, 11, 25, 4, 59)) == "London"
    assert killzone_at(ny(2026, 11, 25, 5, 0)) is None
    assert killzone_at(ny(2026, 11, 25, 1, 59)) is None


def test_ny_window():
    assert killzone_at(ny(2026, 11, 25, 7, 0)) == "NY"
    assert killzone_at(ny(2026, 11, 25, 9, 59)) == "NY"
    assert killzone_at(ny(2026, 11, 25, 10, 0)) is None


def test_input_in_other_tz():
    assert killzone_at(datetime(2026, 11, 25, 12, 30, tzinfo=ZoneInfo("Asia/Kolkata"))) == "London"


def test_dst_gap_week():
    assert killzone_at(datetime(2026, 3, 9, 11, 30, tzinfo=timezone.utc)) == "NY"
    assert killzone_at(datetime(2026, 3, 6, 12, 30, tzinfo=timezone.utc)) == "NY"


def test_weekend_none():
    assert killzone_at(ny(2026, 11, 28, 8)) is None
    assert killzone_at(ny(2026, 11, 29, 8)) is None


def test_naive_raises():
    with pytest.raises(ValueError):
        killzone_at(datetime(2026, 11, 25, 8))


def test_effective_mode_boundary():
    assert effective_mode(CFG, ny(2026, 12, 4, 23, 59)) == "paper"
    assert effective_mode(CFG, ny(2026, 12, 5, 0, 0)) == "alert"


def test_effective_mode_failsafe():
    assert effective_mode(replace(CFG, paper_until=None), ny(2026, 11, 25, 8)) == "alert"
    assert effective_mode(replace(CFG, mode="alert"), ny(2026, 11, 25, 8)) == "alert"


def test_report_due():
    assert report_due(CFG, ny(2026, 12, 5, 8), report_exists=False) is True
    assert report_due(CFG, ny(2026, 12, 5, 8), report_exists=True) is False
    assert report_due(CFG, ny(2026, 12, 4, 8), report_exists=False) is False
    assert report_due(replace(CFG, mode="alert"), ny(2026, 12, 5, 8), report_exists=False) is False


def test_seconds_to_next_candle():
    assert seconds_to_next_candle(ny(2026, 11, 25, 10, 14, 30)) == 90
    assert seconds_to_next_candle(ny(2026, 11, 25, 10, 15, 0)) == 960
