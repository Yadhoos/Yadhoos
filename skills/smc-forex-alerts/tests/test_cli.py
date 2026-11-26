import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SMC = SKILL_DIR / "scripts" / "smc.py"
NOW = "2026-11-25T12:30:00+00:00"  # 07:30 New York, NY killzone
GOLD = ["--pair", "XAUUSD", "--direction", "sell", "--entry", "2388.0", "--sl", "2393.2",
        "--levels", "2377.6", "2366.2", "2350.0"]


@pytest.fixture
def cfg(tmp_path):
    data = json.loads((SKILL_DIR / "config.example.json").read_text())
    data["data_dir"] = str(tmp_path / "data")
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))
    return p


def run(cfg, *args, now=NOW, code=0):
    r = subprocess.run([sys.executable, str(SMC), "--config", str(cfg), "--now", now, *args],
                       capture_output=True, text=True)
    assert r.returncode == code, r.stderr + r.stdout
    return json.loads(r.stdout)


def test_status_in_ny_killzone(cfg):
    out = run(cfg, "status")
    assert out["killzone"] == "NY" and out["mode"] == "paper"
    assert out["report_due"] is False and out["symbols"]["XAUUSD"] == "OANDA:XAUUSD"


def test_plan_spec_example(cfg):
    out = run(cfg, "plan", *GOLD)
    assert out["ok"] is True and out["duplicate"] is False and out["pair_has_open_trade"] is False
    assert out["message"] == ("PAPER placed: XAUUSD SELL 2388.00 SL 2393.20 0.19lot(1%) "
                              "TP1 2377.60(2R) TP2 2366.20(4.2R) TP3 2350.00(7.3R) NY")
    assert [leg["lots"] for leg in out["plan"]["legs"]] == [0.11, 0.05, 0.03]


def test_plan_after_record_is_duplicate(cfg):
    key = run(cfg, "plan", *GOLD)["key"]
    assert run(cfg, "record-alert", "--key", key, "--json", "{}")["ok"] is True
    assert run(cfg, "plan", *GOLD)["duplicate"] is True


def test_plan_rejects_low_rr(cfg):
    out = run(cfg, "plan", "--pair", "EURUSD", "--direction", "buy", "--entry", "1.1", "--sl", "1.099",
              "--levels", "1.1014")
    assert out["ok"] is False and out["reason"].startswith("rr below 2")


def test_trade_closed_computes_r(cfg):
    placed = {"trade_id": "XAUUSD-1", "pair": "XAUUSD", "type": "placed",
              "legs": [{"lots": 0.09, "r": 2.0}, {"lots": 0.05, "r": 4.2}, {"lots": 0.03, "r": 7.3}]}
    run(cfg, "trade", "--json", json.dumps(placed))
    assert len(run(cfg, "trades", "--open")["trades"]) == 1
    out = run(cfg, "trade", "--json", json.dumps({"trade_id": "XAUUSD-1", "pair": "XAUUSD", "type": "closed"}),
              "--outcomes", json.dumps({"0": "tp", "1": "be", "2": "be"}))
    assert out["event"]["result_r"] == 1.06
    assert run(cfg, "trades", "--open")["trades"] == []


def test_message_and_notify_once(cfg):
    assert run(cfg, "message", "--kind", "tp1_be", "--pair", "EURUSD")["message"].startswith("PAPER EURUSD")
    assert run(cfg, "notify-once", "--flag", "setup_problem")["send"] is True
    assert run(cfg, "notify-once", "--flag", "setup_problem")["send"] is False


def test_report_written(cfg, tmp_path):
    run(cfg, "trade", "--json", json.dumps({"trade_id": "A", "pair": "EURUSD", "type": "placed"}))
    run(cfg, "trade", "--json", json.dumps({"trade_id": "A", "pair": "EURUSD", "type": "closed", "result_r": 2.0}))
    later = "2026-12-05T13:00:00+00:00"
    assert run(cfg, "status", now=later)["report_due"] is True
    out = run(cfg, "report", now=later)
    assert Path(out["path"]).exists() and out["message"].startswith("SMC paper week done:")
    assert run(cfg, "status", now=later)["report_due"] is False


def test_bad_args_json_error(cfg):
    out = run(cfg, "plan", "--pair", "XAUUSD", "--direction", "up", "--entry", "1", "--sl", "2",
              "--levels", "3", code=2)
    assert "error" in out
