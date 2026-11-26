"""Load and validate the skill's config.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class ContractSpec:
    units_per_lot: float
    pip_size: float
    price_decimals: int
    min_stop: float = 0.0  # stops shorter than this are treated as a misread


@dataclass(frozen=True)
class Config:
    mode: str
    paper_until: date | None
    balance: float
    account_currency: str
    risk_pct: float
    symbols: dict
    contracts: dict
    partials: dict
    data_dir: Path
    max_lots: float = 10.0


DEFAULT_CONTRACTS = {
    # min_stop = 2x the SL buffer: FX 4 pips, gold 1.0
    "EURUSD": ContractSpec(100000, 0.0001, 5, 0.0004),
    "GBPUSD": ContractSpec(100000, 0.0001, 5, 0.0004),
    "XAUUSD": ContractSpec(100, 0.1, 2, 1.0),
}
DEFAULT_PARTIALS = {1: [1.0], 2: [0.6, 0.4], 3: [0.5, 0.3, 0.2]}
DEFAULT_SYMBOLS = {p: p for p in DEFAULT_CONTRACTS}


def _parse_date(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read config {path}: {exc}") from exc

    mode = raw.get("mode", "alert")
    if mode not in ("paper", "alert"):
        raise ValueError(f"mode must be 'paper' or 'alert', got {mode!r}")

    risk_pct = float(raw.get("risk_pct", 1.0))
    if not 0 < risk_pct <= 5:
        raise ValueError(f"risk_pct must be > 0 and <= 5, got {risk_pct}")

    balance = float(raw.get("balance", 0))
    if balance <= 0:
        raise ValueError("balance must be your account size (> 0)")

    max_lots = float(raw.get("max_lots", 10.0))
    if max_lots <= 0:
        raise ValueError("max_lots must be > 0")

    contracts = dict(DEFAULT_CONTRACTS)
    for pair, spec in (raw.get("contracts") or {}).items():
        try:
            pip = float(spec["pip_size"])
            contracts[pair.upper()] = ContractSpec(
                float(spec["units_per_lot"]), pip, int(spec["price_decimals"]),
                float(spec.get("min_stop", 4 * pip)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"contracts.{pair} needs units_per_lot, pip_size, price_decimals") from exc

    partials = {k: list(v) for k, v in DEFAULT_PARTIALS.items()}
    for count, fractions in (raw.get("partials") or {}).items():
        n = int(count)
        fr = [float(f) for f in fractions]
        if len(fr) != n or any(f <= 0 for f in fr) or abs(sum(fr) - 1.0) > 1e-6:
            raise ValueError(f"partials.{count} must be {n} positive fractions summing to 1")
        partials[n] = fr

    symbols = dict(DEFAULT_SYMBOLS)
    symbols.update({k.upper(): v for k, v in (raw.get("symbols") or {}).items()})

    data_dir = Path(raw.get("data_dir", "~/smc-alerts")).expanduser()

    return Config(
        mode=mode,
        paper_until=_parse_date(raw.get("paper_until")),
        balance=balance,
        account_currency=str(raw.get("account_currency", "USD")),
        risk_pct=risk_pct,
        symbols=symbols,
        contracts=contracts,
        partials=partials,
        data_dir=data_dir,
        max_lots=max_lots,
    )
