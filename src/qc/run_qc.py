#!/usr/bin/env python3
"""QC the call scoreboard against RULES.md v1 + live JSON schema.

Source of truth (do not invent fields):
  /workspace/call-scoreboard/{RULES.md,cites.json,marks.json,scoreboard.json}

Writes:
  /workspace/scoreboard-qc/reports/qc-YYYYMMDD-HHMM.{md,json}

Exit 1 if any FAIL findings.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]  # /workspace/call-scoreboard
REPORT_DIR = Path("/workspace/scoreboard-qc/reports")

CITE_REQUIRED = [
    "id", "handle", "platform", "post_url", "cited_et", "underlying", "side",
    "strike", "expiry", "cite_ask", "claim_quote", "hindsight_flag", "note",
]
MARK_REQUIRED = [
    "cite_id", "contract", "handle", "first_ask", "now_ask", "ask_pct",
    "peak_ask", "peak_pct", "time_to_peak_et", "exit_ask", "exit_pct",
    "expiry_ask", "expiry_pct", "win_50", "win_2x", "win_3x",
    "hold_expiry_win", "early_vs_expiry", "status", "feed", "hindsight_flag",
]
BOARD_COLS = [
    "contract", "first_ask", "now_ask", "ask_pct", "peak_ask", "peak_pct",
    "time_to_peak_et", "exit_ask", "exit_pct", "expiry_ask", "expiry_pct",
    "win_50", "hold_expiry_win", "early_vs_expiry", "cited_et", "handle",
    "status", "feed",
]
OVERALL_KEYS = [
    "n", "win_50", "win_2x", "win_3x", "wins_50", "wins_2x", "wins_3x",
    "hold_expiry_n", "hold_expiry_hit_rate", "hold_expiry_wins",
    "early_exit_opp_n", "early_exit_opp_rate", "early_exit_opp_count",
    "median_peak_pct", "median_expiry_pct",
    "current_streak", "longest_win_streak", "longest_loss_streak",
    "excluded_hindsight_n",
]

PCT_TOL = 0.02  # rounding noise


def now_et() -> datetime:
    return datetime.now(ET)


def stamp() -> str:
    return now_et().strftime("%Y%m%d-%H%M")


def _load(path: Path) -> Any:
    return json.loads(path.read_text())


def _pct(ask: Optional[float], first: Optional[float]) -> Optional[float]:
    if ask is None or first is None or first == 0:
        return None
    return round((ask - first) / first * 100.0, 2)


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return float(v)
    return None


def _close(a: Optional[float], b: Optional[float], tol: float = PCT_TOL) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _rate_close(a: Any, b: Any, tol: float = 0.00015) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


class Findings:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def add(
        self,
        severity: str,
        file: str,
        id_: Optional[str],
        field: str,
        expected: Any,
        actual: Any,
        rule: str,
        contract: Optional[str] = None,
    ) -> None:
        self.items.append({
            "severity": severity,
            "file": file,
            "id": id_,
            "contract": contract,
            "field": field,
            "expected": expected,
            "actual": actual,
            "rule": rule,
        })

    def counts(self) -> Dict[str, int]:
        out = {"FAIL": 0, "WARN": 0, "INFO": 0}
        for f in self.items:
            out[f["severity"]] = out.get(f["severity"], 0) + 1
        return out


def check_cite_schema(cites: List[Dict], F: Findings) -> None:
    for c in cites:
        cid = c.get("id")
        for k in CITE_REQUIRED:
            if k not in c:
                F.add("FAIL", "cites.json", cid, k, "key present", "missing",
                      "cite required field (CoS schema)")
        # note may be empty string; null is WARN (key present but empty expected as "")
        if "note" in c and c.get("note") is None:
            F.add("WARN", "cites.json", cid, "note", '"" or string', None,
                  "note key should exist; prefer empty string over null")


def check_mark_schema(marks: List[Dict], F: Findings) -> None:
    for m in marks:
        cid = m.get("cite_id")
        contract = m.get("contract")
        for k in MARK_REQUIRED:
            if k not in m:
                F.add("FAIL", "marks.json", cid, k, "key present", "missing",
                      "mark required field (RULES + CoS)", contract=contract)


def check_board_columns(sb: Dict, F: Findings) -> None:
    for board_name in ("live_board", "graveyard_top10"):
        rows = sb.get(board_name) or []
        for i, row in enumerate(rows):
            missing = [c for c in BOARD_COLS if c not in row]
            if missing:
                F.add(
                    "FAIL", "scoreboard.json",
                    f"{board_name}[{i}]",
                    ",".join(missing),
                    "all board columns present",
                    f"missing {missing}",
                    "phone-board columns (CoS)",
                    contract=row.get("contract"),
                )


def check_score_math(marks: List[Dict], F: Findings) -> None:
    for m in marks:
        cid = m.get("cite_id")
        contract = m.get("contract")
        first = _num(m.get("first_ask"))
        peak_pct = _num(m.get("peak_pct"))
        ask_pct = _num(m.get("ask_pct"))
        exit_pct = _num(m.get("exit_pct"))
        expiry_pct = _num(m.get("expiry_pct"))
        peak_ask = _num(m.get("peak_ask"))
        now_ask = _num(m.get("now_ask"))
        exit_ask = _num(m.get("exit_ask"))
        expiry_ask = _num(m.get("expiry_ask"))

        # pct consistency
        for label, ask, pct in (
            ("ask_pct", now_ask, ask_pct),
            ("peak_pct", peak_ask, peak_pct),
            ("exit_pct", exit_ask, exit_pct),
            ("expiry_pct", expiry_ask, expiry_pct),
        ):
            expected = _pct(ask, first)
            if expected is not None and pct is not None and not _close(expected, pct):
                F.add("FAIL", "marks.json", cid, label, expected, pct,
                      f"{label} = round((ask-first_ask)/first_ask*100,2)",
                      contract=contract)
            elif expected is not None and pct is None:
                F.add("FAIL", "marks.json", cid, label, expected, None,
                      f"{label} missing when ask+first_ask numeric",
                      contract=contract)
            elif expected is None and pct is not None and first is not None and ask is not None:
                # first==0 edge
                F.add("WARN", "marks.json", cid, label, None, pct,
                      f"{label} set but cannot compute (first_ask={first})",
                      contract=contract)

        # win_50 / 2x / 3x from peak_pct
        if peak_pct is not None:
            for flag, thresh, name in (
                ("win_50", 50.0, "win_50 <=> peak_pct >= 50"),
                ("win_2x", 100.0, "win_2x <=> peak_pct >= 100"),
                ("win_3x", 200.0, "win_3x <=> peak_pct >= 200"),
            ):
                expected = peak_pct >= thresh
                actual = m.get(flag)
                if actual is None:
                    F.add("FAIL", "marks.json", cid, flag, expected, None, name,
                          contract=contract)
                elif bool(actual) != expected:
                    F.add("FAIL", "marks.json", cid, flag, expected, actual, name,
                          contract=contract)
        else:
            for flag in ("win_50", "win_2x", "win_3x"):
                if m.get(flag) is True:
                    F.add("FAIL", "marks.json", cid, flag, False, True,
                          f"{flag} cannot be true without peak_pct",
                          contract=contract)

        # hold_expiry_win
        if expiry_pct is not None:
            expected = expiry_pct >= 50.0
            actual = m.get("hold_expiry_win")
            if actual is None or bool(actual) != expected:
                F.add("FAIL", "marks.json", cid, "hold_expiry_win", expected, actual,
                      "hold_expiry_win <=> expiry_pct >= 50",
                      contract=contract)
        elif m.get("hold_expiry_win") is True:
            F.add("FAIL", "marks.json", cid, "hold_expiry_win", False, True,
                  "hold_expiry_win cannot be true without expiry_pct",
                  contract=contract)

        # early_vs_expiry
        if peak_pct is not None and expiry_pct is not None:
            expected = peak_pct >= 50.0 and expiry_pct <= 0.0
            actual = m.get("early_vs_expiry")
            if actual is None or bool(actual) != expected:
                F.add("FAIL", "marks.json", cid, "early_vs_expiry", expected, actual,
                      "early_vs_expiry <=> peak_pct >= 50 AND expiry_pct <= 0",
                      contract=contract)
        elif m.get("early_vs_expiry") is True:
            F.add("FAIL", "marks.json", cid, "early_vs_expiry", False, True,
                  "early_vs_expiry needs both peak_pct and expiry_pct",
                  contract=contract)

        # peak should dominate now when both present (peak_ask >= now_ask)
        if peak_ask is not None and now_ask is not None and peak_ask + PCT_TOL < now_ask:
            F.add("FAIL", "marks.json", cid, "peak_ask", f">= now_ask ({now_ask})",
                  peak_ask, "peak_ask is max ask while alive",
                  contract=contract)


def check_cross_file(
    cites: List[Dict],
    marks: List[Dict],
    marks_doc: Dict,
    sb: Dict,
    F: Findings,
) -> Tuple[Dict[str, Any], Dict[str, Any], bool]:
    cite_ids = {c.get("id") for c in cites if c.get("id")}
    mark_by_cite = {m.get("cite_id"): m for m in marks if m.get("cite_id")}
    marked_ids = set(mark_by_cite)

    for m in marks:
        cid = m.get("cite_id")
        if not cid:
            F.add("FAIL", "marks.json", None, "cite_id", "non-empty", None,
                  "every mark needs cite_id", contract=m.get("contract"))
        elif cid not in cite_ids:
            F.add("FAIL", "marks.json", cid, "cite_id", "exists in cites.json",
                  "orphan mark", "mark.cite_id must exist in cites",
                  contract=m.get("contract"))

    orphans = cite_ids - marked_ids
    for oid in sorted(orphans):
        F.add("WARN", "cites.json", oid, "mark", "mark present", "no mark",
              "orphan cite with no mark (WARN unless expected)")

    # hindsight consistency cite <-> mark
    cite_hs = {c.get("id"): bool(c.get("hindsight_flag")) for c in cites}
    for m in marks:
        cid = m.get("cite_id")
        if cid in cite_hs and bool(m.get("hindsight_flag")) != cite_hs[cid]:
            F.add("FAIL", "marks.json", cid, "hindsight_flag", cite_hs[cid],
                  m.get("hindsight_flag"),
                  "mark.hindsight_flag must match cite",
                  contract=m.get("contract"))

    # Recompute overall / contaminated using hit_rate logic (inline mirror)
    sys.path.insert(0, str(ROOT / "src"))
    from hit_rate import (  # type: ignore
        join_cites, rate_block, streak_stats, ordered_win50, build_scoreboard,
    )

    joined = join_cites(marks, ROOT / "cites.json")
    clean = [m for m in joined if not m.get("hindsight_flag")]
    contaminated = [m for m in joined if m.get("hindsight_flag")]

    fresh_overall = {
        **rate_block(clean),
        **streak_stats(ordered_win50(clean)),
        "excluded_hindsight_n": len(contaminated),
    }
    fresh_contam = rate_block(contaminated)

    # Compare headline KPIs
    sb_overall = sb.get("overall") or {}
    math_match = True
    for key in OVERALL_KEYS:
        expected = fresh_overall.get(key)
        actual = sb_overall.get(key)
        if key in ("win_50", "win_2x", "win_3x", "hold_expiry_hit_rate", "early_exit_opp_rate"):
            ok = _rate_close(expected, actual)
        elif key in ("median_peak_pct", "median_expiry_pct"):
            ok = _close(_num(expected), _num(actual), tol=0.05) if not (
                expected is None and actual is None
            ) else True
            if expected is None and actual is None:
                ok = True
            elif expected is None or actual is None:
                ok = False
            else:
                ok = _close(float(expected), float(actual), tol=0.05)
        else:
            ok = expected == actual
        if not ok:
            math_match = False
            F.add("FAIL", "scoreboard.json", "overall", key, expected, actual,
                  "scoreboard.overall must match recompute from marks (hindsight excluded)")

    # Contaminated n
    sb_contam = sb.get("contaminated") or {}
    if sb_contam.get("n") != fresh_contam.get("n"):
        math_match = False
        F.add("FAIL", "scoreboard.json", "contaminated", "n",
              fresh_contam.get("n"), sb_contam.get("n"),
              "contaminated bucket n = hindsight_flag=true count")
    if fresh_overall.get("excluded_hindsight_n") != len(contaminated):
        F.add("FAIL", "scoreboard.json", "overall", "excluded_hindsight_n",
              len(contaminated), fresh_overall.get("excluded_hindsight_n"),
              "excluded_hindsight_n = contaminated count")

    # Hindsight must not be in headline n
    scored_clean = [
        m for m in clean
        if m.get("first_ask") is not None and m.get("win_50") is not None
    ]
    if any(m.get("hindsight_flag") for m in scored_clean):
        F.add("FAIL", "scoreboard.json", "overall", "n", "no hindsight in n",
              "hindsight leaked", "Exclude hindsight_flag=true from headline n")

    # mark_count / freshness
    expected_count = len(joined)
    if sb.get("mark_count") != expected_count:
        F.add("FAIL", "scoreboard.json", None, "mark_count", expected_count,
              sb.get("mark_count"),
              "mark_count must equal len(marks) after join")
    if sb.get("marks_updated_et") != marks_doc.get("updated_et"):
        F.add("WARN", "scoreboard.json", None, "marks_updated_et",
              marks_doc.get("updated_et"), sb.get("marks_updated_et"),
              "scoreboard.marks_updated_et should mirror marks.updated_et")
    if sb.get("last_peak_refresh_et") != marks_doc.get("last_peak_refresh_et"):
        F.add("WARN", "scoreboard.json", None, "last_peak_refresh_et",
              marks_doc.get("last_peak_refresh_et"), sb.get("last_peak_refresh_et"),
              "scoreboard last_peak_refresh_et vs marks")

    # live_board / graveyard membership
    live_marks = [m for m in joined if m.get("status") == "LIVE"]
    grave_marks = [m for m in joined if m.get("status") in ("GRAVEYARD", "EXPIRED")]
    live_contracts = {r.get("contract") for r in (sb.get("live_board") or [])}
    grave_contracts = {r.get("contract") for r in (sb.get("graveyard_top10") or [])}

    # Top-25 live by abs peak/ask (same as hit_rate)
    def _sort_key(m):
        return abs(m["peak_pct"] if m.get("peak_pct") is not None else m.get("ask_pct") or 0)

    expected_live = sorted(live_marks, key=_sort_key, reverse=True)[:25]
    expected_grave = sorted(grave_marks, key=_sort_key, reverse=True)[:10]
    exp_live_set = {m.get("contract") for m in expected_live}
    exp_grave_set = {m.get("contract") for m in expected_grave}

    missing_live = exp_live_set - live_contracts
    extra_live = live_contracts - exp_live_set
    if missing_live or extra_live:
        F.add("FAIL", "scoreboard.json", "live_board", "membership",
              f"top25 of {len(live_marks)} LIVE",
              f"missing={sorted(missing_live)[:8]} extra={sorted(extra_live)[:8]}",
              "live_board rows should match LIVE marks (top 25 by |peak|)")

    missing_g = exp_grave_set - grave_contracts
    extra_g = grave_contracts - exp_grave_set
    if missing_g or extra_g:
        F.add("FAIL", "scoreboard.json", "graveyard_top10", "membership",
              f"top10 of {len(grave_marks)} EXPIRED/GRAVEYARD",
              f"missing={sorted(missing_g)[:8]} extra={sorted(extra_g)[:8]}",
              "graveyard_top10 should match expired/dropped (top 10 by |peak|)")

    # LIVE row on graveyard or vice versa
    for r in sb.get("live_board") or []:
        if r.get("status") not in (None, "LIVE"):
            F.add("FAIL", "scoreboard.json", r.get("contract"), "status",
                  "LIVE", r.get("status"), "live_board rows must be LIVE status")
    for r in sb.get("graveyard_top10") or []:
        if r.get("status") not in ("EXPIRED", "GRAVEYARD"):
            F.add("WARN", "scoreboard.json", r.get("contract"), "status",
                  "EXPIRED|GRAVEYARD", r.get("status"),
                  "graveyard rows should be expired/dropped")

    # Spot-check board row values vs marks.
    # Key = (contract, handle, cited_et) — contract alone collides (same OCC, different cites).
    def _row_key(row: Dict[str, Any]):
        return (row.get("contract"), row.get("handle"), row.get("cited_et"))

    by_key = {_row_key(m): m for m in joined}
    # INFO: duplicate contracts across cites
    from collections import Counter
    cc = Counter(m.get("contract") for m in joined if m.get("contract"))
    for contract, n in sorted(cc.items()):
        if n > 1:
            F.add("INFO", "marks.json", None, "contract", "unique per cite",
                  f"{n} cites share {contract}",
                  "duplicate contract labels — board join must use handle+cited_et",
                  contract=contract)

    for board_name in ("live_board", "graveyard_top10"):
        for r in sb.get(board_name) or []:
            m = by_key.get(_row_key(r))
            if not m:
                # fallback: unique contract match
                cands = [x for x in joined if x.get("contract") == r.get("contract")]
                if len(cands) == 1:
                    m = cands[0]
                else:
                    F.add("WARN", "scoreboard.json", r.get("contract"), "row_key",
                          "(contract,handle,cited_et) in marks", "not found / ambiguous",
                          f"{board_name} row could not be joined to a unique mark",
                          contract=r.get("contract"))
                    continue
            for field in ("first_ask", "peak_pct", "win_50", "hold_expiry_win",
                          "early_vs_expiry", "handle", "status", "feed"):
                if r.get(field) != m.get(field):
                    if field in ("first_ask", "peak_pct") and _close(_num(r.get(field)), _num(m.get(field))):
                        continue
                    F.add("FAIL", "scoreboard.json", m.get("cite_id"), field,
                          m.get(field), r.get(field),
                          f"{board_name} cell must match mark",
                          contract=r.get("contract"))

    # Also build full fresh scoreboard for report context (not written)
    fresh_sb = build_scoreboard(ROOT / "marks.json", ROOT / "cites.json")

    return fresh_overall, fresh_sb, math_match


def render_md(report: Dict[str, Any]) -> str:
    c = report["counts"]
    lines = [
        f"# Call Scoreboard QC — {report['stamp_et']}",
        "",
        f"_Rules: {report['rules_ref']} · Board: `{report['board_root']}`_",
        "",
        "## Summary",
        "",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| FAIL | **{c['FAIL']}** |",
        f"| WARN | **{c['WARN']}** |",
        f"| INFO | **{c['INFO']}** |",
        f"| **overall math match** | **{report['overall_math_match']}** |",
        "",
        "### Scoreboard.overall vs recompute",
        "",
        "| Key | Scoreboard | Recompute |",
        "|-----|------------|-----------|",
    ]
    sb_o = report["scoreboard_overall"]
    fr_o = report["recomputed_overall"]
    for key in OVERALL_KEYS:
        lines.append(f"| {key} | {sb_o.get(key)} | {fr_o.get(key)} |")
    lines += [
        "",
        f"- marks.updated_et: `{report['marks_updated_et']}`",
        f"- scoreboard.updated_et: `{report['scoreboard_updated_et']}`",
        f"- mark_count (file): `{report['mark_count_file']}` · expected `{report['mark_count_expected']}`",
        f"- cites: {report['n_cites']} · marks: {report['n_marks']}",
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("_No findings._")
    else:
        lines += [
            "| Sev | File | Id/Contract | Field | Expected | Actual | Rule |",
            "|-----|------|-------------|-------|----------|--------|------|",
        ]
        for f in report["findings"]:
            ident = f.get("id") or ""
            if f.get("contract"):
                ident = f"{ident} / {f['contract']}" if ident else f["contract"]
            lines.append(
                f"| {f['severity']} | {f['file']} | {ident} | {f['field']} | "
                f"{f['expected']!s} | {f['actual']!s} | {f['rule']} |"
            )
    lines += ["", "---", "_QC only — does not mutate board files._", ""]
    return "\n".join(lines)


def main() -> int:
    cites_path = ROOT / "cites.json"
    marks_path = ROOT / "marks.json"
    sb_path = ROOT / "scoreboard.json"

    cites_doc = _load(cites_path)
    marks_doc = _load(marks_path)
    sb = _load(sb_path)
    cites = cites_doc.get("cites") or []
    marks = marks_doc.get("marks") or []

    F = Findings()

    if marks_doc.get("version", 0) < 4:
        F.add("WARN", "marks.json", None, "version", ">=4", marks_doc.get("version"),
              "marks should be v4+")
    if sb.get("version", 0) < 2:
        F.add("WARN", "scoreboard.json", None, "version", ">=2", sb.get("version"),
              "scoreboard should be v2+")

    check_cite_schema(cites, F)
    check_mark_schema(marks, F)
    check_board_columns(sb, F)
    check_score_math(marks, F)
    fresh_overall, fresh_sb, math_match = check_cross_file(cites, marks, marks_doc, sb, F)

    # Cap explosion: board cell mismatches can be huge; keep all but summarize in counts
    ts = stamp()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = REPORT_DIR / f"qc-{ts}.json"
    out_md = REPORT_DIR / f"qc-{ts}.md"

    report = {
        "stamp_et": now_et().strftime("%Y-%m-%d %H:%M ET"),
        "stamp_file": ts,
        "rules_ref": "RULES.md v1",
        "board_root": str(ROOT),
        "counts": F.counts(),
        "overall_math_match": math_match,
        "n_cites": len(cites),
        "n_marks": len(marks),
        "marks_updated_et": marks_doc.get("updated_et"),
        "scoreboard_updated_et": sb.get("updated_et"),
        "mark_count_file": sb.get("mark_count"),
        "mark_count_expected": len(marks),
        "scoreboard_overall": sb.get("overall") or {},
        "recomputed_overall": fresh_overall,
        "recomputed_contaminated_n": (fresh_sb.get("contaminated") or {}).get("n"),
        "findings": F.items,
    }
    out_json.write_text(json.dumps(report, indent=2, default=str) + "\n")
    out_md.write_text(render_md(report))

    print(json.dumps({
        "ok": F.counts()["FAIL"] == 0,
        "counts": F.counts(),
        "overall_math_match": math_match,
        "report_md": str(out_md),
        "report_json": str(out_json),
    }, indent=2))
    return 1 if F.counts()["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
