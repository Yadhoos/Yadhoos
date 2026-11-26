from pathlib import Path

import pytest

from smc_core.config import DEFAULT_CONTRACTS, load_config
from smc_core.message import alert_message, event_message, fmt_r
from smc_core.risk import build_plan

CFG = load_config(Path(__file__).resolve().parents[1] / "config.example.json")
GOLD_PLAN, _ = build_plan(CFG, "XAUUSD", "sell", 2388.0, 2393.2, [2377.6, 2366.2, 2350.0], balance=10000)
EXPECTED = "XAUUSD SELL 2388.00 SL 2393.20 0.19lot(1%) TP1 2377.60(2R) TP2 2366.20(4.2R) TP3 2350.00(7.3R) NY"


def test_fmt_r():
    assert (fmt_r(2.0), fmt_r(4.23), fmt_r(10.0), fmt_r(1.996)) == ("2R", "4.2R", "10R", "2R")


def test_alert_spec_example():
    assert alert_message(GOLD_PLAN, DEFAULT_CONTRACTS["XAUUSD"], "NY", 1.0, paper=False) == EXPECTED


def test_paper_prefix():
    assert alert_message(GOLD_PLAN, DEFAULT_CONTRACTS["XAUUSD"], "NY", 1.0, paper=True) == "PAPER placed: " + EXPECTED


def test_fx_five_decimals_and_length():
    plan, _ = build_plan(CFG, "GBPUSD", "sell", 1.27345, 1.27512, [1.27011, 1.26500, 1.25675], balance=10000)
    msg = alert_message(plan, DEFAULT_CONTRACTS["GBPUSD"], "London", 1.0, paper=True)
    assert "1.27345" in msg and msg.endswith("London")
    assert len(msg) <= 200 and "\n" not in msg


def test_event_formats():
    assert event_message("tp1_be", "EURUSD") == "PAPER EURUSD: TP1 hit, SL moved to breakeven"
    assert event_message("closed", "EURUSD", "+2.9R") == "PAPER EURUSD: trade closed +2.9R"
    assert event_message("cancelled", "EURUSD", "not filled in 2h") == "PAPER EURUSD: entry cancelled (not filled in 2h)"
    assert event_message("guard", "") == "SMC scanner: trading panel is not Paper Trading - no orders placed, trading paused"
    assert event_message("setup_problem", "", "TradingView tab not found") == "SMC scanner: TradingView tab not found - checks paused until fixed"
    assert event_message("report", "", "3 trades, 33% win, +1.9R") == "SMC paper week done: 3 trades, 33% win, +1.9R - see ~/smc-alerts/paper-report.md"


def test_unknown_kind():
    with pytest.raises(ValueError):
        event_message("hello", "EURUSD")


def test_truncation():
    msg = event_message("setup_problem", "", "x" * 300)
    assert len(msg) == 200 and msg.endswith("...")
