#!/usr/bin/env python3
"""SMC forex alerts helper. Every command prints one JSON object.

Usage: python scripts/smc.py [--config PATH] [--now ISO] <command> [...]
Commands: status, plan, log-check, record-alert, trade, trades, message, notify-once, report
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smc_core import store  # noqa: E402
from smc_core.config import load_config  # noqa: E402
from smc_core.message import alert_message, event_message, EVENTS  # noqa: E402
from smc_core.report import render_report, report_headline, summarize  # noqa: E402
from smc_core.risk import build_plan  # noqa: E402
from smc_core.session import NY, effective_mode, killzone_at, report_due, seconds_to_next_candle  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
REPORT_WAIT_DAYS = 3


class JsonArgParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"error": message}))
        sys.exit(2)


def _json_arg(text: str) -> dict:
    """A JSON object, or @path to read it from a file (avoids shell quoting problems)."""
    if text.startswith("@"):
        try:
            text = Path(text[1:]).expanduser().read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ValueError(f"cannot read {text[1:]}: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON argument must be an object")
    return value


def cmd_status(cfg, now, args):
    exists = (cfg.data_dir / "paper-report.md").exists()
    local = now.astimezone(NY)
    open_now = store.open_trades(cfg.data_dir)
    due = report_due(cfg, now, exists)
    if due and open_now and local.date() <= cfg.paper_until + timedelta(days=REPORT_WAIT_DAYS):
        due = False  # wait for trades still open at the end of the trial
    return {
        "now_ny": local.isoformat(timespec="minutes"),
        "weekday": local.strftime("%A"),
        "killzone": killzone_at(now),
        "mode": effective_mode(cfg, now),
        "paper_until": cfg.paper_until.isoformat() if cfg.paper_until else None,
        "report_due": due,
        "manage_open_trades": bool(open_now),
        "next_tick_s": seconds_to_next_candle(now),
        "symbols": cfg.symbols,
    }


def cmd_plan(cfg, now, args):
    pair = args.pair.upper()
    if args.balance is None:
        balance, currency = cfg.balance, cfg.account_currency.upper()
    else:
        balance, currency = args.balance, (args.balance_currency or "USD").upper()
    rate = args.quote_to_account
    if rate is None:
        if currency != "USD":
            raise ValueError(f"--quote-to-account (USD to {currency} rate) is required for a {currency} balance")
        rate = 1.0
    plan, reason = build_plan(cfg, pair, args.direction, args.entry, args.sl, args.levels, balance, rate)
    spec = cfg.contracts[pair]
    out = {
        "ok": plan is not None,
        "reason": reason,
        "plan": asdict(plan) if plan else None,
        "message": None,
        "message_alert": None,
        "key": store.setup_key(pair, args.direction, args.entry, spec),
        "duplicate": False,
        "pair_has_open_trade": store.pair_has_open_trade(cfg.data_dir, pair),
    }
    out["duplicate"] = store.is_duplicate(cfg.data_dir, out["key"], now)
    if plan:
        kz = killzone_at(now) or "-"
        out["message"] = alert_message(plan, spec, kz, cfg.risk_pct, paper=effective_mode(cfg, now) == "paper")
        out["message_alert"] = alert_message(plan, spec, kz, cfg.risk_pct, paper=False)
    return out


def cmd_log_check(cfg, now, args):
    store.append_check(cfg.data_dir, _json_arg(args.json), now)
    return {"ok": True}


def cmd_record_alert(cfg, now, args):
    store.record_alert(cfg.data_dir, args.key, now, _json_arg(args.json))
    return {"ok": True}


def cmd_trade(cfg, now, args):
    event = _json_arg(args.json)
    if event.get("type") == "closed" and "result_r" not in event and args.outcomes:
        placed = store.find_placed(cfg.data_dir, event.get("trade_id", ""))
        if placed is None:
            raise ValueError(f"no placed event for trade {event.get('trade_id')!r}")
        event["outcomes"] = _json_arg(args.outcomes)
        event["result_r"] = store.realized_r(placed, event["outcomes"])
    store.append_trade_event(cfg.data_dir, event, now)
    return {"ok": True, "event": event}


def cmd_trades(cfg, now, args):
    return {"trades": store.open_trades(cfg.data_dir) if args.open else store.trade_events(cfg.data_dir)}


def cmd_message(cfg, now, args):
    return {"message": event_message(args.kind, args.pair, args.detail)}


def cmd_notify_once(cfg, now, args):
    return {"send": store.notify_once(cfg.data_dir, args.flag, now)}


def cmd_report(cfg, now, args):
    end = cfg.paper_until or now.astimezone(NY).date()
    start = end - timedelta(days=6)
    summary = summarize(store.trade_events(cfg.data_dir))
    text = render_report(summary, start, end, store.read_jsonl(cfg.data_dir / "log.jsonl"))
    path = cfg.data_dir / "paper-report.md"
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "message": event_message("report", "", report_headline(summary))}


def build_parser() -> argparse.ArgumentParser:
    p = JsonArgParser(prog="smc.py", description="SMC forex alerts helper (JSON output)")
    p.add_argument("--config", type=Path, default=SKILL_DIR / "config.json")
    p.add_argument("--now", help="ISO time with offset (testing); default: current time")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)

    s = sub.add_parser("plan")
    s.add_argument("--pair", required=True)
    s.add_argument("--direction", required=True, choices=["buy", "sell"])
    s.add_argument("--entry", required=True, type=float)
    s.add_argument("--sl", required=True, type=float)
    s.add_argument("--levels", required=True, type=float, nargs="+")
    s.add_argument("--balance", type=float)
    s.add_argument("--balance-currency", help="currency of --balance (default USD)")
    s.add_argument("--quote-to-account", type=float, help="USD to account-currency rate (required if not USD)")
    s.set_defaults(fn=cmd_plan)

    s = sub.add_parser("log-check")
    s.add_argument("--json", required=True)
    s.set_defaults(fn=cmd_log_check)

    s = sub.add_parser("record-alert")
    s.add_argument("--key", required=True)
    s.add_argument("--json", default="{}")
    s.set_defaults(fn=cmd_record_alert)

    s = sub.add_parser("trade")
    s.add_argument("--json", required=True)
    s.add_argument("--outcomes")
    s.set_defaults(fn=cmd_trade)

    s = sub.add_parser("trades")
    s.add_argument("--open", action="store_true")
    s.set_defaults(fn=cmd_trades)

    s = sub.add_parser("message")
    s.add_argument("--kind", required=True, choices=sorted(EVENTS))
    s.add_argument("--pair", default="")
    s.add_argument("--detail", default="")
    s.set_defaults(fn=cmd_message)

    s = sub.add_parser("notify-once")
    s.add_argument("--flag", required=True)
    s.set_defaults(fn=cmd_notify_once)

    sub.add_parser("report").set_defaults(fn=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("--now needs a UTC offset, e.g. 2026-11-25T12:30:00+00:00")
        cfg = load_config(args.config)
        print(json.dumps(args.fn(cfg, now, args)))
        return 0
    except Exception as exc:  # every failure must still be one JSON object
        msg = str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}"
        print(json.dumps({"error": msg}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
