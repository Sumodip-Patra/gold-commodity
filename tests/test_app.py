import datetime as dt
import sqlite3
import tomllib
from pathlib import Path

import pytest

from app.data import connect, init, synthetic
from app.parity import analyse, frame
from app.specs import OZ

CFG = tomllib.loads((Path(__file__).parent.parent / "config.toml").read_text())
END = dt.date(2026, 10, 22)


@pytest.fixture(scope="module")
def con():
    c = connect()
    init(c)
    synthetic(c, CFG, END)
    return c


def test_per_gram_and_fair(con):
    df = frame(con)
    day = analyse(df, CFG, END.isoformat())
    petal = day[(day.symbol == "GOLDPETAL")].iloc[0]
    assert petal.pg == pytest.approx(petal.settle_paise / 100)  # 1 g quote
    gold = day[day.symbol == "GOLD"].iloc[0]
    assert gold.pg == pytest.approx(gold.settle_paise / 100 / 10)
    cfg0 = {**CFG, "duty_pct": 0.0, "carry_pct": 0.0}
    row = analyse(df, cfg0, END.isoformat()).iloc[0]
    assert row.fair == pytest.approx(row.comex_cents_per_oz / 100 * row.usdinr_e4 / 1e4 / OZ)


def test_injected_mispricing_is_the_only_rich_row(con):
    day = analyse(frame(con), CFG, END.isoformat())
    rich = day[day.tags.apply(lambda t: "RICH" in t or "CHEAP" in t)]
    assert list(zip(rich.symbol, rich.expiry)) == [("GOLDPETAL", "2026-11-05")]


def test_ok_and_thin_tags(con):
    day = analyse(frame(con), CFG, END.isoformat())
    gold_near = day[(day.symbol == "GOLD") & (day.expiry == "2026-11-05")].iloc[0]
    assert gold_near.tags == ["OK"]
    assert "THIN" in day[day.volume < CFG["min_volume"]].tags.iloc[0]


def test_schema_refuses_bad_rows(con):
    sid = con.execute("SELECT id FROM series LIMIT 1").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO quote(series_id, session_date, settle_paise, volume) VALUES (?,?,?,?)",
                    (sid, END.isoformat(), -5, 10))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO quote(series_id, session_date, settle_paise, volume) VALUES (?,?,?,?)",
                    (sid, END.isoformat(), 100, 10))  # duplicate key
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO series(symbol, expiry) VALUES ('SILVER','2026-12-05')")


def test_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.get("/").status_code == 200
    assert "[RICH]" in c.get("/tags.txt").text
    assert c.get("/?date=1999-01-01").status_code == 404
