"""One-line (<=200 char) notification texts."""
from __future__ import annotations

from .config import ContractSpec
from .risk import Plan

MAX_LEN = 200

EVENTS = {
    "tp1_be": "PAPER {pair}: TP1 hit, SL moved to breakeven",
    "closed": "PAPER {pair}: trade closed {detail}",
    "cancelled": "PAPER {pair}: entry cancelled ({detail})",
    "guard": "SMC scanner: trading panel is not Paper Trading - no orders placed, trading paused",
    "setup_problem": "SMC scanner: {detail} - checks paused until fixed",
    "report": "SMC paper week done: {detail} - see ~/smc-alerts/paper-report.md",
}


def _clip(text: str) -> str:
    text = " ".join(text.split())  # one line
    return text if len(text) <= MAX_LEN else text[: MAX_LEN - 3] + "..."


def fmt_r(r: float) -> str:
    return f"{round(r, 1):g}R"


def alert_message(plan: Plan, spec: ContractSpec, killzone: str, risk_pct: float, paper: bool) -> str:
    d = spec.price_decimals
    parts = [
        plan.pair, plan.direction.upper(), f"{plan.entry:.{d}f}",
        "SL", f"{plan.sl:.{d}f}", f"{plan.total_lots:.2f}lot({risk_pct:g}%)",
    ]
    for i, leg in enumerate(plan.legs, 1):
        parts.append(f"TP{i} {leg.tp:.{d}f}({fmt_r(leg.r)})")
    parts.append(killzone)
    text = " ".join(parts)
    return _clip(("PAPER placed: " if paper else "") + text)


def event_message(kind: str, pair: str, detail: str = "") -> str:
    if kind not in EVENTS:
        raise ValueError(f"unknown message kind {kind!r}")
    return _clip(EVENTS[kind].format(pair=pair, detail=detail))
