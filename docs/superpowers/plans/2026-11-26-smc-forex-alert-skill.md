# SMC Forex Alert Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code skill that, on a 15-minute loop, reads the user's TradingView charts (EURUSD, GBPUSD, XAUUSD; 4H + 15m) through Claude in Chrome, applies a fixed SMC checklist, and either sends a push alert (`alert` mode) or places and manages trades on TradingView Paper Trading (`paper` mode, one week).

**Architecture:** Claude does what only Claude can do: reading charts and clicking in Chrome, following `SKILL.md` and its reference guides. Everything that must be exact is done by a small stdlib-only Python CLI (`scripts/smc.py`) that Claude calls, which returns JSON: time/killzone/mode decisions, R:R gating, target selection, lot sizing, partial splits, alert text, de-duplication, logs, trade journal and the weekly report. That makes the deterministic half testable here, while the chart-reading half is tested by the user on their PC.

**Tech Stack:** Python ≥ 3.9 standard library (`zoneinfo`, `json`, `argparse`, `dataclasses`, `pathlib`), `tzdata` (needed on Windows for `zoneinfo`), `pytest` for tests. Markdown for the skill files.

**Spec:** `docs/superpowers/specs/2026-11-26-forex-smc-alert-skill-design.md`

## Global Constraints

- Skill lives at `skills/smc-forex-alerts/` in the repo. The user copies it to `~/.claude/skills/smc-forex-alerts/`.
- The Python CLI only uses the standard library plus `tzdata`. Tests use `pytest`. Everything runs on Windows, macOS and Linux (use `pathlib`, no shell-specific code).
- Pairs: `EURUSD`, `GBPUSD`, `XAUUSD`. Timeframes: 4H (swing structure labels) and 15m (internal structure labels).
- Killzones in `America/New_York`: London `02:00–05:00`, New York `07:00–10:00` (start inclusive, end exclusive). No killzones on Saturday or Sunday.
- Risk is 1% of balance per trade. Lot size is always rounded **down** to 0.01. Under 0.01 lots, there is no trade.
- TP1 = nearest opposing liquidity and must be ≥ 2R, or the result is SKIP. TP2/TP3 are the next levels out. Any target beyond 10R is capped at exactly 10R, and nothing is listed after a capped target.
- Partials: 3 targets → 50/30/20, 2 → 60/40, 1 → 100. Configurable.
- Push messages are a single line of ≤ 200 characters with no markdown.
- Duplicate window: 24 hours, keyed on pair + direction + entry rounded to 10 pips (`10 × pip_size`).
- Paper mode only while `mode == "paper"` and today (New York date) ≤ `paper_until`. Anything else, including a missing or invalid `paper_until`, means `alert`.
- Runtime data dir default: `~/smc-alerts/` (`log.jsonl`, `alerts.jsonl`, `trades.jsonl`, `flags.json`, `paper-report.md`, `shots/`).
- Never touch order controls unless effective mode is `paper` **and** the panel shows "Paper Trading". Never trade a real-money account.
- Ambiguity → SKIP with reason `unreadable`.

## Review Focus

1. **DST weeks:** a killzone check on 2026-03-09 (US already on DST, UK not) must still use New York wall-clock time. → tested in Task 2.
2. **Bad levels from the chart read:** an SL on the wrong side of the entry, or targets behind the entry, must be rejected with a reason, never turned into negative or infinite R. → tested in Task 3.
3. **Small account or wide stop:** when the position rounds to < 0.01 lots, the result is SKIP (`position too small`), never rounded up. When one leg rounds to 0.00 the leg is dropped. → tested in Task 3.
4. **Paper end-date boundary:** `paper_until` itself is still paper. The next New York day is alert. A missing or garbage `paper_until` is alert, failing safe. → tested in Task 2.
5. **First run or damaged files:** missing data dir, empty files, or a half-written last JSONL line must be treated as no history, not crash a tick. → tested in Task 5.

---

## File Structure

```
skills/smc-forex-alerts/
  SKILL.md                      # Run procedure Claude follows every tick (Task 9)
  SETUP.md                      # One-time setup on the user's PC (Task 9)
  config.example.json           # Copied to config.json by the user (Task 1)
  requirements.txt              # tzdata (Task 1)
  references/
    smc-checklist.md            # How to read LuxAlgo labels for each checklist item (Task 8)
    paper-trading.md            # Paper Trading guard, placing/managing orders in TradingView (Task 8)
  scripts/
    smc.py                      # CLI entry point, JSON in/out (Task 7)
    smc_core/
      __init__.py
      config.py                 # Config + contract specs (Task 1)
      session.py                # Killzones, effective mode, tick alignment (Task 2)
      risk.py                   # R multiples, target selection, lot sizing, plan (Task 3)
      message.py                # ≤200-char notification text (Task 4)
      store.py                  # JSONL logs, de-dup, trades, flags, realized R (Task 5)
      report.py                 # End-of-week paper report (Task 6)
  tests/
    conftest.py                 # Puts scripts/ on sys.path
    test_config.py  test_session.py  test_risk.py  test_message.py
    test_store.py   test_report.py   test_cli.py   test_skill_docs.py
```

Run all tests with: `python -m pytest skills/smc-forex-alerts/tests -q`

---

### Task 1: Scaffold + config

**Files:**
- Create: `skills/smc-forex-alerts/requirements.txt` (`tzdata>=2024.1`), `config.example.json`, `scripts/smc_core/__init__.py`, `scripts/smc_core/config.py`, `tests/conftest.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) ContractSpec(units_per_lot: float, pip_size: float, price_decimals: int)`
  - `@dataclass(frozen=True) Config(mode: str, paper_until: date | None, balance: float, account_currency: str, risk_pct: float, symbols: dict[str, str], contracts: dict[str, ContractSpec], partials: dict[int, list[float]], data_dir: Path)`
  - `load_config(path: Path) -> Config` raises `ValueError` with a readable message on bad input.
  - `DEFAULT_CONTRACTS`: `EURUSD`/`GBPUSD` = `(100000, 0.0001, 5)`, `XAUUSD` = `(100, 0.1, 2)`
  - `DEFAULT_PARTIALS = {1: [1.0], 2: [0.6, 0.4], 3: [0.5, 0.3, 0.2]}`

`config.example.json`:
```json
{
  "mode": "paper",
  "paper_until": "2026-12-04",
  "balance": 10000,
  "account_currency": "USD",
  "risk_pct": 1.0,
  "symbols": {"EURUSD": "OANDA:EURUSD", "GBPUSD": "OANDA:GBPUSD", "XAUUSD": "OANDA:XAUUSD"},
  "contracts": {},
  "partials": {},
  "data_dir": "~/smc-alerts"
}
```
Empty `contracts`/`partials` mean "use the defaults". Keys provided override per pair or per count. `data_dir` expands `~`.

- [ ] **Step 1: Write `tests/conftest.py`** (insert `Path(__file__).parents[1] / "scripts"` into `sys.path`) **and failing tests** in `test_config.py`:
  - `test_loads_example`: loading `config.example.json` gives `mode == "paper"`, `paper_until == date(2026,12,4)`, `contracts["XAUUSD"].units_per_lot == 100`, `partials[3] == [0.5,0.3,0.2]`, `data_dir == Path.home()/"smc-alerts"`.
  - `test_override_contract`: `{"contracts": {"XAUUSD": {"units_per_lot": 10, "pip_size": 0.1, "price_decimals": 2}}}` merges over defaults, and EURUSD stays default.
  - `test_bad_mode_raises`: `mode: "live"` → `ValueError` matching `"mode"`.
  - `test_partials_must_sum_to_one`: `{"partials": {"3": [0.5,0.3,0.3]}}` → `ValueError`.
  - `test_bad_paper_until_becomes_none`: `"paper_until": "next week"` → `paper_until is None` (no raise; the mode resolves to alert in Task 2).
  - `test_risk_pct_bounds`: `risk_pct` 0 or > 5 → `ValueError`.
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_config.py -q` → FAIL (`ModuleNotFoundError: smc_core`).
- [ ] **Step 3: Implement** `config.py` and the files above. JSON keys for `partials` are strings and must be converted to `int`.
- [ ] **Step 4: Run** the same command → all pass.
- [ ] **Step 5: Commit** `feat(smc): skill scaffold and config loader`.

### Task 2: Session — killzones, mode, tick alignment

**Files:** Create `scripts/smc_core/session.py`. Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `Config` (Task 1).
- Produces:
  - `NY = ZoneInfo("America/New_York")`
  - `killzone_at(now: datetime) -> str | None` returns `"London"`, `"NY"` or `None`. `now` must be timezone-aware, otherwise `ValueError`.
  - `effective_mode(cfg: Config, now: datetime) -> str` returns `"paper"` or `"alert"`, comparing on the New York date.
  - `report_due(cfg: Config, now: datetime, report_exists: bool) -> bool`: True when `cfg.mode == "paper"`, `paper_until` is set, the NY date > `paper_until`, and `not report_exists`.
  - `seconds_to_next_candle(now: datetime, settle_s: int = 60) -> int`: seconds until the next :00/:15/:30/:45 plus `settle_s`.

- [ ] **Step 1: Write failing tests:**
  - `test_london_window`: NY 02:00 → `"London"`, 04:59 → `"London"`, 05:00 → `None`, 01:59 → `None` (on a Wednesday, 2026-11-25).
  - `test_ny_window`: 07:00 → `"NY"`, 09:59 → `"NY"`, 10:00 → `None`.
  - `test_input_in_other_tz`: `datetime(2026,11,25,12,30,tzinfo=ZoneInfo("Asia/Kolkata"))` (= 02:00 NY) → `"London"`.
  - `test_dst_gap_week`: `datetime(2026,3,9,11,30,tzinfo=timezone.utc)` (= 07:30 NY EDT) → `"NY"`. `datetime(2026,3,6,12,30,tzinfo=timezone.utc)` (= 07:30 NY EST) → `"NY"`.
  - `test_weekend_none`: Saturday 2026-11-28 and Sunday 2026-11-29 at 08:00 NY → `None`.
  - `test_naive_raises`.
  - `test_effective_mode_boundary`: with `paper_until=2026-12-04`, NY 2026-12-04 23:59 → `"paper"`, and 2026-12-05 00:00 → `"alert"`.
  - `test_effective_mode_failsafe`: `paper_until=None` → `"alert"`. `mode="alert"` → `"alert"`.
  - `test_report_due`: true on 2026-12-05 with `report_exists=False`, false when `report_exists=True`, false in `alert` mode.
  - `test_seconds_to_next_candle`: 10:14:30 → 90. 10:15:00 → 960 (a full candle away plus 60).
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_session.py -q` → FAIL.
- [ ] **Step 3: Implement** `session.py` by converting `now` with `.astimezone(NY)` before reading hour and weekday.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(smc): killzones, mode resolution, candle alignment`.

### Task 3: Risk — R, targets, lot size, plan

**Files:** Create `scripts/smc_core/risk.py`. Test: `tests/test_risk.py`

**Interfaces:**
- Consumes: `ContractSpec`, `Config` (Task 1).
- Produces:
  - `r_multiple(direction: str, entry: float, sl: float, price: float) -> float` (`direction` is `"buy"` or `"sell"`)
  - `@dataclass Target(price: float, r: float, capped: bool)`
  - `select_targets(direction, entry, sl, levels: list[float], min_r=2.0, max_r=10.0) -> tuple[list[Target], str | None]` returns `(targets, None)` or `([], reason)`.
  - `lot_size(risk_amount: float, entry: float, sl: float, spec: ContractSpec, quote_to_account: float = 1.0) -> float`
  - `split_lots(total: float, fractions: list[float]) -> list[float]`, each rounded down to 0.01.
  - `@dataclass Leg(lots: float, tp: float, r: float)`
  - `@dataclass Plan(pair: str, direction: str, entry: float, sl: float, risk_amount: float, total_lots: float, legs: list[Leg])`
  - `build_plan(cfg: Config, pair: str, direction: str, entry: float, sl: float, levels: list[float], balance: float, quote_to_account: float = 1.0) -> tuple[Plan | None, str | None]`

Rules for `select_targets` (the algorithm isn't fixed by the signature):
1. If the SL is not on the losing side of the entry (buy: `sl < entry`, sell: `sl > entry`), return reason `"sl on wrong side"`.
2. Keep levels strictly on the profit side, deduplicate them, and sort nearest first.
3. If none remain → `"no target"`. If the nearest gives < `min_r` → `"rr below 2 (x.xx)"`, using the actual R to 2 decimals.
4. Walk outwards taking up to 3 levels. A level with R > `max_r` becomes a target at exactly `max_r` (price = `entry ± max_r × risk`, `capped=True`), and the walk stops.

`build_plan`: risk_amount = `balance × risk_pct / 100`. Then compute total lots. If < 0.01 → `(None, "position too small")`. Split by `cfg.partials[len(targets)]`. Legs that round to 0.00 are dropped together with their target. Total = the sum of the kept legs. An unknown pair → `ValueError`.

- [ ] **Step 1: Write failing tests:**
  - `test_r_multiple_sell`: `r_multiple("sell", 2388.0, 2393.2, 2377.6) == pytest.approx(2.0)`.
  - `test_spec_example_targets`: sell, entry 2388.0, SL 2393.2, levels `[2377.6, 2366.2, 2350.0, 2300.0]` → 3 targets with R ≈ 2.0, 4.2, 7.3, none capped.
  - `test_nearest_below_2r_skips` (strict rule): buy entry 1.1000, SL 1.0990, levels `[1.1014, 1.1050]` → `([], "rr below 2 (1.40)")`, even though 1.1050 is 5R.
  - `test_cap_at_10r`: buy entry 100, SL 99, levels `[103, 115]` → targets `[(103, 3R), (110, 10R, capped)]`.
  - `test_sl_wrong_side`: buy with SL above the entry → reason `"sl on wrong side"`.
  - `test_levels_behind_entry_ignored`: buy, levels below the entry only → `"no target"`.
  - `test_lot_size_gold`: risk 100, entry 2388.0, SL 2393.2, XAUUSD spec → `0.19`.
  - `test_lot_size_eurusd`: risk 100, stop 0.0012 → `0.83`.
  - `test_lot_size_rounds_down`: a value that computes to 0.199999 → `0.19`. Guard float error with `math.floor(x * 100 + 1e-9) / 100`.
  - `test_position_too_small`: balance 100, gold, 5.2 stop → `(None, "position too small")`.
  - `test_split_drops_zero_leg`: total 0.03 with 50/30/20 → legs 0.01, 0.00 dropped, 0.00 dropped, so one leg with TP1 only.
  - `test_build_plan_spec_example`: balance 10000, gold example → `total_lots == 0.19`, legs `[0.09, 0.05, 0.03]` (each rounded down; the sum 0.17 ≤ 0.19, so risk stays ≤ 1%).
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_risk.py -q` → FAIL.
- [ ] **Step 3: Implement** `risk.py`. Lot formula: `risk_amount / (abs(entry - sl) * units_per_lot * quote_to_account)`.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(smc): target selection, lot sizing and trade plan`.

### Task 4: Notification messages

**Files:** Create `scripts/smc_core/message.py`. Test: `tests/test_message.py`

**Interfaces:**
- Consumes: `Plan`, `Leg` (Task 3), `ContractSpec` (Task 1).
- Produces:
  - `fmt_r(r: float) -> str`: `2.0 → "2R"`, `4.23 → "4.2R"`, `10.0 → "10R"`
  - `alert_message(plan: Plan, spec: ContractSpec, killzone: str, risk_pct: float, paper: bool) -> str`
  - `event_message(kind: str, pair: str, detail: str = "") -> str`, with `kind` in `{"tp1_be", "closed", "cancelled", "guard", "setup_problem", "report"}`. Unknown → `ValueError`.
  - Every return value is one line of ≤ 200 characters; anything longer is cut to 197 characters plus `"..."`.

Exact formats:
- alert: `"{PAIR} {BUY|SELL} {entry} SL {sl} {lots}lot({risk_pct:g}%) TP1 {p}({r}) TP2 ... {killzone}"`, with prices formatted to `spec.price_decimals` and lots to 2 decimals. In paper mode, prefix with `"PAPER placed: "`.
- `tp1_be`: `"PAPER {PAIR}: TP1 hit, SL moved to breakeven"`
- `closed`: `"PAPER {PAIR}: trade closed {detail}"` (detail such as `"+2.9R"`)
- `cancelled`: `"PAPER {PAIR}: entry cancelled ({detail})"`
- `guard`: `"SMC scanner: trading panel is not Paper Trading - no orders placed, trading paused"`
- `setup_problem`: `"SMC scanner: {detail} - checks paused until fixed"`
- `report`: `"SMC paper week done: {detail} - see ~/smc-alerts/paper-report.md"`

- [ ] **Step 1: Write failing tests:**
  - `test_alert_spec_example`: the gold plan from Task 3 with `XAUUSD` spec, killzone `"NY"` → `"XAUUSD SELL 2388.00 SL 2393.20 0.19lot(1%) TP1 2377.60(2R) TP2 2366.20(4.2R) TP3 2350.00(7.3R) NY"`.
  - `test_paper_prefix`.
  - `test_fx_five_decimals_and_length`: GBPUSD with 3 targets, `"London"`, paper → contains `"1.27345"`, has `len <= 200`, and no `"\n"`.
  - `test_event_formats`: one assertion per kind with the exact strings above.
  - `test_truncation`: a `setup_problem` detail of 300 characters → length 200, ending in `"..."`.
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_message.py -q` → FAIL.
- [ ] **Step 3: Implement** `message.py`.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(smc): notification message formatting`.

### Task 5: Store — logs, de-dup, trades, flags, realized R

**Files:** Create `scripts/smc_core/store.py`. Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `ContractSpec` (Task 1).
- Produces (all take `data_dir: Path` first and create it if missing):
  - `read_jsonl(path: Path) -> list[dict]`: a missing file → `[]`. Blank or unparseable lines are skipped.
  - `append_check(data_dir, record: dict, now: datetime) -> None` → `log.jsonl`, adding `"ts"` (ISO).
  - `setup_key(pair: str, direction: str, entry: float, spec: ContractSpec) -> str` → `"{PAIR}:{direction}:{entry rounded to 10*pip_size, formatted to price_decimals}"`.
  - `is_duplicate(data_dir, key: str, now: datetime, window_hours: int = 24) -> bool` reads `alerts.jsonl`.
  - `record_alert(data_dir, key: str, now: datetime, payload: dict) -> None`.
  - `append_trade_event(data_dir, event: dict, now: datetime) -> None` → `trades.jsonl`. An event needs `trade_id`, `pair` and `type` in `{"placed", "tp1_be", "leg_closed", "cancelled", "closed"}`; otherwise `ValueError`.
  - `open_trades(data_dir) -> list[dict]` returns the `placed` events whose `trade_id` has no `closed` or `cancelled` event.
  - `pair_has_open_trade(data_dir, pair: str) -> bool`.
  - `realized_r(placed: dict, leg_outcomes: dict[int, str]) -> float`. `placed` holds `legs: [{"lots", "r"}, ...]`. An outcome is `"tp"` (gives that leg's `r`), `"sl"` (−1) or `"be"` (0). The result is weighted by each leg's lots over the total lots and rounded to 2 decimals.
  - `notify_once(data_dir, flag: str, now: datetime, cooldown_hours: int = 12) -> bool` → `flags.json`. True if the flag isn't set or is older than the cooldown, and it then records `now`. *(This implements "one setup-problem notification per session". The builder's call is a 12h cooldown, which covers a session.)*

- [ ] **Step 1: Write failing tests:**
  - `test_first_run_no_dir`: `is_duplicate(tmp_path/"new", ...)` is False, and `open_trades` is `[]`.
  - `test_corrupt_last_line`: write a valid line plus `'{"ts": "2026-'` → `read_jsonl` returns 1 record.
  - `test_setup_key_rounding`: XAUUSD entries 2388.04 and 2388.31 → the same key (10 × 0.1 = 1.0 grid). EURUSD entries 1.10012 and 1.10148 → different keys (0.001 grid).
  - `test_duplicate_window`: a record at T. Checked at T+23h → True; at T+25h → False.
  - `test_open_trades_lifecycle`: placed A, placed B, closed A → only B is open. `pair_has_open_trade` follows.
  - `test_trade_event_validation`: a missing `trade_id` → `ValueError`.
  - `test_realized_r`: legs lots `[0.09, 0.05, 0.03]`, r `[2.0, 4.2, 7.3]`. Outcomes `{0:"tp", 1:"be", 2:"be"}` → `round(0.09*2/0.17, 2) == 1.06`. `{0:"sl",1:"sl",2:"sl"}` → `-1.0`.
  - `test_notify_once`: True, then False at +1h, then True at +13h.
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_store.py -q` → FAIL.
- [ ] **Step 3: Implement** `store.py`. Write files with `encoding="utf-8"`, one JSON object per line, opened in append mode.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(smc): logs, de-dup, trade journal and flags`.

### Task 6: Paper week report

**Files:** Create `scripts/smc_core/report.py`. Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `read_jsonl` (Task 5). `closed` events carry `result_r: float`.
- Produces:
  - `summarize(events: list[dict]) -> dict` with the keys `trades` (number of `placed`), `closed`, `cancelled`, `open`, `wins` (`result_r > 0`), `losses` (`< 0`), `breakeven` (`== 0`), `win_rate` (wins/closed, 0 if none closed, as a 0–1 float), `total_r`, and `by_pair: {pair: {"trades", "total_r"}}`.
  - `render_report(summary: dict, start: date, end: date, check_log: list[dict]) -> str`: markdown with the headings `# SMC Paper Trading Week`, `## Results`, `## By pair`, `## Cancelled and open trades`, `## SKIP reasons` (the top 5 `reason` values from `log.jsonl` records with `result == "SKIP"`, with counts).
  - `report_headline(summary: dict) -> str` → `"{closed} trades, {win_rate:.0%} win, {total_r:+.1f}R"`, used as the `detail` of the `report` message.

- [ ] **Step 1: Write failing tests:**
  - `test_summary_counts`: 4 placed; closed with +2.9, −1.0 and 0.0; 1 cancelled → `wins 1, losses 1, breakeven 1, win_rate == 1/3, total_r == 1.9, open == 0`.
  - `test_empty_week`: no events → `win_rate == 0`, and the report renders with a `"No trades"` line instead of failing.
  - `test_render_has_sections`: every heading above is present, and `"EURUSD"` appears in the per-pair table.
  - `test_headline`: → `"3 trades, 33% win, +1.9R"`.
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_report.py -q` → FAIL.
- [ ] **Step 3: Implement** `report.py`.
- [ ] **Step 4: Run** → pass.
- [ ] **Step 5: Commit** `feat(smc): paper week report`.

### Task 7: CLI `smc.py`

**Files:** Create `scripts/smc.py`. Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces the command contract that `SKILL.md` uses. Every command prints exactly one JSON object to stdout and exits 0. Errors print `{"error": "..."}` and exit 2. Global options: `--config PATH` (default: `config.json` next to `smc.py`'s parent, i.e. the skill folder) and `--now ISO` (optional, for tests).

| Command | Args | Output keys |
|---|---|---|
| `status` | — | `now_ny`, `weekday`, `killzone`, `mode` (effective), `paper_until`, `report_due`, `next_tick_s`, `symbols` |
| `plan` | `--pair --direction --entry --sl --levels L [L ...] [--balance B] [--quote-to-account Q]` | `ok`, `reason`, `plan` (as dict), `message`, `key`, `duplicate`, `pair_has_open_trade` |
| `log-check` | `--json '{"pair":..., "result":"BUY\|SELL\|SKIP", "reason":..., "items":{...}}'` | `ok` |
| `record-alert` | `--key K --json PAYLOAD` | `ok` |
| `trade` | `--json EVENT` (for a `closed` event without `result_r`: also `--outcomes '{"0":"tp","1":"be"}'`, and the CLI fills in `result_r` via `realized_r` using the matching `placed` event) | `ok`, `event` |
| `trades` | `--open` | `trades` |
| `message` | `--kind K --pair P [--detail D]` | `message` |
| `notify-once` | `--flag F` | `send` |
| `report` | — | `path`, `message` (writes `paper-report.md` in the data dir; start = `paper_until − 6 days`) |

`--balance` defaults to `cfg.balance`. In paper mode Claude passes the balance read from the panel. `plan` puts the killzone from `status` into the message, and uses `"-"` if outside one. `plan` sets `paper` in the message from the effective mode.

- [ ] **Step 1: Write failing tests** (`subprocess.run([sys.executable, SMC, "--config", cfg, "--now", ...])` against a `tmp_path` config whose `data_dir` is in `tmp_path`):
  - `test_status_in_ny_killzone`: `--now 2026-11-25T12:30:00+00:00` → `killzone == "NY"`, `mode == "paper"`.
  - `test_plan_spec_example`: the gold example → `ok`, `message` equal to the paper-prefixed string from Task 4, and `duplicate False`.
  - `test_plan_after_record_is_duplicate`: `record-alert` with the returned `key`, then `plan` again → `duplicate True`.
  - `test_plan_rejects_low_rr`: → `ok False`, `reason` starts with `"rr below 2"`.
  - `test_trade_closed_computes_r`: `placed` with legs, then `closed` with outcomes → `event.result_r == 1.06`. `trades --open` is then empty.
  - `test_report_written`: after events, `report` → the file exists and `message` starts with `"SMC paper week done:"`.
  - `test_bad_args_json_error`: `plan --direction up` → exit 2 and an `"error"` key.
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_cli.py -q` → FAIL.
- [ ] **Step 3: Implement** `smc.py` with `argparse` subparsers. Map `ValueError` to exit 2.
- [ ] **Step 4: Run** the full suite → pass.
- [ ] **Step 5: Commit** `feat(smc): JSON CLI for the skill`.

### Task 8: Reference guides

**Files:** Create `references/smc-checklist.md`, `references/paper-trading.md`.

These are instructions Claude reads at runtime. Content requirements (values copied from the spec):

`smc-checklist.md`:
- Required LuxAlgo "Smart Money Concepts" settings: Swing and Internal structure on, Order Blocks (internal and swing) on, Fair Value Gaps on, Equal Highs/Lows on, Premium/Discount Zones on. Keep the default lengths, and record any the user changes in SETUP.md.
- For each checklist item 1–6 from the spec: which timeframe, which label set (4H **swing**, 15m **internal**), what "pass" looks like on the chart, and what counts as unclear (→ SKIP `unreadable`).
- How to extract numbers for the `plan` command: entry = the near edge of the OB/FVG, SL = beyond the sweep wick plus a buffer (FX 2 pips, XAUUSD 0.5, documented in the guide only, not in config), and `--levels` = every visible opposing swing high/low and equal highs/lows on 15m and 4H, read from the price axis or the indicator label.
- Sweep window: the last 12 15m candles. Price "near" the zone: within 25% of the stop distance (builder's call).
- The output template for the in-session write-up (✅/❌ per item, levels, partial plan, screenshots).

`paper-trading.md`:
- **Guard procedure:** before every order action, read the trading panel's broker name. Continue only if it is exactly "Paper Trading". Otherwise call `notify-once --flag guard`, send the `guard` message if `send`, and do no order actions for the rest of the session.
- Placing: one limit order per leg with lots, entry, SL and TP from `plan.legs`, then record the `trade` `placed` event with `trade_id` = `{PAIR}-{YYYYMMDDHHMM}`, legs, entry, SL and the order times.
- Management each tick (also outside killzones): read Positions and Orders for each open trade.
  - TP1 filled → move the remaining SLs to the entry, record `tp1_be`, notify.
  - Leg closed → record `leg_closed`.
  - All legs done → record `closed` with outcomes, notify with `fmt` of `result_r`.
  - Entry not filled and price touched the SL, or 8 candles (2 hours) since placement → cancel, record `cancelled`, notify.
- Never place an order for a pair where `pair_has_open_trade` is true.
- Never click anything in the panel other than these order actions. Never open broker-connection dialogs.

- [ ] **Step 1: Write both files** to the requirements above.
- [ ] **Step 2: Verify** by running `grep -c "Paper Trading" skills/smc-forex-alerts/references/paper-trading.md` (≥ 2) and `grep -E "swing|internal" skills/smc-forex-alerts/references/smc-checklist.md` (both present). Task 9's doc test also covers these files.
- [ ] **Step 3: Commit** `docs(smc): chart-reading and paper-trading guides`.

### Task 9: SKILL.md, SETUP.md and doc consistency test

**Files:** Create `SKILL.md`, `SETUP.md`. Test: `tests/test_skill_docs.py`

`SKILL.md`:
- Frontmatter `name: smc-forex-alerts`, plus a `description` that triggers on running the SMC forex scan or loop.
- The tick procedure in order, each step naming the exact CLI command (`python scripts/smc.py ...`, with paths relative to the skill dir):
  1. `status`.
  2. If `report_due`, run `report` and push its `message`.
  3. If mode is `paper`, follow `references/paper-trading.md` management.
  4. If `killzone` is null, end the tick.
  5. Find the "SMC Scanner" tab. On a problem, use `notify-once --flag setup_problem` and the `setup_problem` message, then end the tick.
  6. Loop over the pairs on 4H then 15m per `references/smc-checklist.md`.
  7. On BUY/SELL, run `plan`. If `ok` and not `duplicate` (and, in paper mode, not `pair_has_open_trade`): save the screenshots to `~/smc-alerts/shots/`, then `record-alert`. In alert mode, push `message`. In paper mode, place the orders per the guide and push `message`.
  8. `log-check` for every pair.
- Hard rules at the top: the 4 anti-goals from the spec, the real-money guard, SKIP on ambiguity, and no notification for SKIP.
- Push via the `PushNotification` tool, using the CLI's `message` text verbatim.
- How to start: `/loop 15m run the smc-forex-alerts tick`.

`SETUP.md` (plain language for the user):
1. Install Python ≥ 3.9 and `pip install -r requirements.txt`.
2. Install Claude Code and the Claude in Chrome extension, then allow tradingview.com.
3. Create the TradingView layout "SMC Scanner" with LuxAlgo SMC at the settings from `smc-checklist.md`.
4. Paper Trading: connect TradingView's Paper Trading, and disconnect any real broker for the trial week.
5. Copy `config.example.json` to `config.json`. Set `paper_until` to start date + 6 days, the symbols matching your broker feed, the balance and currency, and check the contract sizes.
6. Copy the folder to `~/.claude/skills/`.
7. Connect Remote Control and install the Claude app on your phone.
8. Keep the PC awake during the killzones (Windows power settings).
9. Start the loop.
10. After the trial, read `paper-report.md`. The skill switches to alerts automatically.
- Include the disclaimer: alerts are not financial advice.

- [ ] **Step 1: Write failing `test_skill_docs.py`:**
  - `test_frontmatter`: `SKILL.md` starts with `---`, has `name: smc-forex-alerts`, and has a non-empty `description`.
  - `test_referenced_files_exist`: every `references/...md` and `scripts/...py` path mentioned in `SKILL.md` exists.
  - `test_cli_commands_exist`: every `smc.py <command>` in `SKILL.md` and `references/*.md` is one of the Task 7 commands (parse the subcommand names from `smc.py --help` output).
  - `test_hard_rules_present`: `SKILL.md` contains `"Paper Trading"`, `"never"` (case-insensitive) near `"real"`, and `"unreadable"`.
  - `test_setup_mentions`: `SETUP.md` contains `"SMC Scanner"`, `"Remote Control"`, `"paper_until"` and `"not financial advice"`.
- [ ] **Step 2: Run** `python -m pytest skills/smc-forex-alerts/tests/test_skill_docs.py -q` → FAIL.
- [ ] **Step 3: Write** `SKILL.md` and `SETUP.md`.
- [ ] **Step 4: Run** the full suite → all pass.
- [ ] **Step 5: Smoke run:** `python skills/smc-forex-alerts/scripts/smc.py --config skills/smc-forex-alerts/config.example.json --now 2026-11-25T12:30:00+00:00 status` → valid JSON with `"killzone": "NY"`.
- [ ] **Step 6: Commit** `feat(smc): SKILL.md run procedure and setup guide`.
