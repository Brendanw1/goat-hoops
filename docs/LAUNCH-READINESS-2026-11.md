# Launch readiness — the pre-deployment review (2026-11-08)

The owner's ask: code quality and speed re-review, the whole-project model
scope, page-by-page standard verification, deployment/scalability prep,
the data scope with an acquisition plan, and every limitation stated.

## 1 · Build and deploy status: GREEN

`next build` (production) passes with **zero errors across all 21 routes**.
The cache map is exactly as designed: the data pages prerender with a
5-minute ISR window (`/`, `/teams`, `/players/[id]`, `/stats`, `/alltime`,
`/eras`, `/market`, `/rookies`, `/research`, `/methods`, `/about`, `/games`),
and the GET-form pages stay dynamic (`/compare`, `/comps`, `/surplus`,
`/teams/[abbr]`, `/lineups`, `/games/[gid]`) — correct, since their whole
point is query params. The prod speed model: first hit pays the R2 fetch +
render (~0.3-1.0 s locally), then the ISR cache serves ~10-30 ms for five
minutes; dev always renders per request.

**Deploy runbook (owner's go):**
1. Vercel project from this repo (`web/` root), env: `R2_ACCOUNT_ID`,
   `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`,
   `R2_ENDPOINT`, `R2_PREFIX=hoops`, `NEXT_PUBLIC_BASEBALL_URL=https://goatpro.dev`.
   `USE_LOCAL_DATA` must be ABSENT in prod (R2 is the data plane).
2. DNS: `hoops.goatpro.dev` → the Vercel project (the two-repo decision:
   goatpro.dev = baseball, hoops subdomain here; the switcher pills read
   `NEXT_PUBLIC_BASEBALL_URL` / `NEXT_PUBLIC_HOOPS_URL`, inlined at build).
3. Data plane: the bake runs locally, `r2_sync.py` mirrors
   `data/export/web/` → `hoops/` (3,785 keys as of today, disjoint prefixes —
   it can never touch the baseball site's keys). The sport switcher on the
   baseball side points here via its own env.
4. Ops crons (see §6): the site is only as live as the daily data runs.

## 2 · Page inventory — all verified

18 routes, all HTTP 200, all visually inspected this session: hub (playoff
picture, leaderboards, scorers' race, archetypes), games index + reports,
teams board + team pages (analytics, roster, play-type mix, margin strip,
roster value, starting fives), players index + profiles (contract,
projection+intervals, season stats, splits, career arc, advanced rates,
percentiles+radar, play types, tracking, zones, shot map+quadrant, similar,
surplus, clutch), stats, all-time, eras, lineups, market, rookies, compare,
comps, surplus, research, methods, about. Dev timings 0.07-1.0 s (compile-
bound; the 1.0 s outlier, /surplus, pays six doc parses per request and is
ISR-cached in prod). One deliberate non-fix documented: dev timing parity
with prod is not achievable without stale-data risk in the verify loop.

## 3 · Code quality — standards and remaining debts

Standards held: TypeScript strict-clean; server components with zero client
JS except three purposeful widgets (nav, finder, ticker track); the bake is
the single write path to the export docs; every public number carries its
gate or a descriptive label; judgment/identity/volume color channels are
separated and documented in tone.ts/team-colors.ts.

Remaining debts (ranked, none launch-blocking):
- **D1** the player page is ~800 lines — split into panel components when
  it next changes materially (mechanical, no behavior change).
- **D2** `explore.py` writes outside the bake gate (by design); its outputs
  are deterministic and re-runnable — fine, but the drift check excludes
  them, so a broken explore run would surface only visually.
- **D3** the hub awaits five player docs serially after the parallel block —
  5 × ~30 ms locally, fine; batch them into the Promise.all when touched.
- **D4** `/surplus` parses six docs per request in dev; in prod the ISR
  cache covers it. If it ever matters: memoize the name/age maps bake-side.

## 4 · Model scope — what exists, what's closed, what's next

**Shipped and gated:** the §11 ridge with §14-calibrated 90% intervals
(player projections), the §9 shot-diet/making benchmark, §0d team analytics,
§0e history env, §0f lineups/on-off (site 2025), §0g market calibration.
**Closed by preregistered FAILs (do not reopen without new data):** the RAPM
campaign (§1-§8, response-side ceiling ~0.66-0.68 vs the 0.70 bar — the gap
is defender context no public feed carries), model-class swap (§12a),
tracking-feature rates (§12b), availability classification (§12c), env-
normalized targets (§14a/b — including the proof that fold-scalar
normalization is provably inert for a centered ridge).
**Rebuild-needed:** the 2026-27 stint walk (lineups live-season) — the
derivation runs but its §1 gates fail (player-minutes median 6.98 min);
ruled out: starters, sub-text, clocks; next step: a --label arg and the
2025 control run, then bisect. **Not built (no gate attempted):** Track C
role decomposition/gravity (derivable from the stint spine), the run chart,
the availability surface §12c would have gated.

## 5 · Data scope and the acquisition plan

**Held (the spine):** ESPN boxes/PBP/shots (free, daily-able, validated vs
LUMA at 688/688 scores); BDL season-average pulls 2005-2025 across 21
categories; BDL v2 advanced game rows 2016-2026 (the tail through the live
season arriving in tomorrow's fold-in); BDL boxes site 2024-2026; contracts
with draft slots; odds (site 2026 openings complete, site 2027 live +
snapshots); ESPN injuries/news (free, daily); the mart's LUMA validation
views. **Gaps stated plainly:** defender context on shots (no public feed —
closes the RAPM gap only if a source appears), pre-NBA prospect rankings
(no college feed), per-player injury history detail (ESPN gives current
status only), possession-true team play types (BDL is player-scoped).

**Acquisition:** (a) the free tier — the daily ESPN ingest (boxes/PBP) +
news/injuries fetch + bake + r2_sync, automated as a cron (now scheduled
daily 09:00); (b) the paid tier — a one-month BDL resub mid-season is the
standing plan for advanced-tail catch-up (the walk resumes from its
checkpoint; ~15-18 h to current); (c) should-we-only-plan-for-now: yes
until launch — the free tier carries every surface that is currently live;
the paid tier only widens history and adds refresh cadence.

## 6 · Limitations — stated, not hidden

1. Lineups cover the 2024-25 window only until the 2026-27 walk passes its
   gates (the page says so, with the diagnosis pointer).
2. Projections cover players ≥ 250 minutes (the modeling floor) — early-
   season rookies appear as they qualify; the panel and /rookies say so.
3. Interval calibration is era-local (one-fold-back conformal); a shock
   (rule change, style break) invalidates widths until recalibration.
4. The trade-value composite is a printed-weights ranking lens, not a
   market price; the market's own Brier (0.202) is the benchmark any
   forecast must beat before claiming predictive status.
5. Live-season blocks everywhere carry PARTIAL flags; unit/on-off minutes
   are possession-proportional estimates, not clock minutes.
6. The ticker/injuries are ESPN's editorial statuses (Out/DTD/Q), not
   medical reports.
7. Single-region deployment (Vercel default) reading a single R2 region —
   fine for launch; revisit if there's real traffic from Asia-Pacific.

## 7 · Launch checklist (owner's go)

- [ ] Vercel project + env (§1) · [ ] DNS `hoops.goatpro.dev` ·
- [ ] the daily data cron verified green for 3 consecutive days ·
- [ ] the deadline fold-in (tomorrow 11:30 PT) + final BDL pulls ·
- [ ] cancel the BDL trial after the fold-in ·
- [ ] a prod smoke test of the switcher from goatpro.dev ↔ hoops ·
- [ ] r2_sync after the last local bake before DNS flip.
