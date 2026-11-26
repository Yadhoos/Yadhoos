from datetime import datetime, timedelta, timezone

import pytest

from smc_core.config import DEFAULT_CONTRACTS
from smc_core import store

T = datetime(2026, 11, 25, 12, 30, tzinfo=timezone.utc)
PLACED_LEGS = [{"lots": 0.09, "r": 2.0}, {"lots": 0.05, "r": 4.2}, {"lots": 0.03, "r": 7.3}]


def test_first_run_no_dir(tmp_path):
    d = tmp_path / "new"
    assert store.is_duplicate(d, "k", T) is False
    assert store.open_trades(d) == []


def test_corrupt_last_line(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"a": 1}\n\n{"ts": "2026-', encoding="utf-8")
    assert store.read_jsonl(p) == [{"a": 1}]


def test_append_check_adds_ts(tmp_path):
    store.append_check(tmp_path, {"pair": "EURUSD", "result": "SKIP"}, T)
    rows = store.read_jsonl(tmp_path / "log.jsonl")
    assert rows[0]["result"] == "SKIP" and rows[0]["ts"].startswith("2026-11-25T12:30")


def test_setup_key_rounding():
    gold, eu = DEFAULT_CONTRACTS["XAUUSD"], DEFAULT_CONTRACTS["EURUSD"]
    assert store.setup_key("XAUUSD", "sell", 2388.04, gold) == store.setup_key("XAUUSD", "sell", 2388.31, gold)
    assert store.setup_key("XAUUSD", "sell", 2388.04, gold) == "XAUUSD:sell:2388.00"
    assert store.setup_key("EURUSD", "buy", 1.10012, eu) != store.setup_key("EURUSD", "buy", 1.10148, eu)


def test_duplicate_window(tmp_path):
    store.record_alert(tmp_path, "k", T, {"x": 1})
    assert store.is_duplicate(tmp_path, "k", T + timedelta(hours=23)) is True
    assert store.is_duplicate(tmp_path, "k", T + timedelta(hours=25)) is False
    assert store.is_duplicate(tmp_path, "other", T) is False


def test_open_trades_lifecycle(tmp_path):
    store.append_trade_event(tmp_path, {"trade_id": "A", "pair": "EURUSD", "type": "placed"}, T)
    store.append_trade_event(tmp_path, {"trade_id": "B", "pair": "XAUUSD", "type": "placed"}, T)
    store.append_trade_event(tmp_path, {"trade_id": "A", "pair": "EURUSD", "type": "closed"}, T)
    assert [t["trade_id"] for t in store.open_trades(tmp_path)] == ["B"]
    assert store.pair_has_open_trade(tmp_path, "EURUSD") is False
    assert store.pair_has_open_trade(tmp_path, "XAUUSD") is True


def test_trade_event_validation(tmp_path):
    with pytest.raises(ValueError):
        store.append_trade_event(tmp_path, {"pair": "EURUSD", "type": "placed"}, T)
    with pytest.raises(ValueError):
        store.append_trade_event(tmp_path, {"trade_id": "A", "pair": "EURUSD", "type": "bought"}, T)


def test_realized_r():
    placed = {"legs": PLACED_LEGS}
    assert store.realized_r(placed, {0: "tp", 1: "be", 2: "be"}) == 1.06
    assert store.realized_r(placed, {0: "sl", 1: "sl", 2: "sl"}) == -1.0
    with pytest.raises(ValueError):
        store.realized_r(placed, {0: "tp"})  # every leg needs an outcome


def test_notify_once(tmp_path):
    assert store.notify_once(tmp_path, "setup_problem", T) is True
    assert store.notify_once(tmp_path, "setup_problem", T + timedelta(hours=1)) is False
    assert store.notify_once(tmp_path, "setup_problem", T + timedelta(hours=13)) is True
