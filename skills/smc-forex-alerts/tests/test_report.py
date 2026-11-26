from datetime import date

import pytest

from smc_core.report import render_report, report_headline, summarize


def ev(tid, pair, typ, **kw):
    return {"trade_id": tid, "pair": pair, "type": typ, **kw}


EVENTS = [
    ev("A", "EURUSD", "placed"), ev("B", "XAUUSD", "placed"), ev("C", "GBPUSD", "placed"), ev("D", "EURUSD", "placed"),
    ev("A", "EURUSD", "closed", result_r=2.9), ev("B", "XAUUSD", "closed", result_r=-1.0),
    ev("C", "GBPUSD", "closed", result_r=0.0), ev("D", "EURUSD", "cancelled", reason="not filled in 2h"),
]
LOG = [{"result": "SKIP", "reason": "rr below 2 (1.40)"}, {"result": "SKIP", "reason": "rr below 2 (1.40)"},
       {"result": "SKIP", "reason": "unreadable"}, {"result": "BUY", "reason": ""}]


def test_summary_counts():
    s = summarize(EVENTS)
    assert (s["trades"], s["closed"], s["cancelled"], s["open"]) == (4, 3, 1, 0)
    assert (s["wins"], s["losses"], s["breakeven"]) == (1, 1, 1)
    assert s["win_rate"] == pytest.approx(1 / 3)
    assert s["total_r"] == pytest.approx(1.9)
    assert s["by_pair"]["EURUSD"] == {"trades": 2, "total_r": pytest.approx(2.9)}


def test_empty_week():
    s = summarize([])
    assert s["win_rate"] == 0
    text = render_report(s, date(2026, 11, 28), date(2026, 12, 4), [])
    assert "No trades" in text


def test_render_has_sections():
    text = render_report(summarize(EVENTS), date(2026, 11, 28), date(2026, 12, 4), LOG)
    for h in ["# SMC Paper Trading Week", "## Results", "## By pair", "## Cancelled and open trades", "## SKIP reasons"]:
        assert h in text
    assert "EURUSD" in text and "rr below 2 (1.40) | 2" in text


def test_headline():
    assert report_headline(summarize(EVENTS)) == "3 trades, 33% win, +1.9R"
