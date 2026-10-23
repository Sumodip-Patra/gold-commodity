import pandas as pd

from .specs import OZ
from .tags import label

SQL = """
SELECT q.session_date AS d, s.symbol, s.expiry, q.settle_paise, q.volume,
       r.comex_cents_per_oz, r.usdinr_e4, c.quote_grams, r.source
FROM quote q
JOIN series s ON s.id = q.series_id
JOIN contract c ON c.symbol = s.symbol
JOIN reference r ON r.session_date = q.session_date
ORDER BY q.session_date"""


def frame(con):
    return pd.read_sql_query(SQL, con)


def analyse(df, cfg, date):
    """Rows for one session, sorted by per-gram price, with fair value, basis, z-scores and tags."""
    df = df[df.d <= date].copy()
    df["pg"] = df.settle_paise / 100 / df.quote_grams
    df["days"] = (pd.to_datetime(df.expiry) - pd.to_datetime(df.d)).dt.days
    spot = df.comex_cents_per_oz / 100 * df.usdinr_e4 / 1e4 / OZ * (1 + cfg["duty_pct"])
    df["fair"] = spot * (1 + cfg["carry_pct"] * df.days / 365)
    df["basis_pct"] = (df.pg / df.fair - 1) * 100

    gold = df[df.symbol == "GOLD"].set_index(["d", "expiry"]).pg
    df["gold_pg"] = gold.reindex(pd.MultiIndex.from_frame(df[["d", "expiry"]])).to_numpy()
    not_gold = df.symbol != "GOLD"
    df["cross"] = (df.pg - df.gold_pg).where(not_gold)
    df["premium_pct"] = ((df.pg / df.gold_pg - 1) * 100).where(not_gold)

    def z(s):
        past = s.shift(1).rolling(cfg["z_window"], min_periods=10)
        return (s - past.mean()) / past.std()

    g = df.groupby(["symbol", "expiry"])
    df["z_basis"] = g.basis_pct.transform(z)
    df["z_cross"] = g.cross.transform(z)

    day = df[df.d == date].sort_values(["symbol", "expiry"]).copy()
    prev = day.groupby("symbol")[["pg", "days"]].shift(1)
    day["cal_ann_pct"] = (day.pg / prev.pg - 1) * 365 / (day.days - prev.days) * 100
    out = day.apply(lambda r: label(r, cfg), axis=1, result_type="expand")
    day["tags"], day["why"] = out[0], out[1]
    return day.sort_values("pg", ascending=False)
