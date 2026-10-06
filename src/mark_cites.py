#!/usr/bin/env python3
"""Mark Cite Scout options cites against real option asks (RULES.md v1).

Pattern from AdoNunes/DiscordAlertsTrader (AlertsTracker.price_now / max_pnl):
stamp ask near cite, track now vs **peak** separately from **expiry** / **exit**.

v1 nuance: a cite can peak +50% and still expire worthless — both fields required.

Feed cascade: yfinance public option chain (delayed) labeled `public`.
Stated cite_ask preferred as first_ask when poster named a premium.
Never invent quotes. Does NOT place trades.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CITES = ROOT / "cites.json"
DEFAULT_MARKS = ROOT / "marks.json"


def now_et_str() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d %H:%M")


def contract_label(cite: Dict[str, Any]) -> str:
    return f"{cite.get('underlying', '?')} {cite.get('strike')}{cite.get('side', '?')} {cite.get('expiry', '')}"


def _pct(now: Optional[float], first: Optional[float]) -> Optional[float]:
    if now is None or first is None or first == 0:
        return None
    return round((now - first) / first * 100.0, 2)


def _yfinance_option_quote(
    underlying: str, expiry: str, side: str, strike: float
) -> Tuple[Optional[float], Optional[float], str]:
    """Return (ask_or_last, last, note)."""
    try:
        import yfinance as yf
    except ImportError:
        return None, None, "yfinance not installed"

    try:
        t = yf.Ticker(underlying)
        expiries = list(t.options or [])
        if not expiries:
            return None, None, f"no option chain for {underlying}"

        if expiry in expiries:
            use_exp = expiry
        else:
            want = date.fromisoformat(expiry)
            use_exp = min(expiries, key=lambda e: abs((date.fromisoformat(e) - want).days))
            if abs((date.fromisoformat(use_exp) - want).days) > 7:
                return None, None, f"no nearby expiry (wanted {expiry})"

        chain = t.option_chain(use_exp)
        book = chain.calls if side.upper() == "C" else chain.puts
        if book is None or book.empty:
            return None, None, "empty chain book"

        rows = book[abs(book["strike"] - float(strike)) < 0.011]
        if rows.empty:
            book = book.copy()
            book["_d"] = abs(book["strike"] - float(strike))
            rows = book.nsmallest(1, "_d")
            if float(rows.iloc[0]["_d"]) > 0.5:
                return None, None, f"no strike near {strike}"

        row = rows.iloc[0]

        def _num(v):
            try:
                if v is None:
                    return None
                f = float(v)
                return f if f > 0 else None
            except (TypeError, ValueError):
                return None

        ask_n = _num(row.get("ask"))
        last_n = _num(row.get("lastPrice"))
        bid_n = _num(row.get("bid"))
        note = f"yf {use_exp}" + ("" if use_exp == expiry else f" (wanted {expiry})")
        price = ask_n or last_n or bid_n
        if price is None:
            return None, None, note + " no bid/ask/last"
        if ask_n is None and last_n is not None:
            note += " last"
        elif ask_n is None and bid_n is not None:
            note += " bid-only"
        return price, last_n, note
    except Exception as e:
        return None, None, f"yfinance error: {e}"


def fetch_quote(cite: Dict[str, Any]) -> Tuple[Optional[float], str, str]:
    und, side, strike, expiry = cite["underlying"], cite["side"], cite["strike"], cite["expiry"]
    ask, _last, note = _yfinance_option_quote(und, expiry, side, strike)
    if ask is not None:
        return ask, "public", note
    return None, "public", note or "unmarked"


def parse_exit_from_quote(claim_quote: Optional[str]) -> Optional[float]:
    """Poster-stated *close* premium only (STC / closed / trimmed).

    Bare "Sold N puts/calls @ x" is usually STO *entry* on FinTwit — do NOT
    treat as exit. Never invent.
    """
    if not claim_quote:
        return None
    q = claim_quote.upper()
    # Require explicit close language — not bare SOLD (ambiguous with STO)
    if not re.search(
        r"\b(STC|BTC|CLOSED|CLOSING|TRIMMED|TRIMMING|TOOK\s+PROFITS?|EXITED|EXITING|"
        r"SOLD\s+(?:OUT|HALF|SOME|THE\s+REST)|OUT\s+OF)\b",
        q,
    ):
        return None
    m = re.search(
        r"\b(?:STC|BTC|CLOSED|TRIMMED|EXITED|OUT\s+OF)\b[^@0-9]{0,48}"
        r"(?:@|AT|GOT|FOR)?\s*\$?\s*(\d+(?:\.\d+)?)",
        q,
    )
    if m:
        return float(m.group(1))
    m2 = re.search(r"(?:@|GOT|AT)\s*\$?\s*(\d+(?:\.\d+)?)", q)
    if m2:
        return float(m2.group(1))
    return None


def mark_all(
    cites_path: Path,
    marks_path: Path,
    refresh_live: bool = True,
) -> Dict[str, Any]:
    cites_doc = json.loads(cites_path.read_text())
    cites: List[Dict[str, Any]] = cites_doc.get("cites", [])

    if marks_path.exists():
        try:
            marks_doc = json.loads(marks_path.read_text())
        except json.JSONDecodeError:
            marks_doc = {"version": 1, "marks": []}
    else:
        marks_doc = {"version": 1, "marks": []}
    by_id = {m["cite_id"]: m for m in marks_doc.get("marks", [])}

    as_of = now_et_str()
    today = datetime.now(ET).date()
    out_marks: List[Dict[str, Any]] = []

    for cite in cites:
        cid = cite["id"]
        prev = by_id.get(cid, {})
        expiry_d = date.fromisoformat(cite["expiry"])
        expired = expiry_d < today  # past expiry date
        # Treat expiry day after close as expired for simplicity when date < today;
        # on expiry day keep LIVE until we can stamp expiry mark — if date == today still LIVE.

        stated = cite.get("cite_ask")
        # Prefer prior first_ask; else stated premium; else live stamp
        first_ask = prev.get("first_ask")
        if first_ask is None and stated is not None:
            first_ask = float(stated)

        feed = prev.get("feed", "public")
        note = prev.get("note", "")
        now_ask = prev.get("now_ask")
        peak_ask = prev.get("peak_ask")
        peak_pct_prev = prev.get("peak_pct")
        time_to_peak_et = prev.get("time_to_peak_et")
        expiry_ask = prev.get("expiry_ask")
        exit_ask = prev.get("exit_ask")
        unmarked_reason = None

        # Stated exit from claim text (once)
        if exit_ask is None:
            exit_ask = parse_exit_from_quote(cite.get("claim_quote"))

        if refresh_live and not expired:
            price, feed_q, qnote = fetch_quote(cite)
            note = qnote
            feed = feed_q if price is not None else feed
            if price is not None:
                now_ask = price
                if first_ask is None:
                    first_ask = price
                    feed = feed_q
                # Peak = max ask while alive
                if peak_ask is None or price > peak_ask:
                    peak_ask = price
                    time_to_peak_et = as_of
                # Keep peak at least first_ask floor
                if peak_ask is not None and first_ask is not None and peak_ask < first_ask:
                    peak_ask = first_ask
                    if time_to_peak_et is None:
                        time_to_peak_et = cite.get("cited_et")
            else:
                unmarked_reason = qnote
                if first_ask is None and stated is not None:
                    first_ask = float(stated)
                    feed = "stated_ask"
                    note = "no chain quote; first_ask = poster-stated premium only"
        elif expired:
            # Stamp expiry: 0 if never quoted (OTM worthless proxy) or last known now_ask
            if refresh_live:
                # Try one last quote; if chain gone → 0
                price, feed_q, qnote = fetch_quote(cite)
                note = (qnote + "; expired") if qnote else "expired"
                if price is not None:
                    expiry_ask = price
                    now_ask = price
                    feed = feed_q
                    if peak_ask is None or price > peak_ask:
                        peak_ask = price
                        time_to_peak_et = as_of
                else:
                    expiry_ask = 0.0 if expiry_ask is None else expiry_ask
                    if now_ask is None:
                        now_ask = expiry_ask
                    note = (qnote or "chain gone") + "; expiry_ask=0 OTM/worthless proxy"
            if first_ask is None and stated is not None:
                first_ask = float(stated)
                if feed == "public":
                    feed = "stated_ask"
            if peak_ask is None and first_ask is not None:
                peak_ask = first_ask
                time_to_peak_et = time_to_peak_et or cite.get("cited_et")
            if expiry_ask is None:
                expiry_ask = 0.0
        else:
            if first_ask is None and stated is not None:
                first_ask = float(stated)
                feed = "stated_ask"

        # If stated first_ask and live first stamp was wrong historically, prefer stated when present
        # (accountability to claimed entry). Only override when prev first_ask came from live
        # and stated exists and differs by >1% — actually RULES: stated preferred.
        if stated is not None and first_ask is not None:
            # Keep stated as first_ask always when poster named premium
            first_ask = float(stated)
            if feed == "public" and prev.get("first_ask") != float(stated):
                feed = "stated_ask+public"
            # Re-base peak floor
            if peak_ask is not None and peak_ask < first_ask:
                # live peak below stated entry — still keep observed peak for max map
                pass
            if peak_ask is None:
                peak_ask = first_ask
                time_to_peak_et = cite.get("cited_et")

        ask_pct = _pct(now_ask, first_ask)
        peak_pct = _pct(peak_ask, first_ask)
        expiry_pct = _pct(expiry_ask, first_ask) if expiry_ask is not None else None
        exit_pct = _pct(exit_ask, first_ask) if exit_ask is not None else None

        # Peak-based wins (headline)
        win_50 = peak_pct is not None and peak_pct >= 50.0
        win_2x = peak_pct is not None and peak_pct >= 100.0
        win_3x = peak_pct is not None and peak_pct >= 200.0
        # Hold-to-expiry (separate)
        hold_expiry_win = expiry_pct is not None and expiry_pct >= 50.0
        # Early-exit opportunity: peaked but expired ≤0
        early_vs_expiry = (
            peak_pct is not None
            and peak_pct >= 50.0
            and expiry_pct is not None
            and expiry_pct <= 0.0
        )

        if expired:
            status = "EXPIRED"
        elif first_ask is None:
            status = "UNMARKED"
        elif ask_pct is not None and ask_pct <= -50.0 and (peak_pct is None or peak_pct < 50.0):
            status = "GRAVEYARD"
        else:
            status = "LIVE"

        mark = {
            "cite_id": cid,
            "contract": contract_label(cite),
            "handle": cite.get("handle"),
            "cited_et": cite.get("cited_et"),
            "feed": feed,
            "as_of_et": as_of,
            "first_ask": first_ask,
            "now_ask": now_ask,
            "ask_pct": ask_pct,
            "peak_ask": peak_ask,
            "peak_pct": peak_pct,
            "time_to_peak_et": time_to_peak_et,
            "exit_ask": exit_ask,
            "exit_pct": exit_pct,
            "expiry_ask": expiry_ask,
            "expiry_pct": expiry_pct,
            "status": status,
            "win_50": bool(win_50) if peak_pct is not None else None,
            "win_2x": bool(win_2x) if peak_pct is not None else None,
            "win_3x": bool(win_3x) if peak_pct is not None else None,
            "hold_expiry_win": bool(hold_expiry_win) if expiry_pct is not None else None,
            "early_vs_expiry": bool(early_vs_expiry) if (peak_pct is not None and expiry_pct is not None) else None,
            "hindsight_flag": cite.get("hindsight_flag", False),
            "post_url": cite.get("post_url"),
            "note": note,
            "unmarked_reason": unmarked_reason,
        }
        out_marks.append(mark)

    doc = {
        "version": 1,
        "rules": "RULES.md v1 — peak_pct separate from expiry_pct/exit_pct; headline win_50=peak",
        "updated_et": as_of,
        "disclaimer": "Social callouts are evidence to interrogate, never a copy signal. No CLEAR trade advice.",
        "marks": out_marks,
    }
    marks_path.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Mark options cites (RULES v1 peak/expiry/exit)")
    ap.add_argument("--cites", type=Path, default=DEFAULT_CITES)
    ap.add_argument("--marks", type=Path, default=DEFAULT_MARKS)
    ap.add_argument("--no-refresh", action="store_true")
    args = ap.parse_args(argv)

    if not args.cites.exists():
        print(f"Missing cites: {args.cites}", file=sys.stderr)
        return 1

    # Fresh first_ask from stated: wipe prior first_ask when re-marking with stated preference
    # by clearing marks peak floors only if --reset — default merges.

    doc = mark_all(args.cites, args.marks, refresh_live=not args.no_refresh)
    n = len(doc["marks"])
    live = sum(1 for m in doc["marks"] if m["status"] == "LIVE")
    exp = sum(1 for m in doc["marks"] if m["status"] == "EXPIRED")
    unmarked = sum(1 for m in doc["marks"] if m["status"] == "UNMARKED")
    early = sum(1 for m in doc["marks"] if m.get("early_vs_expiry"))
    print(
        f"Marked {n} → {args.marks} LIVE={live} EXPIRED={exp} UNMARKED={unmarked} "
        f"early_vs_expiry={early} as_of {doc['updated_et']} ET"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
