"""History backfill for Call Scoreboard (RULES v1.1 proposal, CoS 2026-10-06).

Problem fixed: cites with no stated premium were getting first_ask = TODAY's quote,
so a September call was scored from today's price and peak_pct ~0. That makes the
headline (0/94) an artifact, not a hit rate.

This overlay pulls daily option OHLC (Yahoo, last-trade bars, labeled yf_hist_last)
from the cite date forward for every contract Yahoo still serves, and computes:
  entry_px   stated cite_ask if given, else cite-day close (cited in session) or
             next-session open (cited after hours / weekend)
  peak_5d    max daily High within 5 trading sessions after entry (headline window)
  peak_life  max daily High while alive
Bars with Volume==0 are ignored. Highs are trades, not asks: label, never call them asks.
Writes marks_hist.json; never touches marks.json.
"""
import json, sys
from datetime import datetime, time
from pathlib import Path
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]

def occ(c):
    e = datetime.fromisoformat(c["expiry"]).strftime("%y%m%d")
    return f'{c["underlying"].upper()}{e}{c["side"].upper()}{int(round(float(c["strike"])*1000)):08d}'

def pct(a, b):
    return None if a is None or not b else round((a / b - 1) * 100, 2)

def main():
    cites = json.loads((ROOT / "cites.json").read_text())["cites"]
    out, cache = [], {}
    for c in cites:
        sym = occ(c)
        rec = {"cite_id": c["id"], "occ": sym, "handle": c.get("handle"), "cited_et": c["cited_et"],
               "hindsight_flag": bool(c.get("hindsight_flag")), "feed": "yf_hist_last"}
        try:
            cdt = datetime.strptime(c["cited_et"], "%Y-%m-%d %H:%M")
            if sym not in cache:
                cache[sym] = yf.Ticker(sym).history(start=(cdt.date()).isoformat(), interval="1d", auto_adjust=False)
            h = cache[sym]
            h = h[h["Volume"] > 0] if len(h) else h
        except Exception as ex:  # noqa
            h = None; rec["err"] = str(ex)[:120]
        if h is None or len(h) == 0:
            rec["hist_status"] = "NO_HISTORY"  # expired/delisted on Yahoo or no trades
            out.append(rec); continue
        dates = [d.date() for d in h.index]
        in_session = cdt.time() < time(16, 0) and cdt.weekday() < 5
        if in_session and dates[0] == cdt.date():
            i0, entry_hist, basis = 0, float(h["Close"].iloc[0]), "cite_day_close"
            after = h.iloc[1:]
        else:
            i0, entry_hist, basis = 0, float(h["Open"].iloc[0]), "next_open"
            after = h.iloc[0:]
        stated = c.get("cite_ask")
        entry = float(stated) if stated else entry_hist
        if stated:
            basis = "stated_ask"
        w5 = after.iloc[:5]
        p5 = float(w5["High"].max()) if len(w5) else None
        pl = float(after["High"].max()) if len(after) else None
        rec.update({
            "hist_status": "OK", "entry_px": entry, "entry_basis": basis, "entry_hist_px": entry_hist,
            "entry_bar": str(dates[0]), "bars": len(h),
            "peak_5d": p5, "peak_5d_pct": pct(p5, entry),
            "peak_life": pl, "peak_life_pct": pct(pl, entry),
            "peak_life_date": str(after["High"].idxmax().date()) if len(after) else None,
            "last_close": float(h["Close"].iloc[-1]), "last_pct": pct(float(h["Close"].iloc[-1]), entry),
            "last_bar": str(dates[-1]),
        })
        out.append(rec)
    doc = {"version": "1.1-proposal", "as_of_et": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "note": "Daily last-trade bars (Yahoo). Highs are trades not asks. Overlay only.", "marks": out}
    (ROOT / "marks_hist.json").write_text(json.dumps(doc, indent=1))
    ok = [m for m in out if m.get("hist_status") == "OK"]
    print(f"cites {len(out)}  with history {len(ok)}  no_history {len(out)-len(ok)}")

if __name__ == "__main__":
    sys.exit(main())
