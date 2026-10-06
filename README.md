# Call Scoreboard (options social accountability)

Team room: **Call Scoreboard**
- **Cite Scout** — harvest dated X/Reddit options plays → `cites.json`
- **Mark Desk** — ask % since first cite, live + graveyard → `marks.json`
- **Hit Rate** — overall + per-handle hit rate, current/longest streaks → `scoreboard.json` / `scoreboard.md`

**Social callouts are evidence to interrogate, never a copy signal. This stack does not CLEAR trades or auto-trade.**

## Cite schema (one row per play)
| field | notes |
| handle | @x or u/reddit |
| platform | x \| reddit |
| post_url | required |
| cited_et | YYYY-MM-DD HH:MM America/New_York |
| underlying | ticker |
| side | C \| P |
| strike | number |
| expiry | YYYY-MM-DD |
| cite_ask | number or null if not stated |
| claim_quote | short verbatim |
| hindsight_flag | true if looks after-the-fact |

## Mark schema (RULES v1)
| field | notes |
| cite_id | joins cite |
| feed | webull_live \| cboe_delayed \| public \| stated_ask |
| as_of_et | mark stamp |
| first_ask | ask near cite (stated premium preferred when present) |
| now_ask / ask_pct | latest while LIVE |
| **peak_ask / peak_pct** | max ask while alive (max-gain map) — separate from expiry |
| time_to_peak_et | when peak printed |
| **exit_ask / exit_pct** | poster-stated sell/STC if any; else null |
| **expiry_ask / expiry_pct** | at/near expiration; 0 if OTM worthless |
| status | LIVE \| GRAVEYARD \| EXPIRED \| UNMARKED |
| win_50 / 2x / 3x | **peak-based** headline wins |
| hold_expiry_win | expiry_pct ≥ +50% |
| early_vs_expiry | peak ≥ +50% AND expiry ≤ 0 |

## Hit Rate outputs (RULES v1.1 / scoreboard v4)
- **Headline overall hit rate** = peak win_50 / clean long scored rows (hindsight + short-premium out)
- **avg_peak_pct / avg_expiry_pct** (and medians) on overall + per-handle — peak ≠ expiry always
- **Hold-to-expiry hit rate** + **early-exit opportunity rate** (peaked but expiry ≤0)
- Book + per-handle streaks on **peak** win_50 (current + longest W/L)
- **follow_shortlist** labels: `peak_printer` | `hold_candidate` | `thin_sample` | `avoid` (accountability follows — not trade advice)
- Merges `handles.json` dossier (followers, experience_tier, experience_why) into shortlist + Leaders
- Confidence: thin n<10 / decent / strong — never crown n&lt;10
- Mobile phone board: `dashboard/index.html` (Follow shortlist + Leaders show avg %, followers, xp)
  - **UX v1.1 (Scoreboard Design):** sticky hero (hit + streak), bottom thumb tabs Overview/Live/Leaders/Gone, card rows (no wide tables), Peak/Now sort, contaminated banner, feasibility + hot streaks. Prefer Add to Home Screen over Sheets for day-to-day.

Iterate definitions with Ty; log rule changes in `RULES.md`.

---

## How to run (box)

```bash
cd /workspace/call-scoreboard

# 1) Parse free-text callouts (Cite Scout helper)
python3 src/parse_contract.py 'SPY 780C 10/10'
python3 src/parse_contract.py 'AAPL $500C for 9/12' --json
python3 src/parse_contract.py --json <<< '$TSLA 420 calls Oct 23'

# 2) Mark cites (yfinance public chain; labels feed=public)
#    Prefer Webull live when connector is healthy — until then public is fine.
python3 src/mark_cites.py
#    Recompute win flags without re-quoting:
python3 src/mark_cites.py --no-refresh

# 3) Hit rate + streaks → scoreboard.json + scoreboard.md (+ dashboard republish)
python3 src/hit_rate.py
# same via wrapper:
python3 scripts/regen_scoreboard.py

# 4) Decision-surface checks (fixture marks; no live quotes)
python3 -m unittest tests.test_decision_metrics -v

# 5) Phone board (fetch needs a tiny static server)
python3 -m http.server 8765 --directory /workspace/call-scoreboard
# open http://127.0.0.1:8765/dashboard/  → Share → Add to Home Screen
```

Deps: Python 3.10+, `yfinance` (for public option asks). No auto-trade packages required.

---

## Open-source reuse (vendored under `vendor/`)

| Repo | License | What we borrowed |
|------|---------|------------------|
| [AdoNunes/DiscordAlertsTrader](https://github.com/AdoNunes/DiscordAlertsTrader) | BSD-3-Clause | Cite→live mark→analyst rollup pattern (`AlertsTracker.price_now`, portfolio mark loop, `max_pnl` style peak %). **Not** Discord user-token scrape or order placement. |
| [austinpkugler/trendfin](https://github.com/austinpkugler/trendfin) | MIT | `ContractParser` regex ideas for free-text options (`AAPL $500C for 9/12`, glued `780C`, month/day expiry). Reimplemented lean in `src/parse_contract.py`. |
| [LuxAlgo/trade-journal](https://github.com/LuxAlgo/trade-journal) | MIT | Win-rate / streak math (`currentStreak` signed run, `maxWinStreak` / `maxLossStreak`) from `packages/core/src/metrics.ts`; KPI card layout inspiration for the phone board. |

Also researched (not vendored this pass): kollateral accountability UX, twag X triage, journedge OCC parse, Streamlit journals — see `github-candidates.md`.

---

## Layout

```
call-scoreboard/
  cites.json          # Cite Scout output
  marks.json          # Mark Desk output
  handles.json        # followers + experience_tier dossiers
  scoreboard.json     # Hit Rate machine output (v4 + follow_shortlist)
  scoreboard.md       # Human report
  DIGEST.md / DISCOVERY.md / CONTINUE_HERE.md
  RULES.md            # win_50 / streak definitions
  github-candidates.md
  scripts/regen_scoreboard.py
  tests/test_decision_metrics.py
  src/
    parse_contract.py
    mark_cites.py
    history_peak.py
    hit_rate.py
    qc/
  dashboard/
    index.html        # mobile-first phone board
    scoreboard.json   # republished snapshot
  vendor/             # shallow clones (reference only)
```

## Caveats (polish backlog)
- **Peak while alive** needs recurring marks (hourly). Already-expired cites get a single stamp → peak_pct may equal expiry_pct until we wire historical option OHLC.
- **Webull live** preferred over yfinance `public` when connector is healthy; feed is always labeled.
- Exit asks only from explicit STC/closed/trimmed language — bare “Sold N contracts” is treated as STO entry, not exit.
- Social ≠ signal. No auto-trade.

### v1.1 run order (CoS)
`python3 src/history_peak.py && python3 src/hit_rate.py` — history overlay sets cite-time entry + 5-session peak; see RULES.md v1.1.
