# MCX gold relative pricing

Hack in Hills '26, problem statement 3: Commodity Derivatives Intelligence.

MCX lists gold in five contract sizes (GOLD, GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL), each quoted per a different weight. This tool converts every contract to rupees per gram, compares each one to a fair value built from COMEX gold, USDINR, import duty and carry, and labels what it finds with plain text tags.

**Status: prototype.** It runs on seeded synthetic data. The prices are not real MCX prices.

## Run it

Needs Python 3.11 or newer.

```
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

To keep the data in a file instead of regenerating it each start:

```
GOLD_DB=data/gold.db uvicorn app.main:app        # Windows PowerShell: $env:GOLD_DB="data/gold.db"
```

## Pages

| URL | What it returns |
|---|---|
| `/` | The table: per-gram price, fair value, distance from fair, premium over GOLD, tags, reason |
| `/?date=YYYY-MM-DD` | The same table for an earlier session (weekdays within the last 60 sessions) |
| `/tags.txt` | One line per row: `date symbol expiry [TAGS] reason` |
| `/api/rows` | The same rows as JSON |

All three accept `?date=`. An unknown date returns 404 with the available range.

## How it works

- **Per gram:** quoted price divided by the quote weight (10 g for GOLD, GOLDM and GOLDTEN; 8 g for GOLDGUINEA; 1 g for GOLDPETAL).
- **Fair value per gram:** COMEX USD per ounce x USDINR / 31.1035 x (1 + duty) x (1 + carry x days to expiry / 365).
- **Distance from fair:** contract per gram divided by fair, minus 1, in percent.
- **Over GOLD:** each contract's per-gram premium over GOLD at the same expiry.
- **z-scores:** compared with the previous 20 sessions of the same contract. Needs at least 10 sessions.

## Tags

| Tag | Meaning |
|---|---|
| `[RICH]` | Priced above fair by more than `rich_pct` |
| `[CHEAP]` | Priced below fair by more than `cheap_pct` |
| `[WIDE]` | Gap to GOLD is unusually large (z above `z_limit`) |
| `[TIGHT]` | Gap to GOLD is unusually small (z below minus `z_limit`) |
| `[CONTANGO]` | Later expiry costs more than the previous one |
| `[BACKWARDATION]` | Later expiry costs less than the previous one |
| `[ROLL]` | Within `roll_days` of expiry |
| `[THIN]` | Volume below `min_volume`, so treat the signal with care |
| `[OK]` | None of the above |

## Configuration

Edit `config.toml` and restart the server.

| Key | Default | Meaning |
|---|---|---|
| `duty_pct` | 0.06 | Import duty as a fraction |
| `carry_pct` | 0.06 | Annual cost of carry as a fraction |
| `rich_pct` / `cheap_pct` | 0.5 | Tag thresholds in percent |
| `z_window` | 20 | Sessions used for z-scores |
| `z_limit` | 2.0 | z-score threshold for `[WIDE]` and `[TIGHT]` |
| `roll_days` | 5 | Days before expiry that count as `[ROLL]` |
| `min_volume` | 50 | Below this, a row is `[THIN]` |

## Project layout

```
app/
  specs.py      lot and quote sizes per contract
  schema.sql    SQLite schema
  data.py       connection, setup, synthetic data
  parity.py     per-gram, fair value, distance, z-scores
  tags.py       tag rules
  main.py       FastAPI app and the HTML table
tests/
config.toml
```

## Data model

SQLite with strict types. Prices are whole numbers in minor units (paise, US cents, USDINR x 10000). Every column is NOT NULL, references are foreign keys with explicit ON DELETE, and a trigger rejects a quote dated after its contract's expiry.

## Tests

```
python -m pytest -q
```

## Known limits

- Synthetic data only. There is no loader for real MCX, COMEX or USDINR data yet.
- Lot sizes, quote weights and the 6% duty default are from memory. Check them against the MCX contract specification before trusting any number.
- The synthetic generator injects one mispricing (GOLDPETAL, nearest month) on the last session so the tags have something to find.
