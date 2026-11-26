from dataclasses import replace
from pathlib import Path

import pytest

from smc_core.config import DEFAULT_CONTRACTS, load_config
from smc_core.risk import build_plan, lot_size, r_multiple, select_targets, split_lots

CFG = load_config(Path(__file__).resolve().parents[1] / "config.example.json")
GOLD = DEFAULT_CONTRACTS["XAUUSD"]
EU = DEFAULT_CONTRACTS["EURUSD"]
GOLD_LEVELS = [2377.6, 2366.2, 2350.0, 2300.0]


def test_r_multiple_sell():
    assert r_multiple("sell", 2388.0, 2393.2, 2377.6) == pytest.approx(2.0)


def test_spec_example_targets():
    targets, reason = select_targets("sell", 2388.0, 2393.2, GOLD_LEVELS)
    assert reason is None
    assert [round(t.r, 1) for t in targets] == [2.0, 4.2, 7.3]
    assert [t.price for t in targets] == [2377.6, 2366.2, 2350.0]
    assert not any(t.capped for t in targets)


def test_nearest_below_2r_skips():
    assert select_targets("buy", 1.1000, 1.0990, [1.1014, 1.1050]) == ([], "rr below 2 (1.40)")


def test_cap_at_10r():
    targets, reason = select_targets("buy", 100.0, 99.0, [103.0, 115.0])
    assert reason is None
    assert [(t.price, round(t.r, 2), t.capped) for t in targets] == [(103.0, 3.0, False), (110.0, 10.0, True)]


def test_first_target_beyond_10r_capped():
    targets, _ = select_targets("buy", 100.0, 99.0, [150.0])
    assert [(t.price, t.capped) for t in targets] == [(110.0, True)]


def test_sl_wrong_side():
    assert select_targets("buy", 100.0, 101.0, [105.0]) == ([], "sl on wrong side")
    assert select_targets("sell", 100.0, 100.0, [95.0]) == ([], "sl on wrong side")


def test_levels_behind_entry_ignored():
    assert select_targets("buy", 100.0, 99.0, [98.0, 95.0]) == ([], "no target")


def test_bad_direction():
    with pytest.raises(ValueError):
        r_multiple("up", 1, 0, 2)


def test_lot_size_gold():
    assert lot_size(100, 2388.0, 2393.2, GOLD) == 0.19


def test_lot_size_eurusd():
    assert lot_size(100, 1.1000, 1.0988, EU) == 0.83


def test_lot_size_rounds_down():
    assert lot_size(0.199999 * 520, 2388.0, 2393.2, GOLD) == 0.19


def test_position_too_small():
    assert build_plan(CFG, "XAUUSD", "sell", 2388.0, 2393.2, GOLD_LEVELS, balance=100) == (None, "position too small")


def test_split_lots_leftover_to_first_leg():
    # Ruling: leftover from flooring goes to leg 1 so legs sum to the 1% total
    assert split_lots(0.19, [0.5, 0.3, 0.2]) == [0.11, 0.05, 0.03]


def test_split_small_positions_keep_every_target():
    # Final review I7: each target keeps at least 0.01 when the total allows it
    assert split_lots(0.03, [0.5, 0.3, 0.2]) == [0.01, 0.01, 0.01]
    assert split_lots(0.04, [0.5, 0.3, 0.2]) == [0.02, 0.01, 0.01]
    assert split_lots(0.02, [0.5, 0.3, 0.2]) == [0.01, 0.01, 0.0]
    plan, reason = build_plan(CFG, "XAUUSD", "sell", 2388.0, 2393.2, GOLD_LEVELS, balance=1600)
    assert reason is None
    assert plan.total_lots == 0.03
    assert [(leg.lots, leg.tp) for leg in plan.legs] == [(0.01, 2377.6), (0.01, 2366.2), (0.01, 2350.0)]


def test_split_drops_zero_leg():
    plan, _ = build_plan(CFG, "XAUUSD", "sell", 2388.0, 2393.2, GOLD_LEVELS, balance=1100)
    assert [(leg.lots, leg.tp) for leg in plan.legs] == [(0.01, 2377.6), (0.01, 2366.2)]


def test_stop_too_tight_rejected():
    # Final review I3: a misread SL right next to entry must not create a huge position
    assert build_plan(CFG, "EURUSD", "buy", 1.10000, 1.09999, [1.1001], balance=10000) == (None, "stop too tight")
    assert build_plan(CFG, "XAUUSD", "sell", 2388.0, 2388.5, [2386.0], balance=10000) == (None, "stop too tight")


def test_position_too_large_rejected():
    big = replace(CFG, max_lots=1.0)
    assert build_plan(big, "XAUUSD", "sell", 2388.0, 2393.2, GOLD_LEVELS, balance=100000) == (None, "position too large")


def test_build_plan_spec_example():
    plan, reason = build_plan(CFG, "XAUUSD", "sell", 2388.0, 2393.2, GOLD_LEVELS, balance=10000)
    assert reason is None
    assert plan.risk_amount == 100
    assert plan.total_lots == 0.19
    assert [leg.lots for leg in plan.legs] == [0.11, 0.05, 0.03]
    assert sum(leg.lots for leg in plan.legs) * 5.2 * 100 <= 100 + 1e-9


def test_build_plan_rejects_low_rr():
    plan, reason = build_plan(CFG, "EURUSD", "buy", 1.1000, 1.0990, [1.1014], balance=10000)
    assert plan is None and reason.startswith("rr below 2")


def test_build_plan_two_targets_uses_60_40():
    plan, _ = build_plan(CFG, "EURUSD", "buy", 1.1000, 1.0990, [1.1020, 1.1040], balance=10000)
    assert plan.total_lots == 1.0
    assert [leg.lots for leg in plan.legs] == [0.6, 0.4]


def test_unknown_pair():
    with pytest.raises(ValueError):
        build_plan(CFG, "USDJPY", "buy", 150.0, 149.0, [153.0], balance=10000)
