# Site brainstorm 2026-11-05 — from stats site to basketball analytics research site

Inputs: the baked export (24 docs), the raw harvest on disk (pbp spine, odds
snapshots, 20 seasons of category history, the growing v2-advanced stream),
the KB's basketball corpus (Closing 5, EvanMiya, bball-index LEBRON, squared
statistics, arxiv spatial models, Hawk-Eye coverage), and a sweep of what the
modern research sites ship (Cleaning the Glass, Dunks & Threes, bball-index,
databallr, DARKO). Everything below is tagged by what it needs:

- **T1 — front-end only** over already-baked docs; ship in an afternoon.
- **T2 — cheap bake addition**: derivable at bake time from raw files already
  on disk; no new pulls.
- **T3 — new pipeline work**: real build (stint stitching, new docs).
- **T4 — owner-gated**: uses internal-only ratings, or needs data the trial
  doesn't carry.

---

## 0. The thesis

The site currently answers "what are the numbers?" A research site answers
"what do the numbers mean, how do we know, and what did we rule out?" The
program's culture — pre-registration, gates, honest FAIL verdicts, LUMA
credit, do-not-render lists — is already its differentiator. The layout work
is making that culture the surface.

---

## 1. The shell (layout + IA polish)

### 1.1 Landing page = research hub (T1, highest priority)
Today `/` is the games page. Instead: a league pulse strip (standings glance,
yesterday's results, today's slate with rest/rest-edge flags), a **reads
strip** (latest preregistered reads with verdict chips — §0b PASS, §8 FAIL
with the one-line why), story cards (Durant +10.2 on 1,365 FGA; SGA's
year-over-year climb crossing Luka; the archetype map), and a player finder.
The landing page should make a stranger trust the site in ten seconds: recent,
dated, honest about what failed.

### 1.2 Nav regroup (T1)
`Games · Teams · Players · Stats · Compare · Comps · Value · Research · About`.
"Research" (reads index + methods + model inventory) and "About" (sources,
attribution, colophon) are the two missing identity pills. Keep ≤ 9 pills.

### 1.3 /research — the reads index (T1: data is RESULTS-HOOPS.md; render as a doc)
Every preregistered read as a row: section, question, gate, verdict chip
(PASS/FAIL/TIE, colored pos/neg/flag), one-line why, commit link. This is the
site's moat: **it shows its failures**. Includes the RAPM ladder table
(0.464 → 0.618 → 0.621 → 0.658 → 0.676 → FAIL-closed) with the response-side
ceiling explanation. Tag every row internal vs shipped.

### 1.4 /methods + /glossary (T1: render docs/METRICS.md canon)
Metric definitions with formulas, the everywhere-set/derived canon, the
do-not-render list (with reasons), splits canon (why splits render neutral),
the semantic color rules (pos/neg/flag = judgment only; heat ramp = volume
only; brand green/gold = identity only). CTG has "stat guides"; ours is
shorter and stricter.

### 1.5 /about — sources & colophon (T1)
The two-source validation story (BDL vs ESPN: 688/688 games, 11,326 boxes
100% exact) as a credibility artifact; the season-convention gotcha as a
"field notes" item; attribution: ESPN spine, balldontlie (trial — public
surfaces carry BDL numbers only while subscribed; Nov 9 decision), LUMA
credit for benchmarks; the republication rule stated plainly.

### 1.6 Component + responsive pass (T1)
One Card primitive everywhere (the pages drifted), sticky table headers,
mobile: wide tables become horizontally scrolled cards with pinned first
column; every table keeps its min-width but gains a caption when it scrolls.
Focus-visible states on all pills/rows. Consistent page header block
(title · context pill · season pills).

### 1.7 Empty/loading/edge states (T1)
Written copy for every empty state that says WHY: "no 2026-27 advanced rows —
the feed covers 83 of 1,230 games", "no unit ratings — BDL lineups are
starting fives, not minutes", "ratings not rendered — model is
internal-descriptive". The honesty copy is already written in docs; surface it.

### 1.8 Player finder (T1, tiny client component)
⌘K / a search box with a ~1,900-name client index (one small JSON, fuzzy
match). Every research site has one; it's the single highest-traffic widget.

---

## 2. Player depth

### 2.1 Shot-quality quadrant (T1)
From §9 shot-making: scatter x = xefg (diet), y = Δ shooting vs diet, bubble
= FGA — "who shot where they can't vs who shot where they can and hit it".
Durant +10.2 on 1,365 FGA is the anchor story. League version on /stats.

### 2.2 Role strip (T1)
One horizontal strip: archetype chip · position pool percentile median ·
usage tier · diet (3PA share) · spacing role. The scouting-report front door.

### 2.3 Game-level shot pages (T2)
playershots x/y exists per season; game docs have ESPN ids. A game page gains
both teams' shot maps + scoring runs (needs pbp, T3 for runs). Bake per-game
shot arrays at bake time — no new pulls.

### 2.4 Most-used teammates (T3)
From the exact-5 starter groups + pbp stints: minutes shared, net together vs
apart (descriptive until ratings gate opens). This is the "who do you play
with" panel every deep player page has.

### 2.5 YoY self-drift (T3)
explore.py's z-vectors exist internally; bake per-player season vectors and
render "what changed year over year" — a 31-field delta chart (passes up,
deflections down → role shift made visible). Also powers a "similar seasons"
view (which player-seasons in history look like this one).

### 2.6 Contract timeline (T1)
Deals exist; render as a horizontal timeline: past → current (highlighted) →
future years with cap hits, option flags, surplus line under it.

---

## 3. Team depth

### 3.1 Team analytics tab (T2)
Derive at bake from box sums + advagg player rollups: four factors vs league,
pace, zone diet map (team zones from playershots by team), rest schedule
grid (b2b counts, 3-in-4s). Team pages currently have standings/roster/starters
only — the thinnest surface relative to available data.

### 3.2 Lineups upgrade — real unit minutes (T3, the big one)
The pbp spine (397,967 plays × participants/clock/score) stitches into
stints → five-man unit minutes, net rating, opp — what Cleaning the Glass and
bball-index's lineup finder actually sell. The §1 RAPM possession rows prove
the stitching works. Bake a lineups.json with unit minutes/net (descriptive
gate: internal consistency vs box minutes). Starters5 continuity then becomes
a fallback view.

### 3.3 Clutch time surfaces (T2/T3)
Clutch category history exists 2005-2025 (see §4.3); team clutch leaderboards
(T2). T3: last-5-min possession flow per game from pbp (run charts, timeout
sequences) — the "how it actually happened" layer.

### 3.4 Schedule/rest edges (T2)
Game pages gain: rest differential (days + b2b flags both sides), travel
implicit (venue), market line if the odds snapshot covers the game — and a
descriptive "market vs result" log once games resolve.

---

## 4. League / research surfaces

### 4.1 All-time + era pages (T1/T2) — the sleeping giant
careers.json.gz holds **2005-2026 arcs** and the seasavgs category pulls for
**2005-2025 sit on disk unused** (clutch/defense/usage/scoring/misc — 20
seasons × 5 categories!). Ship: all-time leaderboards by career value, age
curves at league level (with the survivorship caveat rendered), draft-class
trajectory grids, "best statistical seasons of the last 20 years" filters.
This is the cheapest way to add an order of magnitude of browsable history.

### 4.2 Leaderboard upgrades (T1)
/stats: advanced-columns config (four factors, tracking counts), position-pool
+ minute-floor filters, per-36 vs per-possession toggle, era presets. All
client-side over baked docs.

### 4.3 Matchup monitor (T2)
advagg carries per-player-game matchup fields (matchup_fga/fgm/pct, minutes,
partial possessions). Bake season matchup tables: "who actually guarded whom,
and what happened" — descriptive, coverage-honest (the feed's own gaps carry
through the coverage flag we just built).

### 4.4 Activity leaderboards (T1)
Box outs, deflections, charges, loose balls, contested shots, screen assists —
all in advagg since 2019 and barely surfaced. A "hustle & activity" board
with per-36 rates and league bands.

### 4.5 League trend pages (T1/T2)
Zone-mix shift 2019-2026 (3PA share by zone), pace/four-factor trends,
shot-diet vs efficiency scatter per season — the "how the league is changing"
story from baked season aggregates.

### 4.6 League pulse (T1)
Yesterday's box scores with |±| leaders, tonight's slate with rest edges and
market lines (odds), and a "market vs result" running log — see §5.

---

## 5. The market layer (odds snapshots — unique, expiring)

The odds loop snapshots every 20 min until Nov 9 11:36 PT (85 snapshots and
growing; spreads/totals/moneylines per game).

### 5.1 Line-movement charts (T2)
Per upcoming game: spread/total path since market open, annotated with news
events where inferable (rest, back-to-back). Descriptive, no betting advice.

### 5.2 Market-implied win% vs results (T2)
Implied probability (vig-free) from closers vs actual results — a calibration
curve that fills itself as the season plays. Purely descriptive; honest
sample-size flags.

### 5.3 Rest/market interaction (T4 — exploratory, needs a preregistration)
Rest edge vs line movement — only if the owner wants an exploratory read; the
splits-persistence lesson (rebound conversion r=0.221) argues for caution.

**Window note:** these must be BAKED before the trial lapses; snapshots are
already archived, so the data survives regardless — the unique part is the
*continuing* collection through Nov 9.

---

## 6. Model-adjacent (T4 — owner-gated)

### 6.1 WOWY / lineup chemistry
The §2/§4 multi-season ratings (internal-descriptive) + stint minutes →
"chemistry" = unit net minus sum of individual expected (the Closing 5
methodology is in the KB). The campaign closed the *rating* question; this is
the *application* question. Would render internal-labeled, or stay internal.

### 6.2 Impact leaderboards
Same ratings as a sortable internal board with the ceiling caveat attached.
Only if the owner wants a surface at all.

### 6.3 Anything defender-context
Still tracking-gated; the §8 closure stands.

---

## 7. Sequencing recommendation

1. **The identity layer** (1.1 hub, 1.3 reads index, 1.4 methods/glossary,
   1.5 about) — one focused pass; this is what makes it a *research* site.
2. **The sleeping giant** (4.1 all-time/era pages from the unused 2005-2025
   category pulls + 4.2 leaderboard upgrades) — an order of magnitude of new
   browsable history for pure front-end + one small bake.
3. **The big one** (3.2 stint-stitched lineups) — the flagship T3 build.
4. **Market layer** (5.1/5.2) while the odds loop still runs.
5. Player polish (2.1/2.2/2.6) as garnish between passes.

Layout mock for the hub:

```
┌ GOAT HOOPS ─ Games Teams Players Stats Compare Comps Value Research About ┐
│                                                                            │
│  League pulse: OKC 12-2 · NYK 10-4 · …    Tonight: 6 games (2 B2B)         │
│  ────────────────────────────────────────────────────────────────          │
│  [ Luka ▾ ]  ┌ Latest reads ─────────────────────────────┐                 │
│  62.2 TS%    │ §0b BDL↔ESPN gate      PASS  688/688      │                 │
│  36.6 USG    │ §9 shot-making gate    PASS  RA .673      │                 │
│  comps ↗     │ §8 τ-grid RAPM         FAIL  ceiling      │                 │
│              └───────────────────────────────────────────┘                 │
│  Story cards: [Durant's diet] [SGA's climb] [The archetype map]            │
└────────────────────────────────────────────────────────────────────────────┘
```

Color discipline stays: pos/neg/flag = judgment only, heat ramp = volume only,
green/gold = identity only. Verdict chips on /research use the same tokens
(PASS green, FAIL red, TIE/partial violet) — one system, everywhere.
