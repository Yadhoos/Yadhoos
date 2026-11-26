"""JSONL logs, alert de-duplication, the paper trade journal and notification flags."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .config import ContractSpec

TRADE_TYPES = {"placed", "tp1_be", "leg_closed", "cancelled", "closed"}
OUTCOME_R = {"sl": -1.0, "be": 0.0}


def _dir(data_dir: Path) -> Path:
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_jsonl(path: Path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _append(path: Path, record: dict) -> None:
    # A torn last line (crash mid-write) has no newline; start a fresh line so
    # this record isn't glued onto it and lost.
    needs_nl = False
    if path.exists() and path.stat().st_size > 0:
        with open(path, "rb") as fh:
            fh.seek(-1, 2)
            needs_nl = fh.read(1) != b"\n"
    with open(path, "a", encoding="utf-8") as fh:
        if needs_nl:
            fh.write("\n")
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_check(data_dir: Path, record: dict, now: datetime) -> None:
    _append(_dir(data_dir) / "log.jsonl", {"ts": now.isoformat(), **record})


def setup_key(pair: str, direction: str, entry: float, spec: ContractSpec) -> str:
    step = 10 * spec.pip_size
    rounded = round(entry / step) * step
    return f"{pair.upper()}:{direction}:{rounded:.{spec.price_decimals}f}"


def _ts(row: dict):
    try:
        return datetime.fromisoformat(row["ts"])
    except (KeyError, TypeError, ValueError):
        return None


def is_duplicate(data_dir: Path, key: str, now: datetime, window_hours: int = 24) -> bool:
    cutoff = now - timedelta(hours=window_hours)
    for row in read_jsonl(Path(data_dir) / "alerts.jsonl"):
        ts = _ts(row)
        if row.get("key") == key and ts is not None and cutoff <= ts <= now:
            return True
    return False


def record_alert(data_dir: Path, key: str, now: datetime, payload: dict) -> None:
    _append(_dir(data_dir) / "alerts.jsonl", {"ts": now.isoformat(), "key": key, "payload": payload})


def append_trade_event(data_dir: Path, event: dict, now: datetime) -> None:
    for field in ("trade_id", "pair", "type"):
        if not event.get(field):
            raise ValueError(f"trade event needs {field}")
    if event["type"] not in TRADE_TYPES:
        raise ValueError(f"trade event type must be one of {sorted(TRADE_TYPES)}")
    _append(_dir(data_dir) / "trades.jsonl", {"ts": now.isoformat(), **event})


def trade_events(data_dir: Path) -> list:
    return read_jsonl(Path(data_dir) / "trades.jsonl")


def open_trades(data_dir: Path) -> list:
    events = trade_events(data_dir)
    done = {e["trade_id"] for e in events if e.get("type") in ("closed", "cancelled")}
    return [e for e in events if e.get("type") == "placed" and e.get("trade_id") not in done]


def pair_has_open_trade(data_dir: Path, pair: str) -> bool:
    return any(t.get("pair", "").upper() == pair.upper() for t in open_trades(data_dir))


def find_placed(data_dir: Path, trade_id: str):
    for e in trade_events(data_dir):
        if e.get("type") == "placed" and e.get("trade_id") == trade_id:
            return e
    return None


def realized_r(placed: dict, leg_outcomes: dict) -> float:
    legs = placed.get("legs") or []
    total = sum(float(l["lots"]) for l in legs)
    if not legs or total <= 0:
        raise ValueError("placed event has no legs")
    outcomes = {int(k): v for k, v in leg_outcomes.items()}
    r = 0.0
    for i, leg in enumerate(legs):
        if i not in outcomes:
            raise ValueError(f"missing outcome for leg {i}")
        o = outcomes[i]
        if o == "tp":
            leg_r = float(leg["r"])
        elif o in OUTCOME_R:
            leg_r = OUTCOME_R[o]
        else:
            raise ValueError(f"outcome must be tp, sl or be, got {o!r}")
        r += leg_r * float(leg["lots"]) / total
    return round(r, 2)


def notify_once(data_dir: Path, flag: str, now: datetime, cooldown_hours: int = 12) -> bool:
    path = _dir(data_dir) / "flags.json"
    try:
        flags = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(flags, dict):
            flags = {}
    except (OSError, json.JSONDecodeError):
        flags = {}
    last = None
    try:
        last = datetime.fromisoformat(flags[flag])
    except (KeyError, TypeError, ValueError):
        pass
    if last is not None and now - last < timedelta(hours=cooldown_hours):
        return False
    flags[flag] = now.isoformat()
    path.write_text(json.dumps(flags), encoding="utf-8")
    return True
