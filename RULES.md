# Scoring rules (v1.1 — locked CoS 2026-10-06)

Nuance: a callout can be **sold early for a gain** and still **expire worthless**. We never collapse those into one number.

## Entry (first_ask)
1. **Poster-stated premium** if they gave one (cite_ask / stated ask).
2. Else **same-day close** (cited in session) or **next-session open** (after hours / weekend) from Yahoo daily option bars (`marks_hist.json`, feed `yf_hist_last`).
3. Always label **feed + as_of_et** (and `entry_basis` when history-backed). Never score a September cite off today's live stamp.

## Peaks (sources must be labeled)
- **peak_ask / peak_pct** — max observed while contract alive (headline uses peak within min(5 sessions, expiry) unless Ty changes it).
- **peak_source / peak_feed** required on every stamped peak, e.g. `cboe_delayed`, `yahoo_daily_high / chartexchange_eod_high`, `cboe_delayed+yf_hist_last`.
- **yahoo_daily_high** (Mark Desk backfill) may replace a CBOE peak **only when labeled and strictly higher than the CBOE live stamp** (`ask_pct` / `peak_cboe_pct`). Never let hist `peak_5d` downgrade a labeled higher yahoo peak. If yahoo is labeled but ≤ CBOE, keep CBOE/hist.
- Yahoo highs are trade prints, not asks — slight upward bias vs selling at bid; label it.
- **peak_life_pct** kept for the max-gain map (life of contract); headline prefers the 5-session window peak.

Also stamp: **now_ask / ask_pct** (LIVE), **exit_ask / exit_pct** (if STC stated), **expiry_ask / expiry_pct**, **time_to_peak_et**. Always report peak and expiry (or exit) — do not collapse.

## Win definitions (headline = long peak path)
- **win_50**: peak_pct ≥ +50%
- **win_2x**: peak_pct ≥ +100%
- **win_3x**: peak_pct ≥ +200%
- **hold_expiry_win**: expiry_pct ≥ +50% (separate)
- **early_vs_expiry**: peak_pct ≥ +50% AND expiry_pct ≤ 0

Default **overall hit rate** = win_50 / clean LONG cites with valid first_ask (peak-based).

## Buckets (not in headline n)
- **Contaminated**: `hindsight_flag=true` — logged, not in overall / streaks / leaderboard rates.
- **Short-premium**: CSP/CC / sold puts-calls / cash-secured / covered calls — parked off long peak win_50. Need credit/retention metrics later.
- **Pending (young cites)**: not yet +50%, fewer than 5 post-entry sessions, not expired → `win_50=None`, **out of headline**, streak **skip** (not a loss, not a break).
- **No cite-time path**: no history, cited before today, no observed win → unscored, streak skip — never a silent 0% loss.

## Streaks
By cited_et order on clean LONG scored cites. Consecutive win_50 wins/losses. Unmarked / pending / no-path **skip** (do not break). Track book + per-handle.

## Drop
Expiry marked, −50% ask with no recovery path Ty cares about, Ty drop, deleted unverifiable post.

## Refresh order
`history_peak.py` → marks → `hit_rate.py` → sync `dashboard/scoreboard.json`.

Never invent quotes. Social ≠ trade signal. No CLEAR advice.
