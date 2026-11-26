# SMC Forex Alert Skill — Design

Date: 2026-11-26
Status: Awaiting user approval

## Intent

The user trades forex with Smart Money Concepts (SMC) and doesn't want to watch
charts all day. They want a Claude Code skill that watches their own TradingView
charts in Chrome on their PC and **alerts them only when a valid setup appears**
(BUY or SELL). Most checks end in SKIP, and SKIP stays silent.

Claude **never places trades**. It reads charts and notifies. The user decides
whether and how to trade.

## Goals

- Watch **EURUSD, GBPUSD and XAUUSD** on **4H** (bias and range) and **15m** (trigger and entry).
- Apply one fixed SMC checklist the same way every time and alert only when **all** criteria pass.
- Deliver alerts as a **Claude app push notification** to the user's phone.
- Avoid duplicate alerts for the same setup, and keep a reviewable log of every check.
- Run unattended in a loop during the London and New York killzones.

## Non-goals

- Placing, modifying or closing orders on any broker or on TradingView.
- Backtesting or performance statistics.
- Pairs or timeframes beyond the three pairs on 4H and 15m. The builder may make the pair list configurable but doesn't have to.
- Working while the PC is off. The PC, Chrome and Claude Code must be running.

## Anti-goals (it has failed if...)

- It alerts on setups that don't meet every criterion. Noisy alerts destroy trust.
- It interacts with any order or trade button in TradingView. It must never click Buy, Sell or Trade, or open the trading panel.
- It changes the user's chart drawings, indicators or saved layout, beyond switching symbol and timeframe.
- It sends a notification for SKIP results or routine status.

## Constraints

- **Runtime:** Claude Code (CLI or desktop app) on the user's PC, with the
  **Claude in Chrome** extension controlling the user's real Chrome, where
  TradingView is already logged in. This cloud session can't run it. The skill
  is built and pushed here, then installed on the PC.
- **Chart reading:** done from screenshots and page text via Claude in Chrome.
- **Indicator:** the user adds LuxAlgo's free **"Smart Money Concepts"**
  indicator to their TradingView chart layout. Claude reads its labels and zones
  (BOS, CHoCH, order blocks, FVGs, equal highs/lows, premium/discount zones)
  instead of inferring structure from raw candles.
- **Notification:** Claude Code's `PushNotification` tool. It sends a desktop
  notification and also pushes to the phone **when Remote Control is
  connected**. The message must be one line under 200 characters with no
  markdown. The tool may skip sending if the user is active at the terminal,
  which is acceptable.
- **Scheduling:** Claude Code's `/loop` with a fixed interval, kept in a
  long-running session.

## Approaches considered

1. **Claude reads raw candles by eye.** No chart setup needed, but swing,
   order-block and FVG detection from screenshots is inconsistent between runs,
   which leads to noisy or missed alerts. Rejected.
2. **Claude reads a chart already labeled by an SMC indicator.** *(Chosen by the user.)*
   The indicator applies the same structural definitions every time, and Claude
   judges confluence against the checklist, killzone and R:R. Costs a one-time
   indicator setup and means trusting LuxAlgo's definitions.
3. **Python computes SMC from an OHLC data API.** The most precise option, but
   it doesn't read the user's TradingView chart, needs a separate (often paid
   for gold) data feed, and is much more to build. Rejected.

## What the user decided

- Strategy: SMC, with **all criteria required** (including the killzone filter).
- Pairs: EURUSD, GBPUSD, XAUUSD. Timeframes: 4H and 15m.
- Alert channel: Claude app push (option B).
- Chart reading: approach 2 (LuxAlgo SMC indicator).
- Labels: swing structure on 4H, internal structure on 15m.
- R:R: strict, measured to the nearest opposing liquidity.
- Claude only notifies. It never trades.

## The checklist (every item must pass, or the result is SKIP)

For each pair, every run:

0. **Killzone:** current time is in the London killzone **02:00–05:00 New York
   time** or the New York killzone **07:00–10:00 New York time**. Times are
   defined in America/New_York so DST is handled automatically, and the skill
   converts them from the PC's clock. Outside these windows the run does
   nothing (no chart reads).
**Which labels count (user's decision):** 4H rules use LuxAlgo **swing**
structure labels. 15m rules use **internal** structure labels. SETUP.md pins
the indicator settings (swing length, internal structure on, OB and FVG
filters) so the labels are the same every run.

1. **4H bias:** the most recent 4H **swing** structure label is a BOS in one direction,
   with structure consistent with it (bullish = higher highs and higher lows,
   bearish = the reverse). If the bias is unclear or there's a fresh opposing
   4H swing CHoCH, SKIP.
2. **Premium/discount (4H range):** for BUY, price is in the discount half
   (below 50%) of the current 4H dealing range. For SELL, price is in the
   premium half.
3. **Liquidity sweep (15m):** within the last ~12 15m candles (about 3 hours),
   price took out a recent swing low or equal lows (BUY) or a swing high or
   equal highs (SELL), against the bias direction.
4. **CHoCH (15m):** after that sweep, a 15m **internal** CHoCH formed in the direction of
   the 4H bias.
5. **Entry zone (15m):** a fresh (unmitigated) order block or FVG created by
   the CHoCH move, with price currently inside it or within a small distance of
   it. An OB and FVG overlapping is noted as stronger confluence but isn't
   required.
6. **Risk-to-reward ≥ 1:2:** entry = the zone's proximal edge, stop-loss =
   beyond the swept high or low (plus a small buffer), target = the
   **nearest** opposing liquidity (swing high/low or equal highs/lows) on
   either timeframe. That nearest level alone must give ≥ 1:2. A further level
   with better R:R doesn't rescue the setup (user's decision: strict).
   R:R = (target − entry) / (entry − stop), with signs flipped for SELL.

**Ambiguity rule:** if any item can't be read with confidence from the
chart (labels overlapping, chart not loaded, indicator missing), the result is
**SKIP**, recorded with reason "unreadable". It never guesses toward an alert.

## Run flow (each loop tick)

1. Check the killzone. If outside, log nothing and end the tick.
2. Find the dedicated scanner tab (a separate TradingView layout named
   "SMC Scanner", see Setup). Confirm the user is logged in and the SMC
   indicator is visible. If not, skip this tick and retry on the next one.
   Send **one** "setup problem" notification per session (not per tick), and
   keep the loop running so a slow page load doesn't lose the killzone.
   *(Builder's call.)*
3. For each pair: set symbol (using the exact symbols from config, e.g.
   `OANDA:XAUUSD`), set 4H, wait for the chart to load, read it and
   take a screenshot. Then set 15m, wait, read it and take a screenshot.
4. Evaluate the checklist and produce BUY / SELL / SKIP with a reason per item.
5. **De-duplication:** a setup is identified by pair + direction + entry zone
   (rounded). If the same setup was alerted in the last 24 hours, don't alert
   again.
6. For each new BUY/SELL: save the screenshots, write the log entry, and send
   one `PushNotification`, e.g.
   `XAUUSD SELL 2387.5-2389.0 SL 2393.2 TP 2371.0 RR 1:2.9 (NY KZ) - see log`.
7. Append every result (including SKIP) to the log.

## Cadence

Run `/loop 15m` started by the user. Each tick does its work only inside the
killzones, ideally reading just after a 15m candle closes. Aligning the tick
to candle close is left to the builder (e.g. a short wait to the next :00/:15/
:30/:45 + ~1 min).

## Files and log (builder may adjust names)

```
skills/smc-forex-alerts/
  SKILL.md              # the instructions Claude follows each run (checklist above)
  SETUP.md              # one-time setup: extension, indicator, Remote Control, starting the loop
  references/smc-checklist.md   # detailed reading guide for the LuxAlgo labels
```

Runtime data on the user's PC, outside the repo:
`~/smc-alerts/log.jsonl` (one line per pair per tick: time, pair, result,
per-item reasons, levels) and `~/smc-alerts/shots/` (screenshots for alerts).

## Setup the user does once (documented in SETUP.md)

1. Install Claude Code and the Claude in Chrome extension on the PC.
2. In TradingView, create a **separate layout named "SMC Scanner"** and open it
   in its own Chrome tab. The skill only ever drives this layout, so the user's
   own working chart is never taken over. *(Builder's call.)* On it, add LuxAlgo "Smart Money Concepts" to the chart layout with
   swing and internal structure, order blocks, FVGs, equal highs/lows and
   premium/discount zones turned on.
3. Install the skill into `~/.claude/skills/`, and set the three symbols in its
   config to match the user's broker feed (e.g. `OANDA:EURUSD`), so alert
   levels match the prices they trade on. *(Builder's call: default to whatever
   prefix their chart shows.)*
4. Connect Remote Control and have the Claude app on the phone, so push
   notifications reach it.
5. Start a Claude Code session and run `/loop 15m` with the skill's run command.

## Left to the builder

- Exact wording of SKILL.md and how to describe reading LuxAlgo labels.
- Exact buffer sizes for SL and "near the zone", per instrument (gold vs. FX pips).
- How the chart is switched (URL parameters vs. the symbol search box), as long
  as nothing touches trading controls.
- Log format details.
- Verifying in this cloud container: the skill can be checked for structure
  and consistency here. A real end-to-end run happens on the user's PC.

## Disclaimer

Alerts are not financial advice. The user is responsible for any trade.
SETUP.md says this plainly.
