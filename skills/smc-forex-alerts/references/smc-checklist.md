# SMC checklist: how to read the chart

Read this before evaluating a pair. Every item must pass for BUY or SELL.
If you can't read an item with confidence (labels overlap, chart still loading,
indicator hidden, price axis unreadable), the result is **SKIP** with reason
`unreadable`. Never guess toward an alert.

## Indicator: LuxAlgo "Smart Money Concepts"

Expected settings on the "SMC Scanner" layout (the user sets these once, see SETUP.md):

| Setting | Value |
|---|---|
| Mode | Historical |
| Internal Structure (BOS/CHoCH) | On, labels shown |
| Swing Structure (BOS/CHoCH) | On, labels shown, default length (50) |
| Internal Order Blocks | On |
| Swing Order Blocks | On |
| Equal Highs/Lows | On |
| Fair Value Gaps | On (auto threshold) |
| Premium/Discount Zones | On |

If these look different from the screenshot (e.g. no swing labels at all), SKIP
with `unreadable` and mention it in the session write-up.

**Which labels count:**
- **4H uses swing structure labels** (the larger BOS/CHoCH labels).
- **15m uses internal structure labels** (the smaller, dashed BOS/CHoCH labels).

## Items

### 1. 4H bias (4H, swing labels)
- **Bullish:** the most recent swing label is a bullish **BOS**, and the swings form higher highs and higher lows.
- **Bearish:** the most recent swing label is a bearish **BOS**, and the swings form lower highs and lower lows.
- **Fail:** the most recent swing label is a **CHoCH** against the previous trend (a fresh opposing CHoCH), or the structure is mixed.
- Only take BUYs with a bullish bias and SELLs with a bearish bias.

### 2. Premium / discount (4H)
- Use the indicator's Premium/Discount zones for the current 4H dealing range (between the latest swing high and low).
- **BUY:** price is below the 50% equilibrium line (discount).
- **SELL:** price is above it (premium).
- Exactly at equilibrium counts as a fail.

### 3. Liquidity sweep (15m)
- Look at the **last 12 candles on 15m** (about 3 hours).
- **BUY:** a wick went **below** a recent swing low or an EQL (equal lows) line, then price closed back above it.
- **SELL:** a wick went **above** a recent swing high or EQH line, then price closed back below it.
- Note the sweep's extreme wick price. It sets the stop-loss.

### 4. CHoCH (15m, internal labels)
- **After** the sweep candle, there is an **internal CHoCH** label in the direction of the 4H bias.
- If the CHoCH came before the sweep, or points the other way, the item fails.

### 5. Entry zone (15m)
- The impulse that made the CHoCH left a **fresh** order block or FVG. Fresh means price hasn't traded back through it yet. The indicator removes or greys out mitigated zones.
- Price is **inside the zone, or within 25% of the stop distance** from its near edge.
- If an OB and an FVG overlap, note "OB+FVG" (stronger), but one of them is enough.

### 6. Risk-to-reward (the CLI decides)
Gather the numbers and let `smc.py plan` decide. Don't do this math yourself.

- **entry** = the near edge of the zone: the top of a bullish zone for BUY, the bottom of a bearish zone for SELL.
- **sl** = beyond the sweep's extreme wick, plus a buffer: **FX 2 pips (0.0002), XAUUSD 0.5**.
- **levels** = every visible opposing liquidity price on 15m **and** 4H, meaning swing highs/lows and EQH/EQL lines on the profit side. Include them all; the CLI picks the nearest and caps at 10R.
- Read prices from the price axis or label tooltips with the instrument's precision (FX 5 decimals, gold 2).

Then run:

```
python <skill>/scripts/smc.py plan --pair XAUUSD --direction sell --entry 2388.0 --sl 2393.2 --levels 2377.6 2366.2 2350.0
```

- If `ok` is false, SKIP with the returned `reason` (e.g. `rr below 2 (1.40)`, `position too small`).

## Session write-up (only for BUY or SELL)

Post this in the session. The phone only gets the one-line `message`.

```
🟢/🔴 PAIR — BUY/SELL  (London|NY killzone, HH:MM New York)

✅ 4H bias: <swing BOS details>
✅ Discount/Premium: <where price is in the range>
✅ Sweep: <what was taken, price, time>
✅ CHoCH: <internal CHoCH price, time>
✅ Entry: <OB / FVG / OB+FVG zone prices>
✅ R:R: entry <e> SL <sl> → TP1 <p> (xR), TP2 <p> (xR), TP3 <p> (xR)

Size: <total lots> lots for 1% risk (<risk amount> <currency>)
Plan: close legs at TP1 / TP2 / TP3 (<lots per leg>), move SL to breakeven after TP1.
Screenshots: <paths of the 4H and 15m shots>
```

For SKIP, log the first failing item as `reason` (e.g. `no 15m sweep`) and don't post a write-up.
