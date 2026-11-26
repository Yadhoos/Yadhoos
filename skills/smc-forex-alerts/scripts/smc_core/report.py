"""End-of-week paper trading report."""
from __future__ import annotations

from collections import Counter
from datetime import date


def summarize(events: list) -> dict:
    placed = [e for e in events if e.get("type") == "placed"]
    closed = [e for e in events if e.get("type") == "closed"]
    cancelled = [e for e in events if e.get("type") == "cancelled"]
    done = {e.get("trade_id") for e in closed + cancelled}
    rs = [float(e.get("result_r", 0.0)) for e in closed]
    by_pair: dict = {}
    for e in placed:
        by_pair.setdefault(e.get("pair", "?"), {"trades": 0, "total_r": 0.0})["trades"] += 1
    for e, r in zip(closed, rs):
        by_pair.setdefault(e.get("pair", "?"), {"trades": 0, "total_r": 0.0})["total_r"] += r
    return {
        "trades": len(placed),
        "closed": len(closed),
        "cancelled": len(cancelled),
        "open": sum(1 for e in placed if e.get("trade_id") not in done),
        "wins": sum(1 for r in rs if r > 0),
        "losses": sum(1 for r in rs if r < 0),
        "breakeven": sum(1 for r in rs if r == 0),
        "win_rate": (sum(1 for r in rs if r > 0) / len(rs)) if rs else 0,
        "total_r": round(sum(rs), 2),
        "by_pair": by_pair,
        "_cancelled": cancelled,
        "_open": [e for e in placed if e.get("trade_id") not in done],
    }


def report_headline(summary: dict) -> str:
    return f"{summary['closed']} trades, {summary['win_rate']:.0%} win, {summary['total_r']:+.1f}R"


def render_report(summary: dict, start: date, end: date, check_log: list) -> str:
    s = summary
    out = [f"# SMC Paper Trading Week", "", f"{start.isoformat()} to {end.isoformat()}", "", "## Results", ""]
    if s["trades"] == 0:
        out.append("No trades were placed this week.")
    else:
        out += [
            f"- Trades placed: {s['trades']} (closed {s['closed']}, cancelled {s['cancelled']}, still open {s['open']})",
            f"- Wins / losses / breakeven: {s['wins']} / {s['losses']} / {s['breakeven']}",
            f"- Win rate (closed trades): {s['win_rate']:.0%}",
            f"- Total result: {s['total_r']:+.2f}R",
        ]
    out += ["", "## By pair", "", "| Pair | Trades | Total R |", "|---|---|---|"]
    for pair, v in sorted(s["by_pair"].items()):
        out.append(f"| {pair} | {v['trades']} | {v['total_r']:+.2f} |")
    out += ["", "## Cancelled and open trades", ""]
    rows = [f"- {e.get('trade_id')} {e.get('pair')}: cancelled ({e.get('reason', 'no reason')})" for e in s.get("_cancelled", [])]
    rows += [f"- {e.get('trade_id')} {e.get('pair')}: still open" for e in s.get("_open", [])]
    out += rows or ["None."]
    out += ["", "## SKIP reasons", "", "| Reason | Count |", "|---|---|"]
    reasons = Counter(r.get("reason") or "unknown" for r in check_log if r.get("result") == "SKIP")
    for reason, n in reasons.most_common(5):
        out.append(f"{reason} | {n}".join(["| ", " |"]))
    if not reasons:
        out.append("| none | 0 |")
    out += ["", "_Paper trading results only. Not financial advice._", ""]
    return "\n".join(out)
