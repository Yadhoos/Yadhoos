"""R multiples, target selection, lot sizing and the trade plan."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import Config, ContractSpec

DIRECTIONS = ("buy", "sell")


@dataclass
class Target:
    price: float
    r: float
    capped: bool = False


@dataclass
class Leg:
    lots: float
    tp: float
    r: float


@dataclass
class Plan:
    pair: str
    direction: str
    entry: float
    sl: float
    risk_amount: float
    total_lots: float
    legs: list = field(default_factory=list)


def _sign(direction: str) -> int:
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be 'buy' or 'sell', got {direction!r}")
    return 1 if direction == "buy" else -1


def r_multiple(direction: str, entry: float, sl: float, price: float) -> float:
    sign = _sign(direction)
    risk = (entry - sl) * sign
    if risk <= 0:
        raise ValueError("sl on wrong side")
    return (price - entry) * sign / risk


def select_targets(direction, entry, sl, levels, min_r=2.0, max_r=10.0):
    sign = _sign(direction)
    risk = (entry - sl) * sign
    if risk <= 0:
        return [], "sl on wrong side"
    ahead = sorted({lv for lv in levels if (lv - entry) * sign > 0}, key=lambda lv: abs(lv - entry))
    if not ahead:
        return [], "no target"
    first_r = (ahead[0] - entry) * sign / risk
    if first_r < min_r - 1e-9:
        return [], f"rr below 2 ({first_r:.2f})"
    targets = []
    for lv in ahead:
        if len(targets) == 3:
            break
        r = (lv - entry) * sign / risk
        if r > max_r + 1e-9:
            targets.append(Target(round(entry + sign * max_r * risk, 10), max_r, True))
            break
        targets.append(Target(lv, r, False))
    return targets, None


def _floor_lots(x: float) -> float:
    return math.floor(x * 100 + 1e-9) / 100


def lot_size(risk_amount: float, entry: float, sl: float, spec: ContractSpec, quote_to_account: float = 1.0) -> float:
    per_lot = abs(entry - sl) * spec.units_per_lot * quote_to_account
    if per_lot <= 0:
        return 0.0
    return _floor_lots(risk_amount / per_lot)


def split_lots(total: float, fractions: list) -> list:
    """Floor each leg to 0.01; the leftover goes to leg 1 so legs sum to total.
    Then later legs that got 0.00 take 0.01 from leg 1 while leg 1 can spare it,
    so small positions still keep every target."""
    cents = round(total * 100)
    legs = [math.floor(cents * f + 1e-9) for f in fractions]
    legs[0] += cents - sum(legs)
    for i in range(1, len(legs)):
        if legs[i] == 0 and legs[0] > 1:
            legs[0] -= 1
            legs[i] = 1
    return [c / 100 for c in legs]


def build_plan(cfg: Config, pair: str, direction: str, entry: float, sl: float, levels: list,
               balance: float, quote_to_account: float = 1.0):
    pair = pair.upper()
    if pair not in cfg.contracts:
        raise ValueError(f"unknown pair {pair}")
    for v in (entry, sl, *levels):
        if not math.isfinite(v):
            raise ValueError("entry, sl and levels must be real numbers")
    targets, reason = select_targets(direction, entry, sl, levels)
    if reason:
        return None, reason
    if abs(entry - sl) < cfg.contracts[pair].min_stop - 1e-12:
        return None, "stop too tight"
    risk_amount = balance * cfg.risk_pct / 100
    total = lot_size(risk_amount, entry, sl, cfg.contracts[pair], quote_to_account)
    if total < 0.01:
        return None, "position too small"
    if total > cfg.max_lots:
        return None, "position too large"
    lots = split_lots(total, cfg.partials[len(targets)])
    legs = [Leg(l, t.price, t.r) for l, t in zip(lots, targets) if l > 0]
    return Plan(pair, direction, entry, sl, risk_amount, round(sum(l.lots for l in legs), 2), legs), None
