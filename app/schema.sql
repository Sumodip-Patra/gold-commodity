CREATE TABLE contract (
  symbol      text PRIMARY KEY CHECK (symbol IN ('GOLD','GOLDM','GOLDTEN','GOLDGUINEA','GOLDPETAL')),
  lot_grams   integer NOT NULL CHECK (lot_grams > 0),
  quote_grams integer NOT NULL CHECK (quote_grams > 0)
) STRICT;

CREATE TABLE series (
  id     integer PRIMARY KEY,
  symbol text NOT NULL REFERENCES contract(symbol) ON DELETE RESTRICT,
  expiry text NOT NULL CHECK (expiry GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  UNIQUE (symbol, expiry)
) STRICT;

-- Reference prices in minor units: US cents per ounce, and USDINR times 10000.
CREATE TABLE reference (
  session_date       text PRIMARY KEY CHECK (session_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  comex_cents_per_oz integer NOT NULL CHECK (comex_cents_per_oz > 0),
  usdinr_e4          integer NOT NULL CHECK (usdinr_e4 > 0),
  source             text NOT NULL CHECK (source IN ('synthetic','csv'))
) STRICT;

-- settle_paise is the quoted price in paise for quote_grams of gold.
CREATE TABLE quote (
  series_id    integer NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  session_date text NOT NULL REFERENCES reference(session_date) ON DELETE RESTRICT,
  settle_paise integer NOT NULL CHECK (settle_paise > 0),
  volume       integer NOT NULL CHECK (volume >= 0),
  created_at   text NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (series_id, session_date)
) STRICT, WITHOUT ROWID;

CREATE INDEX quote_by_date ON quote(session_date);

CREATE TRIGGER quote_not_after_expiry BEFORE INSERT ON quote
WHEN NEW.session_date > (SELECT expiry FROM series WHERE id = NEW.series_id)
BEGIN
  SELECT RAISE(ABORT, 'quote dated after contract expiry');
END;
