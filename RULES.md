# Scoring rules (v1 — Ty 2026-10-06)

Nuance: a callout can be **sold early for a gain** and still **expire worthless**. We never collapse those into one number.

## Marks (per cite)
From first_ask (ask near cite; label feed + as_of_et):
- **peak_ask / peak_pct** — max ask observed while contract was alive (max execution / max gain map)
- **now_ask / ask_pct** — latest mark while LIVE
- **exit_ask / exit_pct** — if poster stated a sell/STC, use that; else null
- **expiry_ask / expiry_pct** — ask (or mid/last if no ask) at/near expiration; 0 if expired OTM worthless
- **time_to_peak_et** — when peak printed

Always report **both** peak_pct and expiry_pct (or exit_pct if they closed). Holding to expiry is not the only score.

## Win definitions (headline uses peak path)
Window = min(5 trading days after cite, expiry). Peak measured over life of contract for max-gain map; headline wins use peak within window unless Ty changes it.
- **win_50**: peak_pct ≥ +50%
- **win_2x**: peak_pct ≥ +100%
- **win_3x**: peak_pct ≥ +200%
- **hold_expiry_win**: expiry_pct ≥ +50% (separate column — hold-to-expiry book)
- **early_vs_expiry**: flag when peak_pct ≥ +50% AND expiry_pct ≤ 0 (sold-early edge vs held-to-zero)

Default **overall hit rate** = win_50 / marked cites with valid first_ask (peak-based).
**Exclude `hindsight_flag=true` from headline n** — park them in a contaminated bucket (still logged, not in overall/streaks/leaderboard rates).
Also publish **hold-to-expiry hit rate** and **early-exit opportunity rate** (peak win but expiry lose).

## Streaks
By cited_et order: consecutive win_50 (peak) wins or losses. Break on unmarked.
Track book-wide + per-handle: current streak, longest win, longest loss.

## Drop
Expiry passed (after expiry mark written), −50% ask before catalyst with no peak recovery path Ty cares about, Ty drop, deleted unverifiable post.

Never invent quotes. Social ≠ trade signal.
