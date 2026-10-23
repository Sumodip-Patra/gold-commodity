import os
import tomllib
from datetime import date as Date
from html import escape as esc
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from .data import connect, init, last_weekday, synthetic
from .parity import analyse, frame

cfg = tomllib.loads((Path(__file__).parent.parent / "config.toml").read_text())
con = connect(os.environ.get("GOLD_DB", ":memory:"))
if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'contract'").fetchone():
    init(con)
    synthetic(con, cfg, last_weekday(Date.today()))
app = FastAPI()

CSS = """
:root{--paper:#e9eef1;--ink:#16222d;--rule:#aebbc5;--quiet:#7b8a96;--rich:#9c2a2a;--cheap:#1c5c99;--brass:#8c6d1f}
*{box-sizing:border-box}
body{margin:0;padding:1.5rem;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:76rem;margin:0 auto}
h1{font-size:1.5rem;font-weight:600;margin:0 0 .25rem}
p{max-width:62ch;margin:.25rem 0}
form{display:flex;gap:.75rem;align-items:end;margin:1rem 0}
label{display:grid;gap:.125rem;font-size:.875rem}
input,button{font:inherit;padding:.375rem .625rem;border:1px solid var(--ink);background:#fff;color:var(--ink)}
button{background:var(--ink);color:#fff;cursor:pointer}
:focus-visible{outline:3px solid var(--brass);outline-offset:2px}
.scroll{overflow-x:auto;border-top:2px solid var(--ink)}
table{border-collapse:collapse;width:100%;min-width:60rem;font-variant-numeric:tabular-nums}
th,td{padding:.5rem .75rem;text-align:left;border-bottom:1px solid var(--rule);vertical-align:middle}
th{font-weight:600;font-size:.875rem}
td.n,th.n{text-align:right}
.rich{color:var(--rich);font-weight:600}.cheap{color:var(--cheap);font-weight:600}
"""


def session(date):
    df = frame(con)
    days = sorted(df.d.unique())
    date = date or days[-1]
    if date not in days:
        return None, days
    return (date, analyse(df, cfg, date), df[df.d == date].source.iloc[0]), days


def bar(b, tags):
    w = max(-60, min(60, b / 1.5 * 60))
    color = "var(--rich)" if "RICH" in tags else "var(--cheap)" if "CHEAP" in tags else "var(--quiet)"
    return (f'<svg width="120" height="12" role="img" aria-label="{b:+.2f} percent from fair">'
            f'<rect x="{min(60, 60 + w):.1f}" y="2" width="{abs(w):.1f}" height="8" fill="{color}"/>'
            f'<line x1="60" x2="60" y1="0" y2="12" stroke="var(--brass)" stroke-width="2"/></svg>')


def tag_html(tags):
    return " ".join(f'<span class="{t.lower()}">[{t}]</span>' if t in ("RICH", "CHEAP") else f"[{t}]" for t in tags)


def page(body):
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gold contracts, per gram</title><style>{CSS}</style><main>{body}</main></html>'


@app.get("/", response_class=HTMLResponse)
def index(date: str | None = Query(None)):
    got, days = session(date)
    form = (f'<form><label>Session<input type="date" name="date" min="{days[0]}" max="{days[-1]}" '
            f'value="{esc(date or days[-1])}"></label><button>Show session</button></form>')
    head = "<h1>Gold contracts, per gram</h1>"
    if got is None:
        msg = f"<p>No session on {esc(date)}. Pick a date from {days[0]} to {days[-1]}.</p>"
        return HTMLResponse(page(head + msg + form), 404)
    d, rows, source = got
    trs = "".join(
        f'<tr><td>{r.symbol}</td><td>{r.expiry}</td><td class="n">{r.pg:,.2f}</td><td class="n">{r.fair:,.2f}</td>'
        f'<td>{bar(r.basis_pct, r.tags)}</td><td class="n">{r.basis_pct:+.2f}%</td>'
        f'<td class="n">{"" if r.premium_pct != r.premium_pct else f"{r.premium_pct:+.2f}%"}</td>'
        f"<td>{tag_html(r.tags)}</td><td>{esc(r.why)}</td></tr>"
        for r in rows.itertuples())
    intro = (f"<p>Session {d}. Data source: {source}. The brass line is fair value per gram from COMEX gold, "
             f"USDINR, import duty and carry. Each bar shows how far a contract settled from it.</p>")
    table = ('<div class="scroll"><table><thead><tr><th>Contract</th><th>Expiry</th><th class="n">Rupees per gram</th>'
             '<th class="n">Fair per gram</th><th colspan="2">Distance from fair</th><th class="n">Over GOLD</th>'
             f"<th>Tags</th><th>Why</th></tr></thead><tbody>{trs}</tbody></table></div>")
    return page(head + intro + form + table + f'<p><a href="/tags.txt?date={d}">Plain text tags for this session</a></p>')


@app.get("/tags.txt", response_class=PlainTextResponse)
def tags_txt(date: str | None = Query(None)):
    got, days = session(date)
    if got is None:
        return PlainTextResponse(f"No session on {date}. Available {days[0]} to {days[-1]}.\n", 404)
    d, rows, _ = got
    return "".join(f"{d} {r.symbol} {r.expiry} {''.join(f'[{t}]' for t in r.tags)} {r.why}\n" for r in rows.itertuples())


@app.get("/api/rows")
def api_rows(date: str | None = Query(None)):
    got, days = session(date)
    if got is None:
        return {"error": f"No session on {date}", "first": days[0], "last": days[-1]}
    d, rows, _ = got
    cols = ["symbol", "expiry", "pg", "fair", "basis_pct", "z_basis", "premium_pct", "tags", "why"]
    return {"date": d, "rows": rows[cols].where(rows[cols].notna(), None).to_dict("records")}
