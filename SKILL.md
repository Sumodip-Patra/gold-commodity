---
name: mcx-gold-relative-pricing
description: Use when building or changing the MCX gold futures relative-pricing tool for Hack in Hills 26 PS3, or when a task mentions GOLD, GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL, per-gram comparison, basis against COMEX, or text tag signals.
---

# MCX Gold Relative Pricing

Goal: compare all MCX gold contracts on one common basis, flag where they are priced out of line, and label each finding with a plain text tag.

## Rules for the agent

- Python 3.11, pandas, numpy, FastAPI. Free data only. No paid APIs, no API keys.
- UI is one server-rendered HTML table. System fonts, flat colors, no gradients, blur, glass effects, shadows, animations, or UI libraries.
- Write only what is needed. No placeholder files, no unused abstractions, no comments that restate code.
- Every number shown must come from a function with a test.
- Verify contract specs (lot size, quote unit) against the MCX contract specification page before hardcoding. Treat the table below as a starting point.

## Layout

```
app/
  specs.py       contract specs
  data.py        loaders (bhavcopy CSV, yfinance, synthetic)
  normalize.py   per-gram conversion
  parity.py      fair value and spreads
  tags.py        text tag rules
  main.py        FastAPI + one HTML table
tests/
data/            cached CSVs
```

## specs.py

One dict per contract: `symbol, lot_grams, quote_grams`.

| symbol | lot_grams | quote_grams |
|---|---|---|
| GOLD | 1000 | 10 |
| GOLDM | 100 | 10 |
| GOLDTEN | 10 | 10 |
| GOLDGUINEA | 8 | 8 |
| GOLDPETAL | 1 | 1 |

## normalize.py

`per_gram = quoted_price / quote_grams`. All comparisons use per-gram. Never compare raw quotes.

## data.py (free sources, tried in order)

1. MCX daily bhavcopy CSV downloaded by hand into `data/`. Parse by symbol and expiry.
2. `yfinance`: `GC=F` (COMEX gold, USD/oz) and `USDINR=X` for the global reference.
3. `synthetic()`: generates realistic prices with injected mispricings, so the demo works offline and tests are deterministic. Seeded.

## parity.py

- `fair_per_gram = GC_usd_per_oz * usdinr / 31.1035 * (1 + duty_pct)`, then `* (1 + carry_pct * days_to_expiry / 365)` so far months are not falsely tagged `[RICH]`. Both are config values (defaults 0.06), editable.
- `basis = contract_per_gram - fair_per_gram`
- `cross_spread(a, b) = per_gram(a) - per_gram(b)` for every contract pair at the same expiry.
- `calendar_spread` = near expiry vs next expiry, per gram, annualized by days between expiries.
- `z = (spread - rolling_mean) / rolling_std` over a 20-session window.

## tags.py (plain text tags)

A tag is an uppercase word in square brackets, attached to each row. Rules are thresholds on `z` and `basis`, kept in one config dict.

| tag | condition |
|---|---|
| `[RICH]` | contract per-gram above fair by more than rich_pct |
| `[CHEAP]` | below fair by more than cheap_pct |
| `[WIDE]` | cross spread z > 2 |
| `[TIGHT]` | cross spread z < -2 |
| `[CONTANGO]` / `[BACKWARDATION]` | sign of calendar spread |
| `[ROLL]` | within 5 days of expiry |
| `[THIN]` | volume below the low-volume threshold, so the signal is unreliable |
| `[OK]` | none of the above |

Each row also gets one `why` string built from the numbers, for example: `GOLDPETAL 0.31% above per-gram fair, z=2.4`.

## Unique features (build in this order)

1. **Per-gram ladder**: one table sorted by per-gram price across all contracts and expiries.
2. **Parity gap**: basis against the COMEX x USDINR reference, with editable duty.
3. **Odd-lot premium**: spread of GOLDGUINEA and GOLDPETAL over GOLD per gram, since small lots usually carry a premium. Report the premium in percent.
4. **Replay mode**: `?date=YYYY-MM-DD` re-runs tags on a past session from cached data.
5. **Tag export**: `/tags.txt` returns one line per row: `DATE SYMBOL EXPIRY [TAG] why`. Greppable, no JSON needed.

## main.py

- `GET /` renders the table: symbol, expiry, per-gram, fair, basis, z, tags, why.
- `GET /tags.txt` plain text.
- `GET /api/rows` JSON, same rows.
- Config in `config.toml`: duty, thresholds, window.

## Schema (SQLite, STRICT tables)

See `app/schema.sql`. Money and FX are integers in minor units (paise, US cents, USDINR x 10000). Every column is NOT NULL, every reference is a FOREIGN KEY with an explicit ON DELETE, no soft delete, and a trigger rejects quotes dated after expiry.

## Design tokens

Paper #e9eef1, ink #16222d, rule #aebbc5, rich #9c2a2a, cheap #1c5c99, brass #8c6d1f (fair-value line only). One system font family, tabular numbers, sentence-case labels. The diverging bar beside each row is the only graphic.

## Tests

- Normalization: each symbol converts to the expected per-gram value.
- Parity: known inputs give a known basis.
- Tags: each rule fires on a crafted row and `[OK]` otherwise.
- Synthetic data with an injected 1% mispricing produces `[RICH]` or `[CHEAP]` on exactly that row.

## Done when

`uvicorn app.main:app` shows the table from synthetic data with no network, switches to live data when files or network exist, and `pytest` passes.
