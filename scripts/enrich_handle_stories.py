#!/usr/bin/env python3
"""Enrich scoreboard.json with horizon + past/current/potential + cos_eval.

Prefer full regen when marks.json is valid:
  python3 scripts/regen_scoreboard.py

This path updates an existing scoreboard (box snapshot) when marks are missing,
recovering cite rows from live/graveyard/contaminated/short_premium sections.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hit_rate import (  # noqa: E402
    attach_handle_stories,
    render_markdown,
    republish_dashboard,
)


def main() -> int:
    sb_path = ROOT / "scoreboard.json"
    md_path = ROOT / "scoreboard.md"
    if not sb_path.exists():
        print(f"Missing {sb_path}", file=sys.stderr)
        return 1
    sb = json.loads(sb_path.read_text())
    sb = attach_handle_stories(sb)
    sb_path.write_text(json.dumps(sb, indent=2) + "\n")
    md_path.write_text(render_markdown(sb))
    republish_dashboard(sb)
    fl = sb.get("follow_shortlist") or []
    sample = ", ".join(
        f"{r.get('handle')}:{r.get('cos_eval')}/{r.get('horizon')}" for r in fl[:5]
    )
    print(f"Enriched → {sb_path} v{sb.get('version')} · shortlist {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
