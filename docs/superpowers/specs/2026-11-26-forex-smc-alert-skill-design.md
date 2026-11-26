# SMC Forex Alert Skill — Design

Date: 2026-11-26
Status: Approved by user 2026-11-26

## Intent

The user trades forex with Smart Money Concepts (SMC) and doesn't want to watch
charts all day. They want a Claude Code skill that watches their own TradingView
charts in Chrome on their PC and **alerts them only when a valid setup appears**
(BUY or SELL). Most checks end in SKIP, and SKIP stays silent.

Two modes:

- **`paper` (first week):** Claude places and manages trades **on its own,
  without asking**, on TradingView's **Paper Trading** account (simulated money).
  The user wants a one-week trial to see whether the rules are worth trusting.
- **`alert` (default after the trial):** Claude only notifies. The user decides
  whether and how to trade.

Claude **never** trades a real-money account in any mode.

## Goals

- Watch **EURUSD, GBPUSD and XAUUSD** on **4H** (bias and range) and **15m** (trigger and entry).
- Apply one fixed SMC checklist the same way every time and alert only when **all** criteria pass.
- Deliver alerts as a **Claude app push notification** to the user's phone.
- Avoid duplicate alerts for the same setup, and keep a reviewable log of every check.
- Run unattended in a loop during the London and New York killzones.

## Non-goals

- Placing, modifying or closing orders on any real-money broker, in any mode.
- Any order activity in `alert` mode.
- Backtesting or performance statistics.
- Pairs or timeframes beyond the three pairs on 4H and 15m. The builder may make the pair list configurable but doesn't have to.
- Working while the PC is off. The PC, Chrome and Claude Code must be running.

## Anti-goals (it has failed if...)

- It alerts on setups that don't meet every criterion. Noisy alerts destroy trust.
- It clicks any order control while the trading panel shows anything other than **Paper Trading** (a real broker), or in `alert` mode.
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
- Risk 1% per trade with lot size calculated; targets 2R–10R with partial-profit suggestions (50/30/20 split approved).
- One-week `paper` mode: Claude auto-trades on TradingView Paper Trading without asking, then falls back to `alert` mode.
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

## Risk and targets (user's decision, details proposed)

- **Risk per trade: 1% of account balance.** The skill reads `balance` and
  `account_currency` from its config file, which the user keeps up to date.
  Lot size = (balance × 1%) ÷ (stop distance × value per pip/point per lot),
  rounded **down** to 0.01 lots. Pip values come from per-symbol contract specs
  in config (default: FX 100,000 units/lot; XAUUSD 100 oz/lot), with the
  quote→account currency conversion read from the live chart price. The alert
  says "check your broker's contract size" in the setup guide.
- **Targets from 2R up to 10R:** TP1 is the nearest opposing liquidity and must
  be ≥ 2R (gate above). TP2 and TP3 are the next opposing liquidity levels
  (15m, then 4H) beyond TP1, kept only if ≤ 10R. Any level beyond 10R is
  capped at 10R. If no further level exists, only TP1 is shown.
- **Suggested partials (proposal):** close 50% at TP1 and move SL to
  breakeven. Close 30% at TP2. Let the last 20% run to TP3 (or TP2 if only
  two targets). With one target only: close 100% at TP1. The split lives in
  config so the user can change it.

**Ambiguity rule:** if any item can't be read with confidence from the
chart (labels overlapping, chart not loaded, indicator missing), the result is
**SKIP**, recorded with reason "unreadable". It never guesses toward an alert.

## Paper-trading mode (user's decision)

- **Switch:** `mode` in config: `paper` or `alert`, plus `paper_until` (a date
  one week after start). After that date the skill behaves as `alert` mode
  without being told.
- **Real-money guard:** immediately before every order action (place, modify,
  cancel, close), confirm the TradingView trading panel is connected to
  **Paper Trading**. If not, take no action, send one notification, and pause
  trading for the session (alerts continue). SETUP.md recommends disconnecting
  any real broker from TradingView during the trial.
- **Placing:** on a valid setup, place **3 limit orders** at the entry price,
  all with the same SL, and TP1/TP2/TP3 respectively, sized 50% / 30% / 20% of
  the 1%-risk position (rounded down, minimum 0.01 lots). Lot sizes use the
  paper account's balance read from the panel. If there's only one or two
  targets, the split is 100%, or 60%/40% (proposal).
- **Managing (every tick, also outside killzones):**
  - When TP1 has filled, move the SL of the remaining orders to the entry
    price (breakeven).
  - Cancel unfilled entry orders if price touches the SL level first, or after
    8 15m candles (2 hours) without a fill.
- **De-duplication:** don't open a second trade on a pair that already has an
  open position or pending orders from the skill.
- **Notifications (≤ 200 chars each):** trade placed, TP1 hit + SL to
  breakeven, trade fully closed (with result in R), entry cancelled, guard
  triggered.
- **Trade journal:** every trade's levels, fills, management actions and
  final R go into `~/smc-alerts/trades.jsonl`.
- **End-of-week report:** on the first tick after `paper_until`, write
  `~/smc-alerts/paper-report.md` (trades, win rate, total R, per-pair results,
  notable failures) and send a notification pointing to it.
- **Limits:** management only happens while the PC, Chrome and loop are
  running. Resting SL/TP orders still protect positions if the PC sleeps.
  Claude in Chrome may need TradingView allowed so order clicks don't wait for
  confirmation, which SETUP.md covers.

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
   one `PushNotification` (≤ 200 chars), e.g.
   `XAUUSD SELL 2388.0 SL 2393.2 0.19lot(1%) TP1 2377.6(2R) TP2 2366.2(4.2R) TP3 2350.0(7.3R) NY`.
   The full write-up in the session also gives the partial-profit plan.
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
