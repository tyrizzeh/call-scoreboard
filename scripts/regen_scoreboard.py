#!/usr/bin/env python3
"""Regenerate scoreboard.json (+ markdown + phone board) from marks.

Usage (repo root):
  python3 scripts/regen_scoreboard.py
  python3 scripts/regen_scoreboard.py --marks PATH --cites PATH

Wraps src/hit_rate.py. Peak ≠ expiry. No trade advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hit_rate import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
