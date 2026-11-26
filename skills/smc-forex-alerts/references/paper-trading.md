# Paper trading: placing and managing trades

**Placing** new trades: only when `smc.py status` says `"mode": "paper"`.
**Managing** trades already in the journal: whenever `status` says
`"manage_open_trades": true`, including after the trial ends. Otherwise, never touch the trading panel.

## The guard (before EVERY order action)

Before every place, modify, cancel or close action:

1. Look at the TradingView trading panel (bottom panel) and read the connected broker's name.
2. Continue **only** if it says exactly **Paper Trading**.
3. If it shows anything else (a real broker such as OANDA, a login prompt, or nothing at all):
   - Do not click anything in the panel.
   - Run `python <skill>/scripts/smc.py notify-once --flag guard`. If `send` is true, push the `guard` message from `smc.py message --kind guard`.
   - Make **no order actions for the rest of this session**. Alerts continue as in alert mode, pushing the plan's `message_alert`, never the `PAPER placed:` `message`.

Never open broker connection dialogs, never log in or out of a broker, and never change account settings. The only clicks allowed in the panel are the order actions below, and only on Paper Trading.

## Placing a trade

Do this only after `smc.py plan` returned `ok: true`, `duplicate: false` and `pair_has_open_trade: false`.

1. Check the guard.
2. For **each leg** in `plan.legs`, place one **limit** order:
   - side BUY/SELL, quantity = `leg.lots` (convert to units if the panel asks for units: lots × contract size)
   - limit price = `plan.entry`
   - stop loss = `plan.sl`
   - take profit = `leg.tp`
3. Confirm each order appears under the panel's **Orders** tab with the right prices. If one fails, cancel the legs you already placed, log a SKIP with reason `order failed`, and stop for this pair.
4. Record it. Copy entry, sl and each leg's `lots`, `tp` and `r` from the `plan` output exactly (legs are numbered from 0 in that order):
   ```
   python <skill>/scripts/smc.py trade --json '{"trade_id":"XAUUSD-202611251230","pair":"XAUUSD","type":"placed","direction":"sell","entry":2388.0,"sl":2393.2,"legs":[{"lots":0.11,"tp":2377.6,"r":2.0},{"lots":0.05,"tp":2366.2,"r":4.2},{"lots":0.03,"tp":2350.0,"r":7.3}],"placed_at":"<ISO time>"}'
   ```
   `trade_id` = `PAIR-YYYYMMDDHHMM` in New York time.
5. Push the `message` from `smc.py plan`. It already starts with `PAPER placed:`.

## Managing open trades (every tick, also outside killzones)

Run `python <skill>/scripts/smc.py trades --open`. For each trade, open its pair in the SMC Scanner tab and check the **Positions** and **Orders** tabs:

| What you see | Do this |
|---|---|
| Entry not filled, and price has touched the SL level | Guard → cancel all its orders → `trade` event `cancelled` with `"reason":"sl touched before fill"` → push `message --kind cancelled --pair P --detail "sl touched before fill"` |
| Entry not filled, and 8 candles (2 hours) have passed since `placed_at` | Guard → cancel → `cancelled` with `"reason":"not filled in 2h"` → push the `cancelled` message |
| TP1 leg closed in profit, and no `tp1_be` event yet | Guard → change the SL of the remaining legs to `entry` → `trade` event `tp1_be` → push `message --kind tp1_be --pair P` |
| Any leg closed | `trade` event `leg_closed` with `"leg":<index>,"outcome":"tp"|"sl"|"be"` |
| All legs closed | `trade` event `closed` with `--outcomes '{"0":"tp","1":"be","2":"be"}'` (one per leg). The CLI computes `result_r`. Push `message --kind closed --pair P --detail "<+x.xR>"` |

A leg's outcome is:
- `tp` if it closed at its take-profit
- `sl` if it closed at the original stop-loss
- `be` if it closed at the breakeven stop (entry)

## Never

- Never place a second trade on a pair with an open or pending trade from this skill.
- Never trade when the guard fails, and never on a real-money account, in any mode.
- Never move a stop-loss further away, add to a position, or change take-profits after placing, other than the breakeven move above.
