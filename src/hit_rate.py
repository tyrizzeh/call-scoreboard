#!/usr/bin/env python3
"""Hit Rate + streaks from Mark Desk marks (RULES.md v1.1).

Headline overall hit rate = peak win_50.
Also: hold-to-expiry hit rate, early-exit opportunity rate
(peak win_50 but expiry_pct ≤ 0).

Streaks use peak win_50 by cited_et (LuxAlgo trade-journal streak math).
Social = interrogate, never copy. No CLEAR trade advice.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKS = ROOT / "marks.json"
DEFAULT_CITES = ROOT / "cites.json"
DEFAULT_OUT = ROOT / "scoreboard.json"
DEFAULT_MD = ROOT / "scoreboard.md"
DEFAULT_HANDLES = ROOT / "handles.json"


def _contract_label(cite: Dict[str, Any]) -> str:
    und = cite.get("underlying")
    side = cite.get("side")
    strike = cite.get("strike")
    exp = cite.get("expiry")
    if und and side and strike is not None and exp:
        return f"{und} {strike}{side} {exp}"
    return ""


def apply_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """RULES v1.1 (CoS 2026-10-06): score from cite-time price, not today's stamp.

    Overlay marks_hist.json (Yahoo daily last-trade bars from cite date). When history
    exists: first_ask=entry_px (stated premium preferred), headline peak_pct=peak_5d_pct,
    peak_life_pct kept for the max-gain map. When no history AND no observed path from
    cite time (cited before today, no stated-ask path seen), win flags -> None so the row
    leaves the headline instead of counting as a fake 0% loss.
    """
    hp = ROOT / "marks_hist.json"
    if not hp.exists():
        return rows
    try:
        hist = {m["cite_id"]: m for m in json.loads(hp.read_text()).get("marks", [])}
    except Exception:
        return rows
    today = datetime.now(ET).strftime("%Y-%m-%d")

    def _p(a, b):
        return None if a is None or not b else round((a / b - 1) * 100, 2)

    out = []
    for r in rows:
        r = dict(r)
        h = hist.get(r.get("cite_id"))
        if h and h.get("hist_status") == "OK" and h.get("entry_px"):
            e = float(h["entry_px"])
            r["first_ask_live_stamp"] = r.get("first_ask")
            r["first_ask"] = e
            r["entry_basis"] = h.get("entry_basis")
            # RULES v1.1: labeled external peaks (yahoo_daily_high / chartexchange_eod_high)
            # overwrite only when labeled AND higher than CBOE live stamp.
            src_l = str(r.get("peak_source") or r.get("peak_feed") or "").lower()
            labeled_ext = ("yahoo" in src_l) or ("chartexchange" in src_l)
            ext_peak_ask = r.get("peak_ask") if labeled_ext else None
            ext_peak_pct = r.get("peak_pct") if labeled_ext else None
            cboe_peak_pct = r.get("peak_cboe_pct")
            if cboe_peak_pct is None and labeled_ext:
                cboe_peak_pct = r.get("ask_pct")
            cboe_peak_ask = r.get("peak_ask") if not labeled_ext else None
            r["feed"] = f"{r.get('feed')}+yf_hist_last"
            pk = h.get("peak_5d_pct")
            if pk is None:
                pk = _p(r.get("peak_ask"), e)
            use_ext = (
                labeled_ext
                and ext_peak_pct is not None
                and ext_peak_pct > (cboe_peak_pct if cboe_peak_pct is not None else float("-inf"))
            )
            if use_ext:
                r["peak_pct"] = ext_peak_pct
                r["peak_ask"] = ext_peak_ask
                r["peak_feed"] = r.get("peak_source")
                pk = ext_peak_pct
                r["peak_hist_5d_pct"] = h.get("peak_5d_pct")
                r["peak_cboe_pct"] = cboe_peak_pct
            else:
                r["peak_pct"] = pk
                r["peak_ask"] = h.get("peak_5d") if h.get("peak_5d") is not None else (
                    ext_peak_ask if labeled_ext else cboe_peak_ask
                )
                if h.get("peak_5d") is not None and not labeled_ext:
                    r["peak_source"] = r.get("peak_source") or "cboe_delayed+yf_hist_last"
                if labeled_ext and ext_peak_pct is not None and not use_ext:
                    r["peak_ext_skipped_pct"] = ext_peak_pct
            r["peak_life_pct"] = h.get("peak_life_pct")
            r["peak_life_date"] = h.get("peak_life_date")
            if r.get("now_ask") is not None:
                r["ask_pct"] = _p(r["now_ask"], e)
            elif h.get("last_close") is not None:
                r["ask_pct"] = h.get("last_pct")
            if r.get("expiry_ask") is not None:
                r["expiry_pct"] = _p(r["expiry_ask"], e)
            if pk is not None:
                r["win_50"], r["win_2x"], r["win_3x"] = pk >= 50, pk >= 100, pk >= 200
            # Window still open and not yet a win -> pending (not a loss yet)
            post_bars = max(0, int(h.get("bars") or 0) - (1 if h.get("entry_basis") != "next_open" else 0))
            expired = (r.get("status") == "EXPIRED")
            if not r.get("win_50") and post_bars < 5 and not expired:
                r["pending"] = True
                r["unscored_reason"] = f"5-session window open ({post_bars}/5)"
                r["win_50"] = r["win_2x"] = r["win_3x"] = None
            if r.get("expiry_pct") is not None:
                r["hold_expiry_win"] = r["expiry_pct"] >= 50
                r["early_vs_expiry"] = bool(pk is not None and pk >= 50 and r["expiry_pct"] <= 0)
            r["path_observed"] = True
        else:
            cited_day = (r.get("cited_et") or "")[:10]
            observed_win = (r.get("peak_pct") or 0) >= 50
            if cited_day and cited_day < today and not observed_win:
                r["path_observed"] = False
                r["unscored_reason"] = "no price path from cite time (no history; live stamp is late)"
                r["win_50"] = r["win_2x"] = r["win_3x"] = None
            else:
                r["path_observed"] = True
        out.append(r)
    return out



def join_cites(marks: List[Dict[str, Any]], cites_path: Path) -> List[Dict[str, Any]]:
    """Denormalize handle / cited_et / contract from cites.json onto marks."""
    if not cites_path.exists():
        return marks
    cites_doc = json.loads(cites_path.read_text())
    by_id = {c.get("id"): c for c in cites_doc.get("cites", []) if c.get("id")}
    out: List[Dict[str, Any]] = []
    for m in marks:
        row = dict(m)
        c = by_id.get(m.get("cite_id") or "", {})
        if c:
            row["handle"] = c.get("handle") or row.get("handle")
            row["cited_et"] = c.get("cited_et") or row.get("cited_et")
            if "hindsight_flag" not in row or row.get("hindsight_flag") is None:
                row["hindsight_flag"] = c.get("hindsight_flag")
            if not row.get("note"):
                row["note"] = c.get("note")
            if not row.get("claim_quote"):
                row["claim_quote"] = c.get("claim_quote")
            if not row.get("platform"):
                row["platform"] = c.get("platform")
            if not row.get("handle_label"):
                h = row.get("handle") or c.get("handle") or ""
                plat = row.get("platform") or c.get("platform") or ""
                row["handle_label"] = f"{h} · {plat}" if h and plat else (h or plat or None)
            label = _contract_label(c)
            if label:
                row["contract"] = label
            elif not row.get("contract"):
                row["contract"] = row.get("occ")
        out.append(row)
    return apply_history(out)



_SHORT_PREMIUM_RE = re.compile(
    r"\b("
    r"CSP|cash[- ]secured|covered calls?|short[- ]premium|"
    r"short\s+(?:CSP|LEAP\s+)?(?:calls?|puts?)|"
    r"sell to open|\bSTO\b|credit spread|\bwheel\b|"
    r"sold\s+(?:this\s+)?(?:\d+\s+)?(?:more\s+)?(?:cash secured puts?|covered calls?|puts?|calls?)|"
    r"sold\s+\d+\s+more\b[^.]{0,40}?\b(?:calls?|puts?)"
    r")\b",
    re.I,
)


def is_short_premium(row: Dict[str, Any]) -> bool:
    """CSP/CC / sold-premium — park off long peak win_50 path (RULES.md)."""
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("note", "claim_quote", "first_ask_note", "contract")
    )
    return bool(_SHORT_PREMIUM_RE.search(blob))


def now_et_str() -> str:

    return datetime.now(ET).strftime("%Y-%m-%d %H:%M")


def confidence(n: int) -> str:
    if n < 10:
        return "thin"
    if n < 30:
        return "decent"
    return "strong"


def streak_stats(ordered_wins: List[Optional[bool]]) -> Dict[str, Any]:
    """Signed run: +W / -L. None (unmarked) breaks the streak (RULES)."""
    max_win = 0
    max_loss = 0
    run = 0
    current = 0
    for w in ordered_wins:
        if w is None:
            run = 0
            continue
        direction = 1 if w else -1
        if run == 0 or (run > 0) != (direction > 0):
            run = direction
        else:
            run = run + direction
        if run > max_win:
            max_win = run
        if -run > max_loss:
            max_loss = -run
        current = run
    label = "flat"
    if current > 0:
        label = f"{current}W"
    elif current < 0:
        label = f"{-current}L"
    return {
        "current_streak": current,
        "current_streak_label": label,
        "longest_win_streak": max_win,
        "longest_loss_streak": max_loss,
    }


def rate_block(marks: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [m for m in marks if m.get("first_ask") is not None and m.get("win_50") is not None]
    n = len(scored)
    if n == 0:
        return {
            "n": 0,
            "win_50": None,
            "win_2x": None,
            "win_3x": None,
            "wins_50": 0,
            "wins_2x": 0,
            "wins_3x": 0,
            "hold_expiry_n": 0,
            "hold_expiry_hit_rate": None,
            "hold_expiry_wins": 0,
            "early_exit_opp_n": 0,
            "early_exit_opp_rate": None,
            "early_exit_opp_count": 0,
            "avg_peak_pct": None,
            "avg_expiry_pct": None,
            "median_peak_pct": None,
            "median_expiry_pct": None,
            "confidence": "thin",
        }

    def _rate(key: str):
        wins = sum(1 for m in scored if m.get(key))
        return wins, round(wins / n, 4)

    w50, r50 = _rate("win_50")
    w2, r2 = _rate("win_2x")
    w3, r3 = _rate("win_3x")

    # Hold-to-expiry book: only cites with expiry_pct stamped
    expiry_scored = [m for m in scored if m.get("expiry_pct") is not None]
    he_n = len(expiry_scored)
    he_wins = sum(1 for m in expiry_scored if m.get("hold_expiry_win"))
    he_rate = round(he_wins / he_n, 4) if he_n else None

    # Early-exit opportunity: peak win but expiry ≤ 0 (needs both)
    early_eligible = [
        m for m in scored
        if m.get("peak_pct") is not None and m.get("expiry_pct") is not None
    ]
    ee_n = len(early_eligible)
    ee_count = sum(1 for m in early_eligible if m.get("early_vs_expiry"))
    ee_rate = round(ee_count / ee_n, 4) if ee_n else None

    peaks = sorted(m["peak_pct"] for m in scored if m.get("peak_pct") is not None)
    exps = sorted(m["expiry_pct"] for m in expiry_scored if m.get("expiry_pct") is not None)

    def _median(vals):
        if not vals:
            return None
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 else round((vals[mid - 1] + vals[mid]) / 2, 2)

    def _mean(vals):
        if not vals:
            return None
        return round(sum(vals) / len(vals), 2)

    peak_vals = [m["peak_pct"] for m in scored if m.get("peak_pct") is not None]
    exp_vals = [m["expiry_pct"] for m in scored if m.get("expiry_pct") is not None]

    return {
        "n": n,
        "win_50": r50,
        "win_2x": r2,
        "win_3x": r3,
        "wins_50": w50,
        "wins_2x": w2,
        "wins_3x": w3,
        "hold_expiry_n": he_n,
        "hold_expiry_hit_rate": he_rate,
        "hold_expiry_wins": he_wins,
        "early_exit_opp_n": ee_n,
        "early_exit_opp_rate": ee_rate,
        "early_exit_opp_count": ee_count,
        "avg_peak_pct": _mean(peak_vals),
        "avg_expiry_pct": _mean(exp_vals),
        "median_peak_pct": _median(peaks),
        "median_expiry_pct": _median(exps),
        "confidence": confidence(n),
    }


def ordered_win50(marks: List[Dict[str, Any]]) -> List[Optional[bool]]:
    sorted_m = sorted(marks, key=lambda m: m.get("cited_et") or "")
    out: List[Optional[bool]] = []
    for m in sorted_m:
        if m.get("pending") or m.get("path_observed") is False:
            continue  # v1.1: open window / no cite-time path = skip, not a streak break
        if m.get("first_ask") is None or m.get("win_50") is None:
            out.append(None)
        else:
            out.append(bool(m["win_50"]))
    return out



def build_feasibility(
    long_marks: List[Dict[str, Any]],
    short_marks: List[Dict[str, Any]],
    contaminated: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Phone Overview: why a play makes sense or not (interrogate, not CLEAR)."""
    out: List[Dict[str, Any]] = []

    def _add(m: Dict[str, Any], verdict: str, why: str) -> None:
        out.append({
            "cite_id": m.get("cite_id"),
            "contract": m.get("contract"),
            "handle": m.get("handle"),
            "platform": m.get("platform"),
            "handle_label": m.get("handle_label") or (
                f"{m.get('handle')} · {m.get('platform')}" if m.get("handle") and m.get("platform") else m.get("handle")
            ),
            "verdict": verdict,
            "why": why,
            "peak_pct": m.get("peak_pct"),
            "ask_pct": m.get("ask_pct"),
            "status": m.get("status"),
        })

    for m in contaminated:
        if m.get("win_50"):
            _add(
                m,
                "kill-hindsight",
                f"Peak {m.get('peak_pct')}% but hindsight_flag=true — excluded from headline; do not promote.",
            )
        else:
            _add(
                m,
                "contam",
                "Hindsight / after-the-fact — parked out of long peak win_50.",
            )

    # Top live long peaks still <50%: watching, not hits yet
    live_long = [
        m for m in long_marks
        if m.get("status") == "LIVE" and m.get("first_ask") is not None
    ]
    live_long.sort(key=lambda m: -(m.get("peak_pct") or -999))
    # Clean long win_50 hits (any status) — headline material
    hits = [m for m in long_marks if m.get("win_50") and m.get("first_ask") is not None]
    def _hit_key(m):
        src = str(m.get("peak_source") or "")
        yahoo_boost = 1 if ("yahoo" in src or "chartexchange" in src) else 0
        return (yahoo_boost, m.get("peak_pct") or 0)
    hits.sort(key=_hit_key, reverse=True)
    for m in hits[:12]:
        src = m.get("peak_source") or m.get("peak_feed") or m.get("feed") or "unknown"
        early = " early_vs_expiry=YES." if m.get("early_vs_expiry") else ""
        _add(
            m,
            "hit",
            f"Clean win_50 peak +{m.get('peak_pct')}% (peak_source={src}).{early} Peak ≠ expiry — hold path separate.",
        )

    for m in live_long[:6]:
        peak = m.get("peak_pct") or 0
        note = (m.get("note") or m.get("claim_quote") or "")[:120]
        if m.get("win_50"):
            continue  # already in hits
        if peak >= 50:
            _add(m, "hit-watch", f"Peak already ≥50% ({peak}%). Confirm window + feed before counting.")
        elif peak >= 10:
            flow = "flow print" if "flow" in note.lower() or "optionwhales" in (m.get("handle") or "").lower() else "first-person / thesis"
            _add(
                m,
                "watch",
                f"Best long peak so far +{peak}% — still short of win_50. {flow}. Peak ≠ expiry.",
            )
        elif (m.get("ask_pct") or 0) <= -50:
            _add(
                m,
                "kill-thesis",
                f"Ask {m.get('ask_pct')}% with peak {peak}% — thesis spent / no peak recovery path yet.",
            )

    # Deep underwater longs with flat peak
    underwater = [
        m for m in live_long
        if (m.get("ask_pct") is not None and m.get("ask_pct") <= -50 and (m.get("peak_pct") or 0) < 10)
    ]
    underwater.sort(key=lambda m: m.get("ask_pct") or 0)
    seen = {r["cite_id"] for r in out}
    for m in underwater[:5]:
        if m.get("cite_id") in seen:
            continue
        _add(
            m,
            "kill-thesis",
            f"Live ask {m.get('ask_pct')}%, peak {m.get('peak_pct') or 0}% — no +50% path printed; treat as dead until tape proves otherwise.",
        )
        seen.add(m.get("cite_id"))

    if short_marks:
        _add(
            {
                "cite_id": f"short_n={len(short_marks)}",
                "contract": "CSP/CC short-premium bucket",
                "handle": "book",
                "peak_pct": None,
                "ask_pct": None,
                "status": "BUCKET",
            },
            "parked",
            f"{len(short_marks)} sold-premium cites parked off long peak win_50 — need credit/retention metrics later, not max-gain %.",
        )

    return out[:16]




def load_handles(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Per-handle dossier (followers + experience_tier). Missing file / nulls OK."""
    path = path or DEFAULT_HANDLES
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text())
    except Exception:
        return {}
    raw = doc.get("handles") or {}
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict) and row.get("handle"):
                out[row["handle"]] = row
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                row = dict(v)
                row.setdefault("handle", k)
                out[k] = row
    return out


def merge_handle_meta(row: Dict[str, Any], dossier: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Attach followers / experience_* from handles.json (additive)."""
    h = row.get("handle")
    meta = dossier.get(h or "") or {}
    row = dict(row)
    row["followers"] = meta.get("followers")
    row["followers_as_of_et"] = meta.get("followers_as_of_et")
    row["experience_tier"] = meta.get("experience_tier") or "unknown"
    row["experience_why"] = meta.get("experience_why") or ""
    return row


_CONTRACT_EXP_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})\s*$")


def parse_expiry_date(row: Dict[str, Any]) -> Optional[str]:
    exp = row.get("expiry")
    if exp:
        return str(exp)[:10]
    contract = str(row.get("contract") or "")
    m = _CONTRACT_EXP_RE.search(contract)
    return m.group(1) if m else None


def dte_days(row: Dict[str, Any]) -> Optional[int]:
    """Calendar DTE at cite time (expiry date − cited date)."""
    cited = str(row.get("cited_et") or "")[:10]
    exp = parse_expiry_date(row)
    if not cited or not exp:
        return None
    try:
        c = datetime.strptime(cited, "%Y-%m-%d").date()
        e = datetime.strptime(exp, "%Y-%m-%d").date()
        return (e - c).days
    except ValueError:
        return None


def dte_bucket(dte: Optional[int]) -> Optional[str]:
    """short ≤14 · mid 15–90 · long >90."""
    if dte is None:
        return None
    if dte <= 14:
        return "short"
    if dte <= 90:
        return "mid"
    return "long"


def compute_horizon(marks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Dominant DTE bucket; mixed if no bucket ≥60% of known-DTE rows."""
    mix = {"short": 0, "mid": 0, "long": 0}
    dtes: List[int] = []
    for m in marks:
        d = dte_days(m)
        b = dte_bucket(d)
        if b is None or d is None:
            continue
        mix[b] += 1
        dtes.append(d)
    n = sum(mix.values())
    if n == 0:
        return {
            "horizon": "mixed",
            "horizon_n": 0,
            "horizon_mix": mix,
            "median_dte": None,
        }
    horizon = "mixed"
    for name in ("short", "mid", "long"):
        if mix[name] / n >= 0.60:
            horizon = name
            break
    dtes_sorted = sorted(dtes)
    mid = len(dtes_sorted) // 2
    median = (
        dtes_sorted[mid]
        if len(dtes_sorted) % 2
        else round((dtes_sorted[mid - 1] + dtes_sorted[mid]) / 2)
    )
    return {
        "horizon": horizon,
        "horizon_n": n,
        "horizon_mix": mix,
        "median_dte": median,
    }


def _fmt_signed_pct(x: Any) -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    return f"{v:+.0f}%"


def summarize_past(hmarks: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
    """Scored / expired summary (peak ≠ expiry)."""
    scored = [
        m for m in hmarks
        if m.get("first_ask") is not None and m.get("win_50") is not None
    ]
    expired = [m for m in hmarks if str(m.get("status") or "").upper() == "EXPIRED"]
    early = sum(1 for m in scored if m.get("early_vs_expiry"))
    n = stats.get("n")
    if n is None:
        n = len(scored)
    w50 = stats.get("win_50")
    w50_s = "n/a" if w50 is None else f"{round(w50 * 100)}%"
    return (
        f"scored n={n} · expired {len(expired)} · peak win_50 {w50_s} · "
        f"avg peak {_fmt_signed_pct(stats.get('avg_peak_pct'))} · "
        f"avg exp {_fmt_signed_pct(stats.get('avg_expiry_pct'))} · "
        f"early≠exp {early}"
    )


def summarize_current(hmarks: List[Dict[str, Any]]) -> str:
    """LIVE book snapshot."""
    live = [m for m in hmarks if str(m.get("status") or "").upper() == "LIVE"]
    if not live:
        return "no LIVE marks"
    now_vals = [m["ask_pct"] for m in live if m.get("ask_pct") is not None]
    peak_vals = [m["peak_pct"] for m in live if m.get("peak_pct") is not None]
    avg_now = round(sum(now_vals) / len(now_vals), 1) if now_vals else None
    avg_peak = round(sum(peak_vals) / len(peak_vals), 1) if peak_vals else None
    return (
        f"{len(live)} LIVE · avg now {_fmt_signed_pct(avg_now)} · "
        f"peak so far {_fmt_signed_pct(avg_peak)}"
    )


def summarize_potential(
    horizon: str,
    stats: Dict[str, Any],
    dossier: Optional[Dict[str, Any]] = None,
    shortlist_label: Optional[str] = None,
) -> str:
    """Style if watched — accountability framing, never trade advice."""
    bits: List[str] = []
    if horizon == "short":
        bits.append("short-DTE style (≤14) — peaks print fast; expiry often fails")
    elif horizon == "mid":
        bits.append("mid-horizon (15–90 DTE) book")
    elif horizon == "long":
        bits.append("longer-dated (>90 DTE) book")
    else:
        bits.append("mixed DTE — no bucket ≥60%")

    avg_peak = stats.get("avg_peak_pct")
    avg_exp = stats.get("avg_expiry_pct")
    if avg_peak is not None and avg_exp is not None and avg_peak >= 50 and avg_exp < 0:
        bits.append("peak≠hold pattern — early peaks, weak expiry path")
    elif avg_exp is not None and avg_exp >= 0:
        bits.append("expiry path more durable than pure peak printers")

    if shortlist_label == "peak_printer":
        bits.append("if watched: track peak prints, not hold-to-expiry")
    elif shortlist_label == "hold_candidate":
        bits.append("if watched: compare hold-to-expiry vs peak separately")
    elif shortlist_label == "avoid":
        bits.append("if watched: fade optics — rates lag the book")

    why = (dossier or {}).get("experience_why") or ""
    if why and "not skimmed" not in why.lower():
        bits.append(why)
    bits.append("accountability only — not trade advice")
    return " · ".join(bits)


def cos_eval_for_handle(
    *,
    shortlist_label: Optional[str],
    n: int,
    win_50: Optional[float],
    book_w50: Optional[float],
    flags: Optional[Dict[str, Any]] = None,
    horizon: str = "mixed",
) -> Dict[str, str]:
    """CoS accountability eval: follow | watch | skip (+ why). Not trade advice."""
    flags = flags or {}
    short_n = flags.get("short_premium_excluded") or 0
    hind_n = flags.get("hindsight_cites") or 0

    if shortlist_label == "avoid" or (
        n >= 5 and win_50 is not None and book_w50 is not None and win_50 < book_w50 - 0.20
    ):
        return {
            "cos_eval": "skip",
            "cos_why": (
                f"win_50 lags book on n={n} — deprioritize harvest "
                f"(accountability fade, not a trade call)"
            ),
        }
    if n <= 0 and hind_n:
        return {
            "cos_eval": "skip",
            "cos_why": "hindsight / contaminated only — out of headline",
        }
    if short_n >= 5 and (n or 0) <= 2:
        return {
            "cos_eval": "skip",
            "cos_why": "CSP/CC-heavy park — short-premium off long peak path",
        }
    if shortlist_label == "hold_candidate" and n >= 3:
        return {
            "cos_eval": "follow",
            "cos_why": (
                f"hold_candidate · {horizon} · n={n} — thicken before crowning; "
                f"peak≠expiry still shown"
            ),
        }
    if shortlist_label == "peak_printer" and n >= 3:
        return {
            "cos_eval": "follow",
            "cos_why": (
                f"peak_printer · {horizon} · n={n} — watch peak path; "
                f"do not treat expiry as the score"
            ),
        }
    if shortlist_label in ("thin_sample", None) or n < 3:
        return {
            "cos_eval": "watch",
            "cos_why": f"thin n={n} · {horizon} — gather more clean scored rows before follow",
        }
    if shortlist_label == "peak_printer":
        return {
            "cos_eval": "watch",
            "cos_why": f"peak_printer but thin · {horizon} — deepen sample",
        }
    return {
        "cos_eval": "watch",
        "cos_why": f"keep sampling · {horizon} · n={n}",
    }


def build_handle_story(
    hmarks: List[Dict[str, Any]],
    stats: Dict[str, Any],
    overall: Dict[str, Any],
    *,
    shortlist_label: Optional[str] = None,
    dossier: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Horizon + past/current/potential + cos_eval for one handle."""
    hz = compute_horizon(hmarks)
    label = shortlist_label
    past = summarize_past(hmarks, stats)
    current = summarize_current(hmarks)
    potential = summarize_potential(hz["horizon"], stats, dossier, label)
    cos = cos_eval_for_handle(
        shortlist_label=label,
        n=int(stats.get("n") or 0),
        win_50=stats.get("win_50"),
        book_w50=overall.get("win_50"),
        flags=stats.get("flags") or {},
        horizon=hz["horizon"],
    )
    return {
        **hz,
        "past": past,
        "current": current,
        "potential": potential,
        **cos,
    }


STORY_KEYS = (
    "horizon",
    "horizon_n",
    "horizon_mix",
    "median_dte",
    "past",
    "current",
    "potential",
    "cos_eval",
    "cos_why",
)


def recover_mark_rows_from_scoreboard(sb: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Best-effort mark rows from published scoreboard sections (when marks.json missing)."""
    by_id: Dict[str, Dict[str, Any]] = {}

    def _put(row: Dict[str, Any]) -> None:
        cid = row.get("cite_id")
        if not cid:
            return
        prev = by_id.get(cid, {})
        merged = {**prev, **{k: v for k, v in row.items() if v is not None}}
        by_id[cid] = merged

    for r in sb.get("live_board") or []:
        _put({**r, "status": r.get("status") or "LIVE"})
    for r in sb.get("graveyard_top10") or []:
        _put({**r, "status": r.get("status") or "EXPIRED"})
    for r in (sb.get("contaminated") or {}).get("rows") or []:
        _put({**r, "hindsight_flag": True})
    for r in (sb.get("short_premium") or {}).get("rows") or []:
        _put(dict(r))
    for r in sb.get("feasibility") or []:
        _put(dict(r))
    return list(by_id.values())


def attach_handle_stories(
    sb: Dict[str, Any],
    marks_by_handle: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    dossier: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Attach horizon / past / current / potential / cos_eval onto leaderboard + shortlist."""
    dossier = dossier if dossier is not None else load_handles()
    overall = sb.get("overall") or {}
    if marks_by_handle is None:
        marks_by_handle = {}
        for m in recover_mark_rows_from_scoreboard(sb):
            marks_by_handle.setdefault(m.get("handle") or "unknown", []).append(m)

    label_by_handle = {
        r.get("handle"): r.get("label")
        for r in (sb.get("follow_shortlist") or [])
        if r.get("handle")
    }

    for row in sb.get("leaderboard") or []:
        handle = row.get("handle") or "unknown"
        hmarks = marks_by_handle.get(handle) or []
        story = build_handle_story(
            hmarks,
            row,
            overall,
            shortlist_label=label_by_handle.get(handle),
            dossier=dossier.get(handle),
        )
        row.update(story)

    lb_by = {r.get("handle"): r for r in (sb.get("leaderboard") or [])}
    for row in sb.get("follow_shortlist") or []:
        handle = row.get("handle") or "unknown"
        src = lb_by.get(handle)
        if src:
            for k in STORY_KEYS:
                if k in src:
                    row[k] = src[k]
            continue
        hmarks = marks_by_handle.get(handle) or []
        story = build_handle_story(
            hmarks,
            row,
            overall,
            shortlist_label=row.get("label"),
            dossier=dossier.get(handle),
        )
        row.update(story)

    for row in sb.get("hot_streaks") or []:
        handle = row.get("handle")
        if not handle:
            continue
        src = lb_by.get(handle)
        if not src:
            continue
        for k in ("horizon", "cos_eval", "past", "current"):
            if k in src:
                row[k] = src[k]

    sb["version"] = max(int(sb.get("version") or 4), 5)
    notes = list(sb.get("notes") or [])
    note = "Handle stories: horizon (short≤14 / mid 15–90 / long>90 / mixed) + past/current/potential + cos_eval."
    if note not in notes:
        notes.append(note)
    sb["notes"] = notes
    return sb


def build_follow_shortlist(
    leaderboard: List[Dict[str, Any]],
    overall: Dict[str, Any],
    unscored_by_handle: Dict[str, int],
    early_by_handle: Dict[str, int],
    dossier: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Decision-ready handles for Ty (social accountability follow — not trade advice)."""
    book_w50 = overall.get("win_50")
    dossier = dossier or {}
    out: List[Dict[str, Any]] = []
    for row in leaderboard:
        n = row.get("n") or 0
        if n <= 0 and not (row.get("flags") or {}).get("hindsight_cites"):
            continue
        if n <= 0:
            continue
        handle = row.get("handle") or "unknown"
        w50 = row.get("win_50")
        avg_peak = row.get("avg_peak_pct")
        avg_exp = row.get("avg_expiry_pct")
        early_n = early_by_handle.get(handle, (row.get("flags") or {}).get("early_vs_expiry") or 0)
        skips = unscored_by_handle.get(handle, 0)
        streak = row.get("current_streak_label") or "flat"

        # Labels for Ty follow decisions (not trade advice). n<3 always thin.
        thicken = " · thicken n before crowning" if n < 10 else ""
        label = "thin_sample"
        why = f"n={n} thin — thicken before crowning"

        # avoid: well below book with enough sample
        if (
            n >= 5
            and w50 is not None
            and book_w50 is not None
            and w50 < (book_w50 - 0.20)
        ):
            label = "avoid"
            why = (
                f"win_50 {round(w50*100)}% ≪ book {round(book_w50*100)}% on n={n} "
                f"(avg peak {avg_peak}% · avg exp {avg_exp}%)"
            )
        elif n < 3:
            label = "thin_sample"
            why = (
                f"thin n={n} · win_50 {None if w50 is None else round(w50*100)}% · "
                f"avg peak {avg_peak}% · avg exp {avg_exp}% · streak {streak}"
            )
        elif avg_exp is not None and avg_exp >= 0 and w50 is not None and w50 >= 0.4:
            label = "hold_candidate"
            why = (
                f"avg expiry {avg_exp}% solid with win_50 {round(w50*100)}% "
                f"(avg peak {avg_peak}%) · streak {streak}{thicken}"
            )
        elif (
            w50 is not None
            and w50 >= 0.5
            and (
                avg_exp is None
                or avg_exp < -40
                or (early_n and early_n >= max(1, int(0.4 * n)))
            )
        ) or (
            avg_peak is not None
            and avg_peak >= 50
            and w50 is not None
            and w50 >= 0.5
        ):
            label = "peak_printer"
            why = (
                f"peak printer — avg peak {avg_peak}% · avg exp {avg_exp}% · "
                f"early≠exp {early_n} · streak {streak} (peak ≠ hold){thicken}"
            )
        else:
            label = "thin_sample" if n < 5 else (
                "avoid" if (w50 is not None and book_w50 is not None and w50 < book_w50 - 0.10) else "peak_printer"
            )
            why = (
                f"win_50 {None if w50 is None else round(w50*100)}% · "
                f"avg peak {avg_peak}% · avg exp {avg_exp}% · n={n} · streak {streak}{thicken}"
            )

        meta = dossier.get(handle) or {}
        out.append({
            "handle": handle,
            "platform": row.get("platform"),
            "handle_label": row.get("handle_label") or handle,
            "n": n,
            "win_50": w50,
            "avg_peak_pct": avg_peak,
            "avg_expiry_pct": avg_exp,
            "median_peak_pct": row.get("median_peak_pct"),
            "streak": streak,
            "early_vs_expiry_n": early_n,
            "unscored_skips": skips,
            "label": label,
            "why": why,
            "followers": meta.get("followers"),
            "followers_as_of_et": meta.get("followers_as_of_et"),
            "experience_tier": meta.get("experience_tier") or "unknown",
            "experience_why": meta.get("experience_why") or "",
        })

    label_rank = {"hold_candidate": 0, "peak_printer": 1, "thin_sample": 2, "avoid": 3}
    out.sort(
        key=lambda r: (
            label_rank.get(r["label"], 9),
            -(r["win_50"] if r["win_50"] is not None else -1),
            -(r["avg_peak_pct"] if r["avg_peak_pct"] is not None else -999),
            -(r["n"] or 0),
        )
    )
    return out[:15]


def build_scoreboard(marks_path: Path, cites_path: Path = DEFAULT_CITES) -> Dict[str, Any]:
    marks_doc = json.loads(marks_path.read_text())
    marks: List[Dict[str, Any]] = join_cites(marks_doc.get("marks", []), cites_path)

    # Headline excludes hindsight + CSP/CC short-premium (RULES.md)
    contaminated = [m for m in marks if m.get("hindsight_flag")]
    non_hindsight = [m for m in marks if not m.get("hindsight_flag")]
    short_premium = [m for m in non_hindsight if is_short_premium(m)]
    clean = [m for m in non_hindsight if not is_short_premium(m)]  # long peak path

    overall = rate_block(clean)
    overall_streaks = streak_stats(ordered_win50(clean))
    contaminated_block = rate_block(contaminated)
    short_block = rate_block(short_premium)
    short_streaks = streak_stats(ordered_win50(short_premium))

    by_handle: Dict[str, List[Dict[str, Any]]] = {}
    short_by_handle: Dict[str, int] = {}
    for m in short_premium:
        short_by_handle[m.get("handle") or "unknown"] = short_by_handle.get(m.get("handle") or "unknown", 0) + 1
    for m in clean:
        by_handle.setdefault(m.get("handle") or "unknown", []).append(m)

    leaderboard = []
    for handle, hmarks in by_handle.items():
        block = rate_block(hmarks)
        streaks = streak_stats(ordered_win50(hmarks))
        plat = next((m.get("platform") for m in hmarks if m.get("platform")), None)
        hlab = next((m.get("handle_label") for m in hmarks if m.get("handle_label")), None)
        if not hlab and handle:
            hlab = f"{handle} · {plat}" if plat else handle
        leaderboard.append({
            "handle": handle,
            "platform": plat,
            "handle_label": hlab,
            **block,
            **streaks,
            "flags": {
                "hindsight_cites": 0,
                "unmarked": sum(1 for m in hmarks if m.get("status") == "UNMARKED"),
                "expired": sum(1 for m in hmarks if m.get("status") == "EXPIRED"),
                "early_vs_expiry": sum(1 for m in hmarks if m.get("early_vs_expiry")),
                "short_premium_excluded": short_by_handle.get(handle, 0),
            },
        })
    # Contaminated cites still counted toward handle hindsight flags (not rates)
    for m in contaminated:
        h = m.get("handle") or "unknown"
        for row in leaderboard:
            if row["handle"] == h:
                row["flags"]["hindsight_cites"] += 1
                break
        else:
            leaderboard.append({
                "handle": h,
                **rate_block([]),
                **streak_stats([]),
                "flags": {
                    "hindsight_cites": 1,
                    "unmarked": 0,
                    "expired": 1 if m.get("status") == "EXPIRED" else 0,
                    "early_vs_expiry": 0,
                },
            })
    leaderboard.sort(
        key=lambda r: (r["win_50"] is not None, r["win_50"] or 0, r["n"]),
        reverse=True,
    )
    dossier = load_handles()
    leaderboard = [merge_handle_meta(r, dossier) for r in leaderboard]

    def _row(m: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "contract": m.get("contract"),
            "first_ask": m.get("first_ask"),
            "now_ask": m.get("now_ask"),
            "ask_pct": m.get("ask_pct"),
            "peak_ask": m.get("peak_ask"),
            "peak_pct": m.get("peak_pct"),
            "time_to_peak_et": m.get("time_to_peak_et"),
            "exit_ask": m.get("exit_ask"),
            "exit_pct": m.get("exit_pct"),
            "expiry_ask": m.get("expiry_ask"),
            "expiry_pct": m.get("expiry_pct"),
            "win_50": m.get("win_50"),
            "hold_expiry_win": m.get("hold_expiry_win"),
            "early_vs_expiry": m.get("early_vs_expiry"),
            "cited_et": m.get("cited_et"),
            "handle": m.get("handle"),
            "platform": m.get("platform"),
            "handle_label": m.get("handle_label") or (
                f"{m.get('handle')} · {m.get('platform')}" if m.get("handle") and m.get("platform") else m.get("handle")
            ),
            "status": m.get("status"),
            "feed": m.get("feed"),
            "peak_source": m.get("peak_source") or m.get("peak_feed"),
            "cite_id": m.get("cite_id"),
        }

    live = [_row(m) for m in marks if m.get("status") == "LIVE"]
    live.sort(key=lambda r: abs(r["peak_pct"] if r["peak_pct"] is not None else r["ask_pct"] or 0), reverse=True)
    graveyard = [_row(m) for m in marks if m.get("status") in ("GRAVEYARD", "EXPIRED")]
    graveyard.sort(key=lambda r: abs(r["peak_pct"] or r["ask_pct"] or 0), reverse=True)

    def _contam_row(m: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "cite_id": m.get("cite_id"),
            "contract": m.get("contract"),
            "handle": m.get("handle"),
            "cited_et": m.get("cited_et"),
            "peak_pct": m.get("peak_pct"),
            "expiry_pct": m.get("expiry_pct"),
            "win_50": m.get("win_50"),
            "status": m.get("status"),
            "reason": "hindsight_flag",
            "peak_source": m.get("peak_source") or m.get("peak_feed"),
            "feed": m.get("feed"),
        }

    def _short_row(m: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "cite_id": m.get("cite_id"),
            "handle": m.get("handle"),
            "contract": m.get("contract"),
            "cited_et": m.get("cited_et"),
            "peak_pct": m.get("peak_pct"),
            "ask_pct": m.get("ask_pct"),
            "expiry_pct": m.get("expiry_pct"),
            "status": m.get("status"),
        }

    # Per-handle unscored skips (v1.1 pending / no cite-time path) — streak optics caveat
    unscored_by_handle: Dict[str, int] = {}
    early_by_handle: Dict[str, int] = {}
    for m in clean:
        h = m.get("handle") or "unknown"
        if m.get("win_50") is None:
            unscored_by_handle[h] = unscored_by_handle.get(h, 0) + 1
        if m.get("early_vs_expiry"):
            early_by_handle[h] = early_by_handle.get(h, 0) + 1

    hot = []
    caveat = "scored rows only · peak ≠ hold"
    # Book hot: current streak ≥3W
    if overall_streaks.get("current_streak", 0) >= 3:
        hot.append({
            "scope": "book",
            "handle": None,
            "handle_label": "BOOK",
            "streak": overall_streaks["current_streak_label"],
            "n": overall.get("n"),
            "win_50": overall.get("win_50"),
            "avg_peak_pct": overall.get("avg_peak_pct"),
            "avg_expiry_pct": overall.get("avg_expiry_pct"),
            "median_peak_pct": overall.get("median_peak_pct"),
            "early_vs_expiry_n": sum(1 for m in clean if m.get("early_vs_expiry")),
            "unscored_skips": sum(1 for m in clean if m.get("win_50") is None),
            "caveat": caveat,
            "why": "book-wide peak win_50 streak ≥3W",
        })
    # Per-handle hot: current ≥2W with n≥2, or win_50≥50% with n≥3
    for row in leaderboard:
        cs = row.get("current_streak") or 0
        n = row.get("n") or 0
        w50 = row.get("win_50")
        handle = row.get("handle") or "unknown"
        label = row.get("handle_label") or handle
        base = {
            "handle": row.get("handle"),
            "handle_label": label,
            "platform": row.get("platform"),
            "streak": row.get("current_streak_label"),
            "n": n,
            "win_50": w50,
            "wins_50": row.get("wins_50"),
            "avg_peak_pct": row.get("avg_peak_pct"),
            "avg_expiry_pct": row.get("avg_expiry_pct"),
            "median_peak_pct": row.get("median_peak_pct"),
            "early_vs_expiry_n": early_by_handle.get(handle, 0),
            "unscored_skips": unscored_by_handle.get(handle, 0),
            "caveat": caveat,
            "followers": row.get("followers"),
            "experience_tier": row.get("experience_tier") or "unknown",
            "experience_why": row.get("experience_why") or "",
        }
        if cs >= 2 and n >= 2:
            hot.append({
                **base,
                "scope": "handle",
                "why": f"{label} on a {row.get('current_streak_label')} peak streak ({caveat})",
            })
        elif w50 is not None and w50 >= 0.5 and n >= 3 and cs < 2:
            hot.append({
                **base,
                "scope": "handle_rate",
                "why": f"{label} hot rate {round(w50*100)}% on n={n} ({caveat})",
            })
    seen = set()
    deduped = []
    for h in hot:
        key = h.get("handle") or h.get("scope")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    hot = deduped

    feasibility = build_feasibility(clean, short_premium, contaminated)
    follow_shortlist = build_follow_shortlist(
        leaderboard, overall, unscored_by_handle, early_by_handle, dossier
    )

    sb = {
        "version": 5,
        "rules_ref": "RULES.md v1.1",
        "updated_et": now_et_str(),
        "disclaimer": "Accountability only — social ≠ trade signal. Peak ≠ expiry. No CLEAR tickets. Hindsight excluded from headline.",
        "overall": {
            **overall,
            **overall_streaks,
            "headline": "peak win_50 / clean LONG cites (CSP/CC short-premium excluded)",
            "hold_expiry_headline": "hold_expiry_win / clean long cites with expiry_pct",
            "early_exit_headline": "peak win_50 & expiry_pct≤0 / clean long with both",
            "excluded_hindsight_n": len(contaminated),
            "excluded_short_premium_n": len(short_premium),
        },
        "contaminated": {
            **contaminated_block,
            "bucket": "hindsight_flag=true",
            "rows": [_contam_row(m) for m in contaminated],
        },
        "short_premium": {
            **short_block,
            **short_streaks,
            "bucket": "CSP/CC short-premium",
            "cite_ids": [m.get("cite_id") for m in short_premium],
            "note": "Peak% path is long-option max-gain; short premium needs credit/retention metrics — do not mix into headline peak win_50.",
            "rows": [_short_row(m) for m in short_premium],
        },
        "leaderboard": leaderboard,
        "live_board": live[:25],
        "graveyard_top10": graveyard[:10],
        "hot_streaks": hot,
        "follow_shortlist": follow_shortlist,
        "feasibility": feasibility,
        "mark_count": len(marks),
        "marks_updated_et": marks_doc.get("updated_et"),
        "last_peak_refresh_et": marks_doc.get("last_peak_refresh_et"),
        "notes": [
            f"marks republish: long clean n={overall['n']}, peak win_50={overall['win_50']}, streak={overall_streaks['current_streak_label']}.",
            f"Short-premium n={len(short_premium)} excluded from headline.",
            "No hot streak." if not hot else f"Hot streaks: {len(hot)} — " + ", ".join((h.get("handle_label") or h.get("scope","")) + " " + str(h.get("streak") or "") for h in hot[:6]),
            "Peak sources: yahoo_daily_high / chartexchange_eod_high overwrite CBOE only when labeled and strictly higher (RULES v1.1).",
        ],
    }
    return attach_handle_stories(sb, by_handle, dossier)


def _fmt_rate(r) -> str:
    if r is None:
        return "n/a"
    return f"{r * 100:.1f}%"


def render_markdown(sb: Dict[str, Any]) -> str:
    o = sb["overall"]
    lines = [
        "# Call Scoreboard (RULES v1.1)",
        "",
        f"_Updated {sb['updated_et']} ET · {sb['disclaimer']}_",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Sample (n, clean LONG) | **{o['n']}** ({o['confidence']}) · hindsight excl {o.get('excluded_hindsight_n', 0)} · short-prem excl {o.get('excluded_short_premium_n', 0)} |",
        f"| **Hit rate (peak win_50)** | **{_fmt_rate(o['win_50'])}** ({o['wins_50']}/{o['n']}) |",
        f"| win_2x / win_3x (peak) | {_fmt_rate(o['win_2x'])} / {_fmt_rate(o['win_3x'])} |",
        f"| **Hold-to-expiry hit rate** | **{_fmt_rate(o['hold_expiry_hit_rate'])}** ({o['hold_expiry_wins']}/{o['hold_expiry_n']}) |",
        f"| **Early-exit opportunity** | **{_fmt_rate(o['early_exit_opp_rate'])}** ({o['early_exit_opp_count']}/{o['early_exit_opp_n']}) |",
        f"| Current streak (peak) | **{o['current_streak_label']}** |",
        f"| Longest win / loss | {o['longest_win_streak']}W / {o['longest_loss_streak']}L |",
        f"| Avg / median peak% | {o.get('avg_peak_pct')} / {o.get('median_peak_pct')} |",
        f"| Avg / median expiry% | {o.get('avg_expiry_pct')} / {o.get('median_expiry_pct')} |",
        "",
        "## Contaminated (hindsight — not in headline)",
        "",
        f"| Contaminated n | {sb.get('contaminated', {}).get('n', 0)} | peak win_50 {_fmt_rate(sb.get('contaminated', {}).get('win_50'))} |",
        "",
        "| Cite | Contract | Peak% | Handle |",
        "|------|----------|-------|--------|",
    ]
    for r in sb.get("contaminated", {}).get("rows", []):
        lines.append(
            f"| {r.get('cite_id')} | {r.get('contract')} | {r.get('peak_pct')} | {r.get('handle')} |"
        )
    lines += [
        "",
        "## Leaderboard (clean cites only)",
        "",
        "| Handle | n | peak win_50 | avg peak% | avg exp% | horizon | cos | streak | conf |",
        "|--------|---|-------------|-----------|----------|---------|-----|--------|------|",
    ]
    for r in sb["leaderboard"]:
        lines.append(
            f"| {r['handle']} | {r['n']} | {_fmt_rate(r['win_50'])} | "
            f"{r.get('avg_peak_pct')} | {r.get('avg_expiry_pct')} | "
            f"{r.get('horizon')} | {r.get('cos_eval')} | "
            f"{r['current_streak_label']} | {r['confidence']} |"
        )
    # rewrite leaderboard header columns
    lines += [
        "",
        "## Follow shortlist (decision view)",
        "",
        "| Handle | label | cos | horizon | n | win_50 | avg peak% | avg exp% | followers | xp | why |",
        "|--------|-------|-----|---------|---|--------|-----------|----------|-----------|----|-----|",
    ]
    for r in sb.get("follow_shortlist", []):
        lines.append(
            f"| {r.get('handle')} | {r.get('label')} | {r.get('cos_eval')} | {r.get('horizon')} | "
            f"{r.get('n')} | {_fmt_rate(r.get('win_50'))} | "
            f"{r.get('avg_peak_pct')} | {r.get('avg_expiry_pct')} | {r.get('followers')} | "
            f"{r.get('experience_tier')} | {r.get('why')} |"
        )
    lines += [
        "",
        "### Shortlist stories (past · current · potential)",
        "",
    ]
    for r in sb.get("follow_shortlist", []):
        lines.append(f"- **{r.get('handle')}** · `{r.get('cos_eval')}` · horizon `{r.get('horizon')}`")
        lines.append(f"  - past: {r.get('past')}")
        lines.append(f"  - current: {r.get('current')}")
        lines.append(f"  - potential: {r.get('potential')}")
        lines.append(f"  - cos: {r.get('cos_why')}")
    lines += [
        "",
        "## Live (peak vs now)",
        "",
        "| Contract | Peak% | Now% | Expiry% | Exit% | Handle |",
        "|----------|-------|------|---------|-------|--------|",
    ]
    for r in sb["live_board"]:
        lines.append(
            f"| {r['contract']} | {r['peak_pct']} | {r['ask_pct']} | "
            f"{r['expiry_pct']} | {r['exit_pct']} | {r['handle']} |"
        )
    lines += [
        "",
        "## Graveyard / expired (peak can still be a win)",
        "",
        "| Contract | Peak% | Expiry% | Early? | Status | Handle |",
        "|----------|-------|---------|--------|--------|--------|",
    ]
    for r in sb["graveyard_top10"]:
        early = "YES" if r.get("early_vs_expiry") else ""
        lines.append(
            f"| {r['contract']} | {r['peak_pct']} | {r['expiry_pct']} | "
            f"{early} | {r['status']} | {r['handle']} |"
        )
    lines += ["", "---", "_Peak ≠ expiry. Interrogate, don't copy._", ""]
    return "\n".join(lines)


def republish_dashboard(sb: Dict[str, Any], dash_dir: Path = ROOT / "dashboard") -> None:
    """Hit Rate owns phone board republish: scoreboard.json + inline fallback."""
    dash_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(sb, indent=2) + "\n"
    (dash_dir / "scoreboard.json").write_text(payload)
    html_path = dash_dir / "index.html"
    if not html_path.exists():
        return
    html = html_path.read_text()
    inline = json.dumps(sb, separators=(",", ":"), ensure_ascii=False)
    new_html, n = re.subn(
        r"window\.__SCOREBOARD__ = \{.*?\};",
        "window.__SCOREBOARD__ = " + inline + ";",
        html,
        count=1,
        flags=re.S,
    )
    if n:
        html_path.write_text(new_html)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Hit rate + streaks (RULES v1.1)")
    ap.add_argument("--marks", type=Path, default=DEFAULT_MARKS)
    ap.add_argument("--cites", type=Path, default=DEFAULT_CITES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip republishing dashboard/scoreboard.json + inline embed",
    )
    args = ap.parse_args(argv)

    if not args.marks.exists():
        print(f"Missing marks: {args.marks}", file=sys.stderr)
        return 1

    try:
        marks_doc = json.loads(args.marks.read_text())
    except json.JSONDecodeError as e:
        print(f"Invalid marks JSON: {args.marks}: {e}", file=sys.stderr)
        return 1
    if not isinstance(marks_doc, dict) or "marks" not in marks_doc:
        print(
            f"marks.json must be an object with a 'marks' array: {args.marks}",
            file=sys.stderr,
        )
        return 1

    sb = build_scoreboard(args.marks, args.cites)
    args.out.write_text(json.dumps(sb, indent=2) + "\n")
    args.md.write_text(render_markdown(sb))
    if not args.no_dashboard:
        republish_dashboard(sb)
    o = sb["overall"]
    sp = sb.get("short_premium", {})
    fl = sb.get("follow_shortlist") or []
    print(
        f"Scoreboard → {args.out} | v{sb.get('version')} "
        f"LONG {o['n']} {_fmt_rate(o['win_50'])} {o['current_streak_label']} "
        f"SHORT {sp.get('n', 0)} "
        f"hold_exp={_fmt_rate(o['hold_expiry_hit_rate'])} "
        f"early_opp={_fmt_rate(o['early_exit_opp_rate'])} "
        f"follow_shortlist={len(fl)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
