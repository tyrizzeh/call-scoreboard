#!/usr/bin/env python3
"""Hit Rate + streaks from Mark Desk marks (RULES.md v1).

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
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKS = ROOT / "marks.json"
DEFAULT_CITES = ROOT / "cites.json"
DEFAULT_OUT = ROOT / "scoreboard.json"
DEFAULT_MD = ROOT / "scoreboard.md"


def _contract_label(cite: Dict[str, Any]) -> str:
    und = cite.get("underlying")
    side = cite.get("side")
    strike = cite.get("strike")
    exp = cite.get("expiry")
    if und and side and strike is not None and exp:
        return f"{und} {strike}{side} {exp}"
    return ""


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
            label = _contract_label(c)
            if label:
                row["contract"] = label
            elif not row.get("contract"):
                row["contract"] = row.get("occ")
        out.append(row)
    return out


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
        "median_peak_pct": _median(peaks),
        "median_expiry_pct": _median(exps),
        "confidence": confidence(n),
    }


def ordered_win50(marks: List[Dict[str, Any]]) -> List[Optional[bool]]:
    sorted_m = sorted(marks, key=lambda m: m.get("cited_et") or "")
    out: List[Optional[bool]] = []
    for m in sorted_m:
        if m.get("first_ask") is None or m.get("win_50") is None:
            out.append(None)
        else:
            out.append(bool(m["win_50"]))
    return out


def build_scoreboard(marks_path: Path, cites_path: Path = DEFAULT_CITES) -> Dict[str, Any]:
    marks_doc = json.loads(marks_path.read_text())
    marks: List[Dict[str, Any]] = join_cites(marks_doc.get("marks", []), cites_path)

    # Headline excludes hindsight_flag=true (contaminated bucket separate)
    clean = [m for m in marks if not m.get("hindsight_flag")]
    contaminated = [m for m in marks if m.get("hindsight_flag")]

    overall = rate_block(clean)
    overall_streaks = streak_stats(ordered_win50(clean))
    contaminated_block = rate_block(contaminated)

    by_handle: Dict[str, List[Dict[str, Any]]] = {}
    for m in clean:
        by_handle.setdefault(m.get("handle") or "unknown", []).append(m)

    leaderboard = []
    for handle, hmarks in by_handle.items():
        block = rate_block(hmarks)
        streaks = streak_stats(ordered_win50(hmarks))
        leaderboard.append({
            "handle": handle,
            **block,
            **streaks,
            "flags": {
                "hindsight_cites": 0,
                "unmarked": sum(1 for m in hmarks if m.get("status") == "UNMARKED"),
                "expired": sum(1 for m in hmarks if m.get("status") == "EXPIRED"),
                "early_vs_expiry": sum(1 for m in hmarks if m.get("early_vs_expiry")),
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
            "status": m.get("status"),
            "feed": m.get("feed"),
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
        }

    return {
        "version": 2,
        "rules_ref": "RULES.md v1",
        "updated_et": now_et_str(),
        "disclaimer": "Accountability only — social ≠ trade signal. Peak ≠ expiry. No CLEAR tickets. Hindsight excluded from headline.",
        "overall": {
            **overall,
            **overall_streaks,
            "headline": "peak win_50 / clean marked cites (hindsight excluded)",
            "hold_expiry_headline": "hold_expiry_win / clean cites with expiry_pct",
            "early_exit_headline": "peak win_50 & expiry_pct≤0 / clean cites with both peak+expiry",
            "excluded_hindsight_n": len(contaminated),
        },
        "contaminated": {
            **contaminated_block,
            "bucket": "hindsight_flag=true",
            "rows": [_contam_row(m) for m in contaminated],
        },
        "leaderboard": leaderboard,
        "live_board": live[:25],
        "graveyard_top10": graveyard[:10],
        "mark_count": len(marks),
        "marks_updated_et": marks_doc.get("updated_et"),
        "last_peak_refresh_et": marks_doc.get("last_peak_refresh_et"),
    }


def _fmt_rate(r) -> str:
    if r is None:
        return "n/a"
    return f"{r * 100:.1f}%"


def render_markdown(sb: Dict[str, Any]) -> str:
    o = sb["overall"]
    lines = [
        "# Call Scoreboard (RULES v1)",
        "",
        f"_Updated {sb['updated_et']} ET · {sb['disclaimer']}_",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Sample (n, clean) | **{o['n']}** ({o['confidence']}) · hindsight excluded: {o.get('excluded_hindsight_n', 0)} |",
        f"| **Hit rate (peak win_50)** | **{_fmt_rate(o['win_50'])}** ({o['wins_50']}/{o['n']}) |",
        f"| win_2x / win_3x (peak) | {_fmt_rate(o['win_2x'])} / {_fmt_rate(o['win_3x'])} |",
        f"| **Hold-to-expiry hit rate** | **{_fmt_rate(o['hold_expiry_hit_rate'])}** ({o['hold_expiry_wins']}/{o['hold_expiry_n']}) |",
        f"| **Early-exit opportunity** | **{_fmt_rate(o['early_exit_opp_rate'])}** ({o['early_exit_opp_count']}/{o['early_exit_opp_n']}) |",
        f"| Current streak (peak) | **{o['current_streak_label']}** |",
        f"| Longest win / loss | {o['longest_win_streak']}W / {o['longest_loss_streak']}L |",
        f"| Median peak% / expiry% | {o.get('median_peak_pct')} / {o.get('median_expiry_pct')} |",
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
        "| Handle | n | peak win_50 | hold-exp | early-opp | streak | conf |",
        "|--------|---|-------------|----------|-----------|--------|------|",
    ]
    for r in sb["leaderboard"]:
        lines.append(
            f"| {r['handle']} | {r['n']} | {_fmt_rate(r['win_50'])} | "
            f"{_fmt_rate(r['hold_expiry_hit_rate'])} | {_fmt_rate(r['early_exit_opp_rate'])} | "
            f"{r['current_streak_label']} | {r['confidence']} |"
        )
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Hit rate + streaks (RULES v1)")
    ap.add_argument("--marks", type=Path, default=DEFAULT_MARKS)
    ap.add_argument("--cites", type=Path, default=DEFAULT_CITES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    args = ap.parse_args(argv)

    if not args.marks.exists():
        print(f"Missing marks: {args.marks}", file=sys.stderr)
        return 1

    sb = build_scoreboard(args.marks, args.cites)
    args.out.write_text(json.dumps(sb, indent=2) + "\n")
    args.md.write_text(render_markdown(sb))
    o = sb["overall"]
    print(
        f"Scoreboard → {args.out} | peak win_50={_fmt_rate(o['win_50'])} n={o['n']} "
        f"hold_exp={_fmt_rate(o['hold_expiry_hit_rate'])} "
        f"early_opp={_fmt_rate(o['early_exit_opp_rate'])} "
        f"streak={o['current_streak_label']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
