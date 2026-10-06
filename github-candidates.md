# GitHub / OSS candidates — Call Scoreboard

**Goal:** OPTIONS social-callout accountability (X + Reddit dated plays → stamp ask at cite → % gain / peak / hit rate / streaks by account).

**Our stack:** Notion/Sheets scoreboard + X MCP + Webull quotes + Python on box. Prefer steal-schema / steal-parser / fork-dashboard over full rewrite.

**Searched:** 2026-10-06 ET. Stars are approximate from GitHub API that day. Pure equity portfolio trackers skipped.

---

## Ranked shortlist (12)

### 1. AdoNunes/DiscordAlertsTrader
- **URL:** https://github.com/AdoNunes/DiscordAlertsTrader
- **Stars:** ~79 | **License:** BSD-3-Clause | **Lang:** Python
- **What:** Parses Discord BTO/STC/SL/PT alerts → analyst portfolios → **live quotes for actual alert P&L** (not claimed prices) → analyst stats / capital tests. Optional Webull/TradeStation/eTrade execution.
- **Steal:** Cite→mark schema, analyst leaderboard, “price at alert vs now” mark loop, message-format parsers, portfolio rollup.
- **Fit:** **Best product match.** Swap Discord ingest for X MCP + Reddit; keep mark/score engine; wire Webull MCP for asks. Do **not** enable auto-trade.
- **Cursor/self-host:** Python package + GUI; runs on box.

### 2. austinpkugler/trendfin
- **URL:** https://github.com/austinpkugler/trendfin
- **Stars:** ~3 | **License:** MIT | **Lang:** Python
- **What:** Reddit/Pushshift finance community toolkit. `ContractParser` turns text like `AAPL $500C for 9/12` into structured contracts; ticker parse + sentiment.
- **Steal:** ContractParser regexes, WSB post/comment scrape patterns.
- **Fit:** **Cite Scout Reddit leg.** Tiny lib — copy parsers into our Python, ignore FMP market data.
- **Note:** Stale (2021); Pushshift may be dead — keep parsers, refresh Reddit via PRAW/public JSON.

### 3. LuxAlgo/trade-journal
- **URL:** https://github.com/LuxAlgo/trade-journal
- **Stars:** ~423 | **License:** MIT | **Lang:** TypeScript
- **What:** Self-hosted trade journal: broker sync (incl. **Webull** via SDK), P&L calendar, win rate, streaks, drawdown, expectancy, per-symbol/tag breakdowns, AI reflection.
- **Steal:** Metrics definitions (streaks, win rate, expectancy), dashboard UX, round-trip trade model. Not social ingest.
- **Fit:** Best **Hit Rate UI / analytics reference**. Heavy to fork whole; harvest metric math + calendar patterns. Sheets/Notion can mirror KPIs first.
- **Cursor/self-host:** One-command self-host; Next-ish stack — fork later if we outgrow Notion.

### 4. RomarioKavin1/kollateral (+ kollateral-extension)
- **URL:** https://github.com/RomarioKavin1/kollateral
- **Stars:** ~1 | **License:** none listed | **Lang:** TypeScript
- **What:** Crypto influencer **accountability layer**: archive every call (wins + losses), price vs history, leaderboard, dossier, contradiction flags, X profile extension card.
- **Steal:** Product UX — verifiable track record, anti-deletion archive, handle dossier, confidence on sample size. Map crypto “call” → options cite.
- **Fit:** Conceptual gold for Call Scoreboard UX; ignore on-chain/TEE. Crypto-only data path not reusable.
- **Cursor/self-host:** Next app + extension — fork UI patterns, not infra.

### 5. clifton/twag
- **URL:** https://github.com/clifton/twag
- **Stars:** ~5 | **License:** MIT | **Lang:** Python (+ FastAPI/React feed)
- **What:** X/Twitter market-signal aggregation: timeline/tier accounts, LLM triage, SQLite FTS5, Telegram alerts, web feed.
- **Steal:** Account watchlist pipeline, FTS search over cites, digest/alert patterns. Pair with our X MCP instead of bird scrapers where possible.
- **Fit:** Cite Scout **X enrichment** (not strike parsing). FastAPI+React = optional live phone feed later.
- **Cursor/self-host:** Yes — FastAPI + React; Cursor-friendly Python.

### 6. Mattbusel/Reddit-Options-Trader-ROT-
- **URL:** https://github.com/Mattbusel/Reddit-Options-Trader-ROT-
- **Stars:** ~12 | **License:** MIT | **Lang:** Python
- **What:** Reddit (+ RSS) → NLP/credibility → structured **options trade ideas** (strike/expiry heuristics) + WebSocket dashboard + Alpaca paper.
- **Steal:** Subreddit poller config, provenance audit trail, strike/expiry heuristics as *suggestions only* (we still need explicit callouts for accountability).
- **Fit:** Reddit ingest + dashboard ideas. Skip auto paper-trade / “crowd signal = trade.”
- **Cursor/self-host:** Full-stack Python; forkable.

### 7. TheQuantum-Dev/journedge
- **URL:** https://github.com/TheQuantum-Dev/journedge
- **Stars:** ~35 | **License:** MIT | **Lang:** TypeScript
- **What:** Local SQLite trading journal with **options** (OCC symbol parse, multiplier), win/loss, **streak analysis**, equity curve, MAE/MFE, strategy playbook.
- **Steal:** OCC option symbol parsing, streak/win-rate schema, local SQLite model for cites/marks if we leave Notion.
- **Fit:** Strong Hit Rate backend reference; no social ingest.

### 8. asayadi/Webull-Trading-Bot
- **URL:** https://github.com/asayadi/Webull-Trading-Bot
- **Stars:** ~18 | **License:** MIT | **Lang:** Python
- **What:** Discord scrape → place **option** orders on Webull.
- **Steal:** How callouts map to Webull option symbols / legs. **Do not** copy Discord user-token scrape or live order placement.
- **Fit:** Mark Desk Webull symbol formatting only. Accountability ≠ execution.

### 9. crux1s/TastyMechanics
- **URL:** https://github.com/crux1s/TastyMechanics
- **Stars:** ~3 | **License:** GPL-3.0 | **Lang:** Python / Streamlit
- **What:** Streamlit options performance scorecard (wheel/theta focus): win rate, capture %, P/L curves, trade log.
- **Steal:** Scorecard UI layout for Hit Rate phone board.
- **Fit:** Good **Streamlit fork** for a live phone dash on box; GPL means keep derivative GPL or don’t vendor wholesale.
- **Cursor/self-host:** `streamlit run` — ideal box phone board.

### 10. RaphaelBecker/tradingJournal
- **URL:** https://github.com/RaphaelBecker/tradingJournal
- **Stars:** ~4 | **License:** MIT | **Lang:** Python / Streamlit
- **What:** Ready-to-run Streamlit journal: win rate, profit factor, drawdown, expectancy, per-symbol stats.
- **Steal:** Lightweight dashboard KPI set; MIT so easier than TastyMechanics.
- **Fit:** Quick Hit Rate Streamlit prototype fed from `marks.json`.

### 11. dgnsrekt/yfs (+ cashtag→OTM call examples)
- **URL:** https://github.com/dgnsrekt/yfs
- **Stars:** ~5 | **License:** MIT | **Lang:** Python/HTML
- **What:** Yahoo Finance options scraper; docs show Twitter cashtags → first OTM call watchlist.
- **Steal:** Fallback **options chain** when Webull chain missing; cashtag cleanup.
- **Fit:** Mark Desk backup feed (label `public` / delayed). Prefer Webull MCP first.

### 12. justinpreston/black-book *(archived)* / uxjulia/stock-options-tracker
- **URLs:** https://github.com/justinpreston/black-book · https://github.com/uxjulia/stock-options-tracker
- **Stars:** ~0 / ~0 | **License:** none | **Lang:** TypeScript (React/Express/SQLite)
- **What:** Self-hosted options journals; BlackBook has multi-leg strategies + Tradier chains; stock-options-tracker has live price fallback (Finnhub/Yahoo/Polygon) + P&L API.
- **Steal:** Options CRUD API shape, multi-leg model, price-provider cascade.
- **Fit:** Secondary UI/API reference if we build a FastAPI board. BlackBook archived — copy ideas, don’t depend.

---

## Honorable mentions (thinner fit)
| Repo | Why skip / skim |
|------|-----------------|
| jitkasempin/FinTwit_Bot | FinTwit→Discord; sentiment/unusual options — not strike accountability |
| nghiamphan/FDApp | Old React WSB ticker/option scanner; TDA API dead |
| IgrovoyFormat/option-scanner | 0DTE scorer→Discord; generates signals, doesn’t audit callouts |
| SmartNSavyBuilds/Options-Trading-AI | Streamlit paper desk; not social accountability |
| atfleming/tradestream | Discord options parse + paper P&L; low stars, heavy auto-trade |
| ebrahimkhodadadi/SignalTrader | Telegram signals → MT5 forex; not US options |
| calesthio/OptionsCanvas | Local options journal via SQLite; execution-focused |
| dstrunin/chain_peeper | IBKR chain analytics Streamlit; mark-data ideas only |

---

## Cursor-friendly / self-hostable dashboards

| Stack | Candidates | Use |
|-------|------------|-----|
| **Streamlit** | TastyMechanics, tradingJournal, Options-Trading-AI, chain_peeper | Fastest phone-usable live Hit Rate board on box |
| **FastAPI + React** | twag, ROT, black-book, stock-options-tracker | If Notion feels dead; serve cites/marks JSON |
| **Next / self-host journal** | LuxAlgo trade-journal, kollateral, journedge | Polished analytics later; heavier fork |

---

## Top-3 reuse first (recommended)

1. **DiscordAlertsTrader** — lift the **cite → live mark → analyst hit-rate/streak** loop into Python on box; feed cites from Cite Scout (X MCP + Reddit), marks from Webull MCP. Closest existing “accountability” engine for options callouts.
2. **trendfin ContractParser** — vendor the options-text parser for Reddit/X free-text (`$SPY 580C 10/17` style) so Cite Scout doesn’t hand-regex every format.
3. **LuxAlgo trade-journal metrics + (optional) Streamlit from tradingJournal/TastyMechanics** — copy win-rate / streak / expectancy definitions and a thin Streamlit phone board over `cites.json`/`marks.json`; keep Notion as the team-facing table until the Streamlit board is sticky.

**Explicitly do later / don’t copy blindly:** kollateral UX (dossier, anti-delete), twag X triage, Webull-Trading-Bot symbol helpers. Never enable Discord user-token scraping or auto-order placement for Ty’s accountability product.

