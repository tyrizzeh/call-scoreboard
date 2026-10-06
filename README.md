# Call Scoreboard

Ty Pham’s **options social accountability board**: cite → mark → hit-rate, with **peak% vs expiry%** kept as separate scores (RULES.md v1).

Social callouts are evidence to interrogate, never a copy signal. This stack does **not** CLEAR trades or auto-trade. Scripts never invent quotes.

## Pipeline

| Role | Job | Output |
|------|-----|--------|
| **Cite Scout** | Harvest dated X/Reddit options plays | `cites.json` |
| **Mark Desk** | Stamp ask near cite; track peak / now / exit / expiry | `marks.json` |
| **Hit Rate** | Overall + per-handle hit rate, streaks | `scoreboard.json`, `scoreboard.md` |

Phone board: `dashboard/index.html` (peak ≠ expiry front and center).

## RULES.md v1 (peak vs expiry)

A callout can **peak +50%** and still **expire worthless**. Headline wins use the peak path; hold-to-expiry is a separate column.

- **peak_ask / peak_pct** — max ask while alive (max-gain map)
- **expiry_ask / expiry_pct** — at/near expiration; 0 if OTM worthless
- **exit_ask / exit_pct** — poster-stated STC only; else null
- **win_50 / win_2x / win_3x** — peak-based
- **hold_expiry_win** — expiry_pct ≥ +50%
- **early_vs_expiry** — peak ≥ +50% and expiry ≤ 0
- Headline **overall hit rate** = peak win_50 / marked cites with valid first_ask
- Exclude `hindsight_flag=true` from headline n (contaminated bucket)
- Streaks: consecutive peak win_50 by `cited_et`; unmarked breaks the streak

Full definitions: [`RULES.md`](RULES.md) (keep v1 intact; log changes there).

## Data files

| File | Role |
|------|------|
| `cites.json` | Cite Scout rows (`handle`, `platform`, `post_url`, `cited_et`, contract fields, `cite_ask`, `claim_quote`, `hindsight_flag`) |
| `marks.json` | Mark Desk rows joined by `cite_id` (peak / now / exit / expiry, status, win flags) |
| `scoreboard.json` | Machine hit-rate + streaks |
| `scoreboard.md` | Human report |
| `dashboard/scoreboard.json` | Snapshot for the static phone board (refresh from root scoreboard when serving) |

Do not wipe or invent marks. Prefer Webull live when available; until then `public` (yfinance) is labeled on each mark.

## How to run

Python 3.10+. For live/public marks: `pip install yfinance`.

```bash
# From repo root

# 1) Parse free-text callouts (Cite Scout helper)
python3 src/parse_contract.py 'SPY 780C 10/10'
python3 src/parse_contract.py 'AAPL $500C for 9/12' --json
python3 src/parse_contract.py --json <<< '$TSLA 420 calls Oct 23'

# 2) Mark cites (yfinance public chain; feed=public)
python3 src/mark_cites.py
# Recompute win flags without re-quoting:
python3 src/mark_cites.py --no-refresh

# 3) Hit rate + streaks → scoreboard.json + scoreboard.md
python3 src/hit_rate.py

# 4) Phone board (fetch needs a static server — open dashboard/)
python3 -m http.server 8765 --directory .
# → http://127.0.0.1:8765/dashboard/
# Share → Add to Home Screen on phone
```

Optional paths: `mark_cites.py --cites PATH --marks PATH`; `hit_rate.py --marks PATH --cites PATH --out PATH --md PATH`.

## Layout

```
.
  cites.json            # Cite Scout
  marks.json            # Mark Desk
  scoreboard.json       # Hit Rate (machine)
  scoreboard.md         # Hit Rate (human)
  RULES.md              # v1 peak / expiry / streaks
  github-candidates.md  # related OSS notes
  src/
    parse_contract.py
    mark_cites.py
    hit_rate.py
  dashboard/
    index.html          # mobile-first board
    scoreboard.json     # board data snapshot
  vendor/               # shallow reference clones (licenses preserved)
```

## Vendored reference (`vendor/`)

| Repo | License | Borrowed |
|------|---------|----------|
| [AdoNunes/DiscordAlertsTrader](https://github.com/AdoNunes/DiscordAlertsTrader) | BSD-3-Clause | Cite→live mark→rollup / max_pnl-style peak % (not Discord scrape or order placement) |
| [austinpkugler/trendfin](https://github.com/austinpkugler/trendfin) | MIT | Free-text contract regex ideas → `src/parse_contract.py` |
| [LuxAlgo/trade-journal](https://github.com/LuxAlgo/trade-journal) | MIT | Win-rate / streak math; KPI layout inspiration for the phone board |

## Caveats

- Peak while alive needs recurring marks; already-expired cites may show peak_pct ≈ expiry_pct until historical option OHLC is wired.
- Exit asks only from explicit STC/closed/trimmed language — bare “Sold N contracts” is STO entry, not exit.
- Social ≠ signal. No auto-trade. Never invent quotes.
