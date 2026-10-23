import datetime as dt
import random
import sqlite3
from pathlib import Path

from .specs import OZ, SPECS

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
PREMIUM = {"GOLD": 0, "GOLDM": 0.0003, "GOLDTEN": 0.0005, "GOLDGUINEA": 0.0015, "GOLDPETAL": 0.003}


def connect(path=":memory:"):
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init(con):
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO contract VALUES (?,?,?)", [(s, *v) for s, v in SPECS.items()])
    con.commit()


def last_weekday(d):
    while d.weekday() > 4:
        d -= dt.timedelta(days=1)
    return d


def synthetic(con, cfg, end, sessions=60, seed=7, inject=("GOLDPETAL", 0.012)):
    """Seeded fake sessions. On the last session, `inject` pushes one near-month
    contract off fair value so the tags have something to find."""
    rng = random.Random(seed)
    days, d = [], end
    while len(days) < sessions:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    days.reverse()
    expiries, y, m = [], end.year, end.month
    while len(expiries) < 3:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        expiries.append(dt.date(y, m, 5))
    ids = {(s, e): con.execute("INSERT INTO series(symbol, expiry) VALUES (?,?)", (s, e.isoformat())).lastrowid
           for s in SPECS for e in expiries}
    comex, fx = 395000.0, 88.0
    for d in days:
        comex *= 1 + rng.gauss(0, 0.008)
        fx *= 1 + rng.gauss(0, 0.002)
        cents, e4 = round(comex), round(fx * 1e4)
        con.execute("INSERT INTO reference VALUES (?,?,?,'synthetic')", (d.isoformat(), cents, e4))
        fair = cents / 100 * e4 / 1e4 / OZ * (1 + cfg["duty_pct"])
        for (sym, e), sid in ids.items():
            pg = fair * (1 + cfg["carry_pct"] * (e - d).days / 365) * (1 + PREMIUM[sym]) * (1 + rng.gauss(0, 0.0006))
            if d == days[-1] and (sym, e) == (inject[0], expiries[0]):
                pg *= 1 + inject[1]
            vol = int(rng.uniform(200, 5000) / 10 ** expiries.index(e))
            con.execute("INSERT INTO quote(series_id, session_date, settle_paise, volume) VALUES (?,?,?,?)",
                        (sid, d.isoformat(), round(pg * SPECS[sym][1] * 100), vol))
    con.commit()
