#!/usr/bin/env python3
"""Parse free-text option callouts into structured contracts.

Inspired by austinpkugler/trendfin ContractParser (MIT) — reimplemented
without pandas/emoji deps so Cite Scout can run lean. Also accepts
DiscordAlertsTrader-style "BTO SPY 780C 10/10 @ 1.25" fragments.

Examples:
  "SPY 780C 10/10"
  "AAPL $500C for 9/12"
  "$TSLA 420 calls Oct 23"
  "BTO NVDA 205P 11/20 @ 2.19"
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional


@dataclass
class ParsedContract:
    underlying: str
    side: str  # C | P
    strike: float
    expiry: Optional[str]  # YYYY-MM-DD when year resolvable, else MM/DD raw
    expiry_raw: Optional[str] = None
    ask: Optional[float] = None
    source_text: str = ""


# Common cashtag / ticker token (1–5 letters). Not a full universe filter.
_TICKER = r"(?:\$)?([A-Z]{1,5})\b"
_STRIKE_SIDE = r"(\d+(?:\.\d+)?)\s*([CcPp]|CALLS?|PUTS?)\b"
_DATE = r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)"
_ASK = r"(?:@|at)\s*\$?\s*(\d+(?:\.\d+)?)(?:\s|$)|(?:got|paid|fill(?:ed)?(?:\s+at)?)\s*\$?\s*(\d+(?:\.\d+)?)"


def _normalize_side(token: str) -> str:
    t = token.upper()
    if t.startswith("P"):
        return "P"
    return "C"


def _resolve_expiry(raw: str, as_of: Optional[date] = None) -> str:
    """Turn M/D or M/D/Y into YYYY-MM-DD. Yearless → next occurrence from as_of."""
    as_of = as_of or date.today()
    parts = raw.split("/")
    month, day = int(parts[0]), int(parts[1])
    if len(parts) == 3:
        year = int(parts[2])
        if year < 100:
            year += 2000
        return date(year, month, day).isoformat()
    candidate = date(as_of.year, month, day)
    if candidate < as_of:
        candidate = date(as_of.year + 1, month, day)
    return candidate.isoformat()


def _month_name_to_md(text: str) -> Optional[str]:
    """Pull 'Oct 23' / 'October 23, 2026' style into M/D[/Y]."""
    months = {
        "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
        "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
        "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9,
        "SEPTEMBER": 9, "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11,
        "DEC": 12, "DECEMBER": 12,
    }
    m = re.search(
        r"\b(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|"
        r"JUL(?:Y)?|AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|OCT(?:OBER)?|"
        r"NOV(?:EMBER)?|DEC(?:EMBER)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
        r"(?:,?\s*((?:20)?\d{2}))?\b",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    month = months[m.group(1).upper().replace(".", "")]
    day = int(m.group(2))
    year = m.group(3)
    if year:
        y = int(year)
        if y < 100:
            y += 2000
        return f"{month}/{day}/{y}"
    return f"{month}/{day}"


def parse_contracts(text: str, as_of: Optional[date] = None) -> List[ParsedContract]:
    """Extract option contracts from free text. Order-preserving, de-duped."""
    if not text:
        return []
    original = text
    text_u = text.upper()
    # Capture @ask / got $x BEFORE stripping @ (trendfin clears @ for tokenizing)
    ask_m = re.search(_ASK, text_u, re.IGNORECASE)
    ask = None
    if ask_m:
        ask = float(next(g for g in ask_m.groups() if g is not None))
    text_u = re.sub(r"HTTPS?://\S+", " ", text_u)
    text_u = re.sub(r"[\n@]", " ", text_u)
    # Verbose CALL/PUT → C/P glued to strike (trendfin style)
    text_u = re.sub(r"(\d+(?:\.\d+)?)\s*(CALLS?|CS)\b", r"\1C", text_u)
    text_u = re.sub(r"(\d+(?:\.\d+)?)\s*(PUTS?|PS)\b", r"\1P", text_u)
    text_u = re.sub(r"(\d+(?:\.\d+)?)\s+([CP])\b", r"\1\2", text_u)

    month_raw = _month_name_to_md(text_u)
    results: List[ParsedContract] = []
    seen = set()

    # Pattern A: TICKER … STRIKESIDE … DATE  (flexible gap)
    pat_a = re.compile(
        rf"{_TICKER}(?:\s+|\s*\$\s*){_STRIKE_SIDE}(?:\s*(?:FOR|EXP(?:IRY|IRING)?|EXP)?\s*){_DATE}?",
        re.IGNORECASE,
    )
    # Pattern B: compact "SPY 780C 10/10"
    pat_b = re.compile(
        rf"{_TICKER}\s+(\d+(?:\.\d+)?)([CP])\s+{_DATE}",
        re.IGNORECASE,
    )
    # Pattern C: "TICKER $500C for 9/12"
    pat_c = re.compile(
        rf"{_TICKER}\s+\$?\s*(\d+(?:\.\d+)?)([CP])\s+(?:FOR\s+)?{_DATE}",
        re.IGNORECASE,
    )

    def _add(ticker: str, strike: float, side: str, date_raw: Optional[str]):
        expiry_raw = date_raw or month_raw
        expiry = _resolve_expiry(expiry_raw, as_of) if expiry_raw else None
        key = (ticker, side, strike, expiry)
        if key in seen:
            return
        seen.add(key)
        results.append(
            ParsedContract(
                underlying=ticker,
                side=side,
                strike=strike,
                expiry=expiry,
                expiry_raw=expiry_raw,
                ask=ask,
                source_text=original.strip()[:240],
            )
        )

    for m in pat_b.finditer(text_u):
        _add(m.group(1).upper(), float(m.group(2)), m.group(3).upper(), m.group(4))
    for m in pat_c.finditer(text_u):
        _add(m.group(1).upper(), float(m.group(2)), m.group(3).upper(), m.group(4))
    for m in pat_a.finditer(text_u):
        ticker = m.group(1).upper()
        strike = float(m.group(2))
        side = _normalize_side(m.group(3))
        date_raw = m.group(4)
        _add(ticker, strike, side, date_raw)

    # Fallback: prefer $cashtags; "350 strike" + CALL/PUT + month name
    if not results:
        cashtags = re.findall(r"\$([A-Z]{1,5})\b", text_u)
        stop = {
            "CALL", "PUTS", "PUT", "CALLS", "THE", "FOR", "AND", "OCT", "NOV", "DEC",
            "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "EXP",
            "BOUGHT", "SOLD", "LOADED", "ABOVE", "ASK", "THIS", "BUY", "SOME",
            "STRIKE", "EXPIRY", "EXPIRING", "PICKED", "PICKE", "GOT", "MORE",
            "LONG", "SHORT", "FROM", "WITH", "THAT", "HAVE", "JUST", "INTO",
        }
        tickers = [t for t in cashtags if t not in stop]
        if not tickers:
            # whole-word tickers only (2–5 caps), exclude stop
            tickers = [
                t for t in re.findall(r"\b([A-Z]{2,5})\b", text_u)
                if t not in stop
            ]
        strike_side = re.search(r"(\d+(?:\.\d+)?)([CP])\b", text_u)
        side = None
        strike = None
        if strike_side:
            strike = float(strike_side.group(1))
            side = strike_side.group(2).upper()
        else:
            sm = re.search(r"\$?(\d+(?:\.\d+)?)\s*STRIKE", text_u)
            if sm:
                strike = float(sm.group(1))
                if re.search(r"\bPUTS?\b", text_u):
                    side = "P"
                elif re.search(r"\bCALLS?\b", text_u):
                    side = "C"
        if tickers and strike is not None and side:
            _add(tickers[0], strike, side, month_raw)

    return results


def parse_one(text: str, as_of: Optional[date] = None) -> Optional[ParsedContract]:
    found = parse_contracts(text, as_of=as_of)
    return found[0] if found else None


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Parse option contracts from free text")
    ap.add_argument("text", nargs="*", help="Text to parse (or stdin)")
    ap.add_argument("--json", action="store_true", help="Emit JSON")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD for yearless expiry")
    args = ap.parse_args(list(argv) if argv is not None else None)

    text = " ".join(args.text) if args.text else None
    if not text:
        import sys
        text = sys.stdin.read()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None
    contracts = parse_contracts(text, as_of=as_of)
    if args.json:
        print(json.dumps([asdict(c) for c in contracts], indent=2))
    else:
        if not contracts:
            print("No contracts found")
            return 1
        for c in contracts:
            ask_s = f" @{c.ask}" if c.ask is not None else ""
            print(f"{c.underlying} {c.strike:g}{c.side} exp={c.expiry or c.expiry_raw}{ask_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
