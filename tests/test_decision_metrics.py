#!/usr/bin/env python3
"""Decision-surface checks: avg peak≠expiry, follow_shortlist labels, handles merge."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hit_rate import (  # noqa: E402
    build_follow_shortlist,
    build_scoreboard,
    compute_horizon,
    cos_eval_for_handle,
    dte_bucket,
    merge_handle_meta,
    rate_block,
)


def _mark(
    cite_id: str,
    handle: str,
    *,
    peak_pct: float,
    expiry_pct: float | None,
    win_50: bool,
    cited_et: str = "2026-09-01 10:00",
    expiry: str = "2026-09-10",
    status: str | None = None,
    hindsight: bool = False,
    style: str | None = None,
) -> dict:
    return {
        "cite_id": cite_id,
        "handle": handle,
        "platform": "x",
        "first_ask": 1.0,
        "peak_pct": peak_pct,
        "expiry_pct": expiry_pct,
        "ask_pct": peak_pct * 0.5 if status != "EXPIRED" else None,
        "win_50": win_50,
        "win_2x": peak_pct >= 100,
        "win_3x": peak_pct >= 200,
        "hold_expiry_win": expiry_pct is not None and expiry_pct >= 50,
        "early_vs_expiry": win_50 and expiry_pct is not None and expiry_pct <= 0,
        "cited_et": cited_et,
        "expiry": expiry,
        "status": status or ("EXPIRED" if expiry_pct is not None else "LIVE"),
        "hindsight_flag": hindsight,
        "style": style,
        "contract": f"TEST 100C {expiry}",
    }


class DecisionMetricsTest(unittest.TestCase):
    def test_avg_peak_ne_avg_expiry(self):
        rows = [
            _mark("a", "@printer", peak_pct=100, expiry_pct=-100, win_50=True),
            _mark("b", "@printer", peak_pct=50, expiry_pct=-50, win_50=True),
        ]
        block = rate_block(rows)
        self.assertEqual(block["avg_peak_pct"], 75.0)
        self.assertEqual(block["avg_expiry_pct"], -75.0)
        self.assertNotEqual(block["avg_peak_pct"], block["avg_expiry_pct"])

    def test_follow_shortlist_labels(self):
        overall = {"win_50": 0.5, "n": 20}
        leaderboard = [
            {
                "handle": "@holdgod",
                "platform": "x",
                "handle_label": "@holdgod · x",
                "n": 5,
                "win_50": 0.8,
                "avg_peak_pct": 120.0,
                "avg_expiry_pct": 10.0,
                "median_peak_pct": 100.0,
                "current_streak_label": "3W",
                "flags": {"early_vs_expiry": 0},
            },
            {
                "handle": "@printer",
                "platform": "x",
                "handle_label": "@printer · x",
                "n": 5,
                "win_50": 0.8,
                "avg_peak_pct": 200.0,
                "avg_expiry_pct": -90.0,
                "median_peak_pct": 180.0,
                "current_streak_label": "4W",
                "flags": {"early_vs_expiry": 4},
            },
            {
                "handle": "@thin",
                "platform": "x",
                "handle_label": "@thin · x",
                "n": 1,
                "win_50": 1.0,
                "avg_peak_pct": 80.0,
                "avg_expiry_pct": None,
                "median_peak_pct": 80.0,
                "current_streak_label": "1W",
                "flags": {"early_vs_expiry": 0},
            },
            {
                "handle": "@fade",
                "platform": "x",
                "handle_label": "@fade · x",
                "n": 6,
                "win_50": 0.1,
                "avg_peak_pct": 5.0,
                "avg_expiry_pct": -99.0,
                "median_peak_pct": 0.0,
                "current_streak_label": "3L",
                "flags": {"early_vs_expiry": 0},
            },
        ]
        dossier = {
            "@holdgod": {
                "followers": 1000,
                "experience_tier": "mixed",
                "experience_why": "dated fills",
            }
        }
        out = build_follow_shortlist(
            leaderboard, overall, {}, {"@printer": 4}, dossier
        )
        by = {r["handle"]: r for r in out}
        self.assertEqual(by["@holdgod"]["label"], "hold_candidate")
        self.assertEqual(by["@printer"]["label"], "peak_printer")
        self.assertEqual(by["@thin"]["label"], "thin_sample")
        self.assertEqual(by["@fade"]["label"], "avoid")
        self.assertEqual(by["@holdgod"]["followers"], 1000)
        self.assertEqual(by["@holdgod"]["experience_tier"], "mixed")

    def test_merge_handle_meta(self):
        row = merge_handle_meta(
            {"handle": "@x", "n": 1},
            {
                "@x": {
                    "followers": 42,
                    "followers_as_of_et": "2026-10-06 16:26",
                    "experience_tier": "experienced",
                    "experience_why": "fluent strikes",
                }
            },
        )
        self.assertEqual(row["followers"], 42)
        self.assertEqual(row["experience_tier"], "experienced")

    def test_regen_from_marks_fixture(self):
        marks = {
            "updated_et": "2026-10-06 16:25",
            "marks": [
                _mark("c1", "@edge", peak_pct=200, expiry_pct=5, win_50=True, cited_et="2026-09-01 09:00"),
                _mark("c2", "@edge", peak_pct=100, expiry_pct=-10, win_50=True, cited_et="2026-09-02 09:00"),
                _mark("c3", "@edge", peak_pct=80, expiry_pct=20, win_50=True, cited_et="2026-09-03 09:00"),
                _mark("c4", "@peaky", peak_pct=150, expiry_pct=-95, win_50=True, cited_et="2026-09-01 10:00"),
                _mark("c5", "@peaky", peak_pct=90, expiry_pct=-100, win_50=True, cited_et="2026-09-02 10:00"),
                _mark("c6", "@peaky", peak_pct=70, expiry_pct=-80, win_50=True, cited_et="2026-09-03 10:00"),
                _mark("c7", "@solo", peak_pct=60, expiry_pct=None, win_50=True, cited_et="2026-09-04 10:00"),
                _mark(
                    "c8",
                    "@hindsight",
                    peak_pct=500,
                    expiry_pct=-100,
                    win_50=True,
                    hindsight=True,
                    cited_et="2026-09-01 08:00",
                ),
            ],
        }
        cites = {
            "cites": [
                {
                    "cite_id": m["cite_id"],
                    "handle": m["handle"],
                    "platform": "x",
                    "hindsight_flag": m.get("hindsight_flag", False),
                    "cited_et": m["cited_et"],
                    "underlying": "TEST",
                    "side": "C",
                    "strike": 100,
                    "expiry": "2026-10-10",
                }
                for m in marks["marks"]
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            marks_p = td_path / "marks.json"
            cites_p = td_path / "cites.json"
            handles_p = td_path / "handles.json"
            marks_p.write_text(json.dumps(marks))
            cites_p.write_text(json.dumps(cites))
            handles_p.write_text(
                json.dumps(
                    {
                        "handles": {
                            "@edge": {
                                "followers": 1325,
                                "experience_tier": "mixed",
                                "experience_why": "Opened/Closed alerts",
                            }
                        }
                    }
                )
            )
            # Point hit_rate DEFAULT_HANDLES by writing into a temp ROOT isn't easy;
            # build_scoreboard loads handles from repo ROOT. Overlay via monkeypatch path:
            import hit_rate as hr

            old = hr.DEFAULT_HANDLES
            hr.DEFAULT_HANDLES = handles_p
            try:
                sb = build_scoreboard(marks_p, cites_p)
            finally:
                hr.DEFAULT_HANDLES = old

        self.assertEqual(sb["version"], 5)
        self.assertEqual(sb["overall"]["n"], 7)  # hindsight excluded
        self.assertIsNotNone(sb["overall"]["avg_peak_pct"])
        self.assertIsNotNone(sb["overall"]["avg_expiry_pct"])
        self.assertNotEqual(sb["overall"]["avg_peak_pct"], sb["overall"]["avg_expiry_pct"])

        labels = {r["handle"]: r["label"] for r in sb["follow_shortlist"]}
        self.assertEqual(labels.get("@edge"), "hold_candidate")
        self.assertEqual(labels.get("@peaky"), "peak_printer")
        self.assertEqual(labels.get("@solo"), "thin_sample")

        edge = next(r for r in sb["leaderboard"] if r["handle"] == "@edge")
        self.assertEqual(edge["followers"], 1325)
        self.assertEqual(edge["experience_tier"], "mixed")
        self.assertNotEqual(edge["avg_peak_pct"], edge["avg_expiry_pct"])
        self.assertIn(edge["horizon"], ("short", "mid", "long", "mixed"))
        self.assertIn(edge["cos_eval"], ("follow", "watch", "skip"))
        self.assertTrue(edge.get("past"))
        self.assertTrue(edge.get("current"))
        self.assertTrue(edge.get("potential"))

        fs_edge = next(r for r in sb["follow_shortlist"] if r["handle"] == "@edge")
        self.assertEqual(fs_edge["cos_eval"], "follow")
        self.assertEqual(fs_edge["horizon"], edge["horizon"])

    def test_horizon_buckets(self):
        self.assertEqual(dte_bucket(7), "short")
        self.assertEqual(dte_bucket(14), "short")
        self.assertEqual(dte_bucket(15), "mid")
        self.assertEqual(dte_bucket(90), "mid")
        self.assertEqual(dte_bucket(91), "long")
        short_rows = [
            _mark("s1", "@h", peak_pct=50, expiry_pct=-100, win_50=True, expiry="2026-09-05"),
            _mark("s2", "@h", peak_pct=60, expiry_pct=-100, win_50=True, expiry="2026-09-08"),
            _mark("s3", "@h", peak_pct=70, expiry_pct=-100, win_50=True, expiry="2026-09-10"),
        ]
        hz = compute_horizon(short_rows)
        self.assertEqual(hz["horizon"], "short")
        mixed_rows = [
            _mark("a", "@h", peak_pct=50, expiry_pct=0, win_50=True, expiry="2026-09-05"),  # 4d short
            _mark("b", "@h", peak_pct=50, expiry_pct=0, win_50=True, expiry="2026-10-15"),  # 44d mid
            _mark("c", "@h", peak_pct=50, expiry_pct=0, win_50=True, expiry="2027-01-15"),  # long
        ]
        self.assertEqual(compute_horizon(mixed_rows)["horizon"], "mixed")

    def test_cos_eval_labels(self):
        self.assertEqual(
            cos_eval_for_handle(
                shortlist_label="hold_candidate", n=5, win_50=0.8, book_w50=0.5, horizon="short"
            )["cos_eval"],
            "follow",
        )
        self.assertEqual(
            cos_eval_for_handle(
                shortlist_label="avoid", n=6, win_50=0.1, book_w50=0.5, horizon="mid"
            )["cos_eval"],
            "skip",
        )
        self.assertEqual(
            cos_eval_for_handle(
                shortlist_label="thin_sample", n=1, win_50=1.0, book_w50=0.5, horizon="short"
            )["cos_eval"],
            "watch",
        )


if __name__ == "__main__":
    unittest.main()
