# Call Scoreboard

Ty Pham’s **options social accountability board**: cite → mark → hit-rate, with **peak% vs expiry%** kept separate (RULES.md v1.1).

Social callouts are evidence to interrogate, never a copy signal. This stack does **not** CLEAR trades or auto-trade. Scripts never invent quotes.

**Authoritative runbooks:** [`CONTINUE_HERE.md`](CONTINUE_HERE.md) · [`RULES.md`](RULES.md)

## Pipeline

| Role | Job | Output |
|------|-----|--------|
| **Cite Scout** | Multi-lane hunt (not likes-first) → dated options plays | `cites.json`, `handles.json` |
| **Mark Desk** | Stamp ask near cite; track peak / now / exit / expiry | `marks.json` |
| **Hit Rate** | Overall + per-handle rates, avg peak/exp %, follow shortlist | `scoreboard.json`, `scoreboard.md` |

Phone board: [`dashboard/index.html`](dashboard/index.html) — Follow shortlist + Leaders show avg peak%, avg exp%, followers, experience. Peak ≠ expiry front and center.

## Decision docs (phone-first)

| Doc | Purpose |
|-----|---------|
| [`DISCOVERY.md`](DISCOVERY.md) | Multi-lane hunt (A–F): hot-handle deepen, runner→who-called-it, ticker search, network, alt platforms, anti-lanes. Likes/views = weak tie-break only. |
| [`DIGEST.md`](DIGEST.md) | Weekday 7:51am ET morning DM format — follow_shortlist + avg peak/exp. |
| [`handles.json`](handles.json) | Dossier schema: `followers` + `experience_tier` (+ why). Vanity ≠ edge. |
| [`CONTINUE_HERE.md`](CONTINUE_HERE.md) | Live CoS state / standing orders (resume without Ty). |
| [`RULES.md`](RULES.md) | v1.1 scoring: entry basis, peak sources, pending/short-premium buckets, streaks. |

## RULES.md v1.1 (peak vs expiry)

A callout can **peak +50%** and still **expire worthless**. Headline wins use the peak path; hold-to-expiry is a separate column.

- **peak_ask / peak_pct** — max ask while alive (labeled `peak_source` / `peak_feed`)
- **expiry_ask / expiry_pct** — at/near expiration; 0 if OTM worthless
- **win_50 / win_2x / win_3x** — peak-based (clean LONG only)
- **hold_expiry_win** — expiry_pct ≥ +50%
- **early_vs_expiry** — peak ≥ +50% and expiry ≤ 0
- Buckets out of headline: hindsight, short-premium (CSP/CC), pending young cites, no cite-time path
- Hit Rate also publishes **avg_peak_pct**, **avg_expiry_pct**, and **follow_shortlist** labels (`peak_printer` / `hold_candidate` / `thin_sample` / `avoid`)

Never crown n&lt;10. Full definitions: [`RULES.md`](RULES.md).

## How to run

Python 3.10+. For public marks: `pip install yfinance`.

```bash
# From repo root

# 1) Parse free-text callouts
python3 src/parse_contract.py 'SPY 780C 10/10'
python3 src/parse_contract.py 'AAPL $500C for 9/12' --json

# 2) Mark cites (feed labeled; prefer Webull live when healthy)
python3 src/mark_cites.py
python3 src/mark_cites.py --no-refresh   # recompute flags without re-quoting

# 3) History overlay (cite-time entry + 5-session peak) then hit rate
python3 src/history_peak.py
python3 src/hit_rate.py

# 4) QC (optional)
python3 src/qc/run_qc.py

# 5) Phone board
python3 -m http.server 8765 --directory .
# → http://127.0.0.1:8765/dashboard/
```

## Layout

```
.
  CONTINUE_HERE.md      # CoS resume / standing orders
  RULES.md              # v1.1 scoring (authoritative)
  DISCOVERY.md          # multi-lane Cite Scout algorithm
  DIGEST.md             # weekday morning DM format
  handles.json          # followers + experience_tier dossier
  cites.json            # Cite Scout
  marks.json            # Mark Desk
  scoreboard.json       # Hit Rate (+ follow_shortlist)
  scoreboard.md
  src/
    parse_contract.py
    mark_cites.py
    history_peak.py
    hit_rate.py
    qc/run_qc.py
  dashboard/
    index.html          # mobile-first phone board
    scoreboard.json
  vendor/               # shallow reference clones
```

## Caveats

- Peak while alive needs recurring marks; hist overlay labels yahoo highs vs CBOE asks.
- Exit asks only from explicit STC/closed/trimmed language.
- Social ≠ signal. No auto-trade. Never invent quotes.
