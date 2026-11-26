import json
from datetime import date
from pathlib import Path

import pytest

from smc_core.config import load_config

SKILL_DIR = Path(__file__).resolve().parents[1]


def write(tmp_path, overrides):
    data = json.loads((SKILL_DIR / "config.example.json").read_text())
    data.update(overrides)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))
    return p


def test_loads_example():
    cfg = load_config(SKILL_DIR / "config.example.json")
    assert cfg.mode == "paper"
    assert cfg.paper_until == date(2026, 12, 4)
    assert cfg.contracts["XAUUSD"].units_per_lot == 100
    assert cfg.partials[3] == [0.5, 0.3, 0.2]
    assert cfg.data_dir == Path.home() / "smc-alerts"


def test_override_contract(tmp_path):
    cfg = load_config(write(tmp_path, {"contracts": {"XAUUSD": {"units_per_lot": 10, "pip_size": 0.1, "price_decimals": 2}}}))
    assert cfg.contracts["XAUUSD"].units_per_lot == 10
    assert cfg.contracts["EURUSD"].units_per_lot == 100000


def test_bad_mode_raises(tmp_path):
    with pytest.raises(ValueError, match="mode"):
        load_config(write(tmp_path, {"mode": "live"}))


def test_partials_must_sum_to_one(tmp_path):
    with pytest.raises(ValueError):
        load_config(write(tmp_path, {"partials": {"3": [0.5, 0.3, 0.3]}}))


def test_bad_paper_until_becomes_none(tmp_path):
    cfg = load_config(write(tmp_path, {"paper_until": "next week"}))
    assert cfg.paper_until is None


@pytest.mark.parametrize("value", [0, 5.5])
def test_risk_pct_bounds(tmp_path, value):
    with pytest.raises(ValueError, match="risk_pct"):
        load_config(write(tmp_path, {"risk_pct": value}))


def test_bom_config_loads(tmp_path):
    p = write(tmp_path, {})
    p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes())
    assert load_config(p).mode == "paper"


def test_balance_required(tmp_path):
    with pytest.raises(ValueError, match="balance"):
        load_config(write(tmp_path, {"balance": 0}))


def test_max_lots_default(tmp_path):
    assert load_config(write(tmp_path, {})).max_lots == 10.0
