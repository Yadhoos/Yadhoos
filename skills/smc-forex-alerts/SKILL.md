---
name: smc-forex-alerts
description: Runs one tick of the SMC forex scanner. Reads the user's TradingView "SMC Scanner" layout in Chrome (EURUSD, GBPUSD, XAUUSD on 4H + 15m), applies the Smart Money Concepts checklist, and either pushes a BUY/SELL alert or, in paper mode, places and manages trades on TradingView Paper Trading. Use when asked to run the SMC scan, the forex scanner tick, or the smc-forex-alerts loop.
---

# SMC forex scanner: one tick

`<skill>` below means this skill's folder (e.g. `~/.claude/skills/smc-forex-alerts`).
Every helper call is `python <skill>/scripts/smc.py <command>`, and each prints one JSON object.
Do all time, mode, R:R, lot-size and message work with the helper. Never do that math yourself.
Run helper commands with the Bash tool (on Windows, Claude Code's Bash tool is Git Bash, so the single-quoted
`--json '...'` examples work as written). If quoting is ever a problem, write the JSON to a file and pass `--json @path/to/file.json`.

## Hard rules

1. **Never trade a real-money account**, in any mode. Order actions happen only when `status` says `"mode": "paper"` **and** the trading panel shows **Paper Trading** (see `references/paper-trading.md`).
2. In alert mode, never click Buy, Sell, Trade or anything in the trading panel.
3. Don't change the user's drawings, indicators or layouts. Only switch symbol and timeframe, and only in the **SMC Scanner** tab.
4. Alert only when **every** checklist item passes. Anything you can't read with confidence → SKIP with reason `unreadable`. Never guess toward an alert.
5. Never notify for SKIP or for routine progress. Notifications use the `PushNotification` tool with the helper's `message` text **verbatim**.
6. **If the helper returns `{"error": ...}`**, never place or change orders on the strength of that step. Run `smc.py notify-once --flag helper_error`, and if `send` is true push `smc.py message --kind setup_problem --detail "helper error: <short error>"`. Then end the tick. If the error came from recording a trade you already placed, say so in the session, because the trade must be recorded by hand.

## Tick procedure

1. **Status.** Run `python <skill>/scripts/smc.py status`.
2. **Weekly report.** If `report_due` is true, run `python <skill>/scripts/smc.py report` and push its `message`.
3. **Manage paper trades.** If `manage_open_trades` is true, run `python <skill>/scripts/smc.py trades --open` and manage those trades per `references/paper-trading.md`, **whatever the mode**. Trades still open when the trial ends keep being managed (guard first), but no new orders are placed once `mode` is `alert`. Do this even outside killzones.
4. **Killzone gate.** If `killzone` is null, end the tick quietly.
5. **Find the chart.** In Chrome (Claude in Chrome), find the tab with the TradingView layout **SMC Scanner**. Check that the user is logged in and the LuxAlgo Smart Money Concepts indicator is drawn. If anything is wrong:
   - run `python <skill>/scripts/smc.py notify-once --flag setup_problem`
   - if `send` is true, push `python <skill>/scripts/smc.py message --kind setup_problem --detail "<what is wrong>"`
   - end the tick, and try again next tick.
6. **Scan each pair** (the symbols come from `status.symbols`, e.g. `OANDA:XAUUSD`):
   1. Switch to the pair on **4H**, wait until the candles and indicator have loaded, and take a screenshot.
   2. Switch to **15m**, wait until loaded, and take a screenshot.
   3. Evaluate items 1–6 in `references/smc-checklist.md`. The first failed item gives the SKIP reason.
7. **On BUY or SELL**, run `python <skill>/scripts/smc.py plan --pair P --direction buy|sell --entry E --sl S --levels L1 L2 ...`.
   - **Paper mode:** add `--balance <balance shown in the Paper Trading panel> --balance-currency USD`.
   - **Account not in USD** (alert mode, `account_currency` in config isn't USD): the helper will refuse without `--quote-to-account <rate>`, the price of 1 USD in the account currency. Read it from the chart: switch the SMC Scanner tab to e.g. `FX_IDC:USDINR`, read the last price, then switch back. Never guess the rate.
   - `ok` false → SKIP with `reason`.
   - `duplicate` true → already alerted in the last 24h. Log it with result SKIP and reason `duplicate`.
   - In paper mode, `pair_has_open_trade` true → log SKIP with reason `open trade on pair`.
   - Otherwise:
     1. If your screenshot tool can save files, save the two screenshots to `<data_dir>/shots/` as `<PAIR>-<YYYYMMDDHHMM>-4h.png` and `-15m.png`. Otherwise keep them in the session write-up.
     2. Run `python <skill>/scripts/smc.py record-alert --key <key> --json '<plan JSON>'`.
     3. **Alert mode:** push `message` and post the write-up from the checklist guide in the session.
     4. **Paper mode:** place the orders per `references/paper-trading.md` (guard first), then push `message` and post the write-up. If the guard failed or the trading pause is on, place nothing and push `message_alert` instead. It doesn't claim an order was placed.
8. **Log every pair**, every killzone tick:
   ```
   python <skill>/scripts/smc.py log-check --json '{"pair":"EURUSD","result":"SKIP","reason":"no 15m sweep","items":{"bias":"bullish","zone":"discount","sweep":false}}'
   ```
   `result` is `BUY`, `SELL` or `SKIP`.
9. End the tick with one short line in the session, e.g. `07:45 NY: EURUSD SKIP (no sweep), GBPUSD SKIP (premium), XAUUSD SELL alerted`.

## Starting the loop

The user starts it in a Claude Code session on their PC:

```
/loop 15m run the smc-forex-alerts tick
```

Ticks should land just after a 15m candle closes. `status.next_tick_s` gives the seconds until the next candle close plus one minute, if you need to align.
