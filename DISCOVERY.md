# Cite Scout discovery algorithm (living)

**Updated:** 2026-10-06 16:26 ET
**Owner:** Cite Scout (execute) · CoS + QC (stress-test / refine)  
**Rule:** Never freeze. Always refine. Measure yield. Kill dead lanes.

Social is evidence to interrogate, never a copy signal.

---

## Goal
Find contemporaneous first-person OPTIONS callouts (2–3 month lookback) that Mark Desk can mark — and surface **handles Ty might follow**, with honest peak≠hold labels.

## What we do NOT do
- Rank by likes / views / follower count alone (vanity ≠ edge).
- Crown anyone on n&lt;10.
- Copy flow dumps, CSP/CC income spam, hindsight flexes, pennies/commodities (unless Ty named).
- Freeze a small watchlist and stop hunting.

---

## Multi-lane hunt (rotate every pass)

Each hourly / backfill pass MUST touch **≥3 lanes**. Log which lanes ran in the cite batch notes + CONTINUE_HERE.

### Lane A — Hot-handle deepen (priority harvest)
Scroll profiles of current `hot_streaks` / priority list (liquidittyedge, edgeflowcapital, HendersonAnalytic, gabimarutrades, A_Pevine, AscendOptions, DudeOnR0ck, ElmagoMagico, …).  
**Why:** thicken n on printers already marking well.  
**Yield metric:** new scorable cites / scroll hour; skip rate (no cite-time path).

### Lane B — Runner → who called it (ex-post discovery)
Take names that **already ripped** (day/week) from delayed tape / Yahoo movers / Stocktwits trending / Barchart unusual. Search X/Stocktwits/Reddit for **pre-move** dated options callouts on that ticker.  
**Why:** finds unknown handles who were early — not who piled on after.  
**Hard filter:** post `cited_et` must be **before** the move; else `hindsight_flag=true` (contaminated, out of headline).  
**Yield metric:** new handles discovered / runners checked; % contemporaneous vs hindsight.

### Lane C — Ticker / contract keyword search
Rotate liquid underlyings (HOOD, NVDA, TSLA, META, AAPL, AMZN, GOOGL, SPY/QQQ lotto, ZETA book names, …). Queries like:  
`"$TICKER" (call OR put OR C OR P) (strike OR expiry OR DTE OR leap)`  
plus Stocktwits `$TICKER` options threads, Reddit r/options / r/thetagang (longs only; park short_premium).  
**Why:** catches first-timers not on any list.  
**Yield metric:** clean FP cites / query; contamination rate.

### Lane D — Network / graph expand
From a hot post: quote-tweets, reply guys who also state strikes, “who to follow” lists, mutuals of peak printers. Sample unknowns every pass.  
**Why:** breaks echo chamber of the current 8.  
**Yield metric:** new handles that later score ≥1 win_50.

### Lane E — Platform alternate (when X MCP = 0)
Signed-in box browser X → Stocktwits → Barchart options ideas → Reddit browser/mirrors. Never stall on a dead feed.  
**Yield metric:** cites landed despite MCP death.

### Lane F — Feasibility / anti-lanes (deprioritize)
Park or soft-skip: CSP/CC heavy, pure flow weaves, hindsight recap accounts, sub-$2 junk. Re-check quarterly in case style changes.  
**Yield metric:** time NOT wasted.

---

## Ranking inside a lane (not likes)
Score a **candidate post** for harvest priority:
1. **Contemporaneous FP** with strike + expiry (+ ask if stated) — highest.
2. Handle already on hot_streaks / priority — deepen.
3. Liquid underlying, premium in lottery band (cheap OTM / under ~$200/contract vibe) — prefer.
4. Likes/views — **weak tie-break only** after (1)–(3). Never the primary sort.
5. After-the-fact / no strike / stock-only — drop or flag contaminated.

## Handle promotion / demotion (living watchlist)
- **Promote to priority harvest:** rising peak streak, or ≥2 clean win_50 in window, or discovered via Lane B pre-move.
- **Keep sampling:** unknowns from C/D even if cold.
- **Deprioritize:** CSP-CC / flow-only / repeated unscored skips / n≥5 with win_50≪book.
- **Never crown** on thin n; board already labels scored-rows-only · peak ≠ hold.

## Stress-test cadence (CoS + QC)
Every meaningful board bump (or daily at checkpoint):
1. Which lanes produced the last 20 cites? Kill / boost accordingly.
2. Are we over-mining the same 2 handles? Force Lane B+C+D next pass.
3. Hindsight contamination rate — if rising, tighten Lane B gate.
4. Unscored-skip rate on hot handles — don’t let streak optics hide tape.
5. Write one line to CONTINUE_HERE: `algo_note: …` (what changed).

## Success
- New handles keep appearing on the board.
- Priority list churns with evidence, not vibes.
- Ty can see **who** and **why** (peak printer vs hold god) without asking how we searched.

## Handle dossier (for Ty follow decisions)
Path: `/workspace/call-scoreboard/handles.json` (schema-first — **do not block cites/marks** waiting on scrape).

When harvesting a handle, upsert:
- `followers` + `followers_as_of_et` (platform count from profile; null OK)
- `experience_tier`: `experienced` | `mixed` | `amateur` | `unknown`
- `experience_why`: one line from skim of recent options posts/threads (strike/expiry fluency, months of dated FP, hindsight ratio — **not** likes/followers)

Hit Rate merges dossier into `follow_shortlist` + leaderboard on every republish. Unknown/null is fine until a real skim lands. Vanity ≠ edge.
