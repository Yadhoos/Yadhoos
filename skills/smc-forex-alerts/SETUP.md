# SMC forex scanner: setup on your PC

This is a one-time setup, about 20 minutes. After that, you start the loop each trading day.

> **This is not financial advice.** The scanner reads charts with fixed rules and
> can be wrong. You are responsible for every real trade you take.

## 1. Python

Install Python 3.9 or newer from python.org. On Windows, tick "Add Python to PATH".
Then, in this folder, run:

```
pip install -r requirements.txt
```

## 2. Claude Code + Claude in Chrome

1. Install Claude Code (CLI or the Claude desktop app) and sign in.
2. Install the **Claude in Chrome** extension in the Chrome profile where you're logged into TradingView.
3. In the extension's site permissions, allow **tradingview.com**, so it can read the chart. In paper mode it also clicks orders, which shouldn't wait for your approval each time.

## 3. TradingView layout "SMC Scanner"

1. In TradingView, create a **new layout** named **SMC Scanner**. Use a separate layout so the scanner never takes over the chart you work on.
2. Add the indicator **"Smart Money Concepts" by LuxAlgo** (free). Use the settings listed in `references/smc-checklist.md`, with internal and swing structure, order blocks, equal highs/lows, FVGs and premium/discount zones all turned on.
3. Open this layout in its own Chrome tab and leave it open.

## 4. Paper Trading (trial week)

1. In the trading panel at the bottom of the chart, connect **Paper Trading** (TradingView's simulated account).
2. **Disconnect any real broker from TradingView for the trial week.** The scanner checks for "Paper Trading" before every click, but this is an extra safety net.

## 5. Config

Copy `config.example.json` to `config.json` in this folder and edit it:

| Field | What to put |
|---|---|
| `mode` | `"paper"` for the trial week. Use `"alert"` to only get alerts. |
| `paper_until` | Your start date + 6 days, e.g. start 2026-11-28 → `"2026-12-04"`. After this date, the scanner switches to alerts on its own. |
| `balance`, `account_currency` | Your real account size, used for lot sizes in alert mode. |
| `symbols` | The exact TradingView symbols of **your broker's feed**, e.g. `"OANDA:XAUUSD"`, so the alert prices match what you trade. |
| `contracts` | Leave `{}` unless your broker's lot size differs (standard is 100,000 units for FX, 100 oz for gold). |
| `partials` | Leave `{}` for 50/30/20 (3 targets) or 60/40 (2 targets). |

## 6. Install the skill

Copy this whole `smc-forex-alerts` folder to `~/.claude/skills/smc-forex-alerts`.
On Windows that's `C:\Users\<you>\.claude\skills\smc-forex-alerts`.

## 7. Phone alerts

1. Install the **Claude app** on your phone and sign in with the same account.
2. In the Claude Code session that runs the scanner, turn on **Remote Control**. Phone pushes only arrive while Remote Control is connected.

## 8. Keep the PC awake

During the killzones, the PC must stay on with Chrome open. On Windows: Settings → System → Power → set "Sleep" to **Never** while plugged in.

Killzones, in New York time: London 02:00–05:00, New York 07:00–10:00.
In India time that's roughly 12:30–15:30 and 17:30–20:30. Both are an hour earlier while the US is on daylight saving time (March to November).

## 9. Start

Open Claude Code, then run:

```
/loop 15m run the smc-forex-alerts tick
```

Outside the killzones each tick does almost nothing, except managing open paper trades.

## 10. After the trial week

On the first tick after `paper_until`, the scanner writes `~/smc-alerts/paper-report.md` (trades, win rate, total R, results per pair, top SKIP reasons) and sends you a notification. From then on it only sends alerts.

## Files it keeps (in `~/smc-alerts/`)

| File | Contents |
|---|---|
| `log.jsonl` | Every check, including SKIPs with the reason |
| `alerts.jsonl` | Every alert, used to avoid duplicates |
| `trades.jsonl` | The paper trade journal |
| `shots/` | Chart screenshots for each alert |
