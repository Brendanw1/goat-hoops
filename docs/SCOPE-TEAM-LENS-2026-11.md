# Production scope — the team-lens stat menu (2026-11-08)

The owner's brief: "what is needed to be on the site as if you were asked by
a creative director in the NBA for a team — what stats they want to see," plus
"adding all basic stats" to make goat-hoops a production analytics site.

This doc answers with the menu an NBA team's desks would demand, maps every
item against the inventory we already hold, and fixes the build order. It
sits on top of (does not replace) `hoops-spec.md` (the owner's requirements),
`SITE-BRAINSTORM-2026-11.md` (surface IA, T1-T4), `PROJECTIONS-SCOPE.md`, and
`MODELS-ROADMAP.md`. Where priorities differ, this doc says why.

## 0. The one-paragraph brief

A team's staff does not want "more stats" — it wants every question its five
desks ask daily answerable on one screen, with league context attached, at
two speeds: *what happened* (descriptive, current, sortable) and *what does
it mean* (ranked, compared, projected). The site already covers the player
desks almost end to end. The production gaps are (1) the **team tier is
half-built** — basic averages only, no pace/four-factors/ratings/opponent
views; (2) **lineups/on-off** (spec §4/§5) — the biggest single
answerability gap, derivable from our validated PBP spine; (3) the
**all-time/era tier** — the site's namesake, sleeping on 21 seasons of
category pulls; (4) the **projection tier** — scoped, foundation next; (5)
**currency** — the live season's advanced/tracking layers, which is exactly
what the BDL trial window (ends 2026-11-09 11:30 PT) is for.

## 1. The menu by desk

Status codes: **HAVE** baked on the site · **DERIVE** data on disk, bake-side
work only · **BUILD** needs the PBP/lineup pipeline or a model · **GAP** no
public source · **CURRENCY** trial/window-dependent refresh.

### 1.1 Front-office desk

| Want | Status | Notes |
|---|---|---|
| Production vs cap (surplus board) | HAVE | /surplus; extremes validated |
| Multi-year deal list per player | HAVE | contracts_agg; salary bars need `contracts/players` details (+540 req, pull while trial lives) |
| Comparables / archetypes | HAVE | /comps, similar-players panel |
| Career trajectory + aging adjustment | HAVE (caveated) | career arcs rendered; aging curves survivorship-dominated — context, not skill |
| Stat projections with intervals | BUILD | next model tier; PROJECTIONS-SCOPE fixes the gate |
| Injury/availability risk | DERIVE | BDL injury snapshots held; games-missed derivable from boxes; live refresh dies with trial |
| Draft/rookie translation | GAP | no NCAA/G-League feed in the mart; contracts carry draft slot — rookie cards possible, projections gated |
| Roster-moves feed (trades/waives) | GAP | BDL returns 404 on trades/transactions (probed 2026-11-08); derivable only as contract start/end diffs |

### 1.2 Coaching desk

| Want | Status | Notes |
|---|---|---|
| **Team pace, ORtg/DRtg, net, four factors (own + opponent)** | DERIVE | team_game mart holds every team box; league env from seasavgs pulls. **The "all basic stats" gap.** |
| Full team box (reb/stl/tov/pf splits, shooting) | DERIVE | team docs carry ast/blk/fg/ft only today |
| Team shot profile (zones, diet, making) | DERIVE | shots mart (validated) aggregates to team level; §9 framework carries over |
| Team play-type mix (what do we/they run) | DERIVE (approx) | minutes-weighted roll-up of player playtype rows; possession-true team split is a GAP (BDL is player-scoped) |
| **Lineups: real unit minutes, net ratings, most-used fives** | BUILD | Track B / spec §4-5; the PBP spine (554,869 possessions, response MAE 0.16) is validated and permanent. Site shows starting-five continuity only |
| On/off per player (net, teammate shooting, rebounding) | BUILD | same spine; spec §5; WOWY discipline from the KB (ASA methodology note) |
| Matchup monitor | PARTIAL | player defense dashboards HAVE (matchups 2019-26 in advagg); team-level monitor = roll-up |
| Schedule/rest edges (B2B, travel, opp tier) | PARTIAL | player splits HAVE; team-level edges = same derivation |
| Clutch behavior | HAVE | clutch categories 2005-25 + advagg; game pages carry play feed |
| Screening counts | GAP | no public source (standing note since day 1) |

### 1.3 Scouting desk

| Want | Status | Notes |
|---|---|---|
| Percentile profile vs league and vs position | HAVE | players.json pos pools; Savant-style grid |
| Shot diet vs making (zones, 5-ft, C&S/pull-up) | HAVE | §9 gate passed; zones tables live |
| Tracking skills (drives, touches, passes, deflections, contested, box-outs, rebound chances, speed/distance) | HAVE | advagg 2019-26 — the tier the spec thought tracking-gated; BDL delivered it |
| Play-type PPP with percentiles | HAVE | 12 categories, 2015-25 |
| Archetype map + nearest neighbors | HAVE | /comps |
| Career arcs, era-aligned | HAVE | careers.json 2005-26 |
| YoY self-drift (form storyboards) | T3 | brainstorm §2.5 |
| Prospect/NCAA scouting | GAP | out of scope until a college feed exists (the baseball program's minor-league probe has no basketball equivalent) |

### 1.4 Performance desk

| Want | Status | Notes |
|---|---|---|
| Load (minutes trends, speed/distance per game) | HAVE | v2 advanced per-game rows carry speed/distance/touches by period |
| Rest effects | HAVE (neutral-labeled) | schedule splits render neutral per METRICS.md until persistence is tested |
| Availability | DERIVE | missed games from boxes; BDL injury feed lapses with trial |

### 1.5 Content desk (the creative director's own)

| Want | Status | Notes |
|---|---|---|
| Leaderboards with context | HAVE | /stats; T1 upgrades in brainstorm §4.2 |
| All-time + era pages | DERIVE | **the sleeping giant** — 2005-25 category pulls unused on-site; era baselines from the same pulls |
| Shareable visuals (shot charts, heat maps, arcs, percentile cards) | HAVE (components) | export-as-image = polish pass |
| Hub storytelling | HAVE | league pulse, reads strip, story cards |
| Methods/glossary trust layer | HAVE | /methods, METRICS canon, /research verdicts |
| Market layer (line movement, implied vs actual) | CURRENCY | odds snapshots are the one expiring asset; loop ends 2026-11-09 |

## 2. Currency — what the trial window is for (ends 2026-11-09 11:30 PT)

1. **v2 advanced stream tail** — 2025-26 back half + playoffs + live 2026-27
   rows sit at the stream's end; the walk (resumed 2026-11-08 ~10:15, 4.3
   pages/min, checkpointed, deadline-halted) is the only path to them.
   Flagship-season completion is the production blocker this window exists
   to remove.
2. **Live-season seasavgs (bdl label 2026)** — the live season's
   tracking/playtype/shotdashboard category rows were never pulled. ~25-40
   files, small. Pull after the walk exits (one request stream).
3. **`contracts/players` details** (+540 req) — year-by-year salary for the
   contract timeline. Pull with leftover budget after 2.
4. **Odds snapshots until the deadline** — the loop already runs to 11-09.
5. **stats_2023 completion** — resume only after 1-3 land (shared 5 rpm).
6. **Injuries refresh** — one last snapshot at the deadline.

**Verdict for the owner: cancel the trial after 2026-11-09 11:30 PT, not
before.** After the deadline the only BDL-only items left are refresh cadence
(live advanced, injuries, odds), all of which can ride a future catch-up
window (a one-month resub mid-season, owner's call) — the free ESPN spine
keeps boxes/standings/scores flowing regardless, and 21 seasons of category
history are already ours. Nothing else in the build order needs BDL.

## 3. Production build order

1. **P1 — Team tier completion** (the owner's "all basic stats"): pace,
   four factors, ORtg/DRtg/net own+opp, full team box, team shot profile,
   team play-type mix, rest edges — one bake pass off the mart + team-page
   analytics tab. Gate: agreement check vs BDL seasavgs roll-ups (the §0b
   pattern) + LUMA scores cross-check.
2. **P2 — All-time/era** (sleeping giant): era pages + all-time leaderboards
   from the 2005-25 pulls; era baselines also feed P4 features.
3. **P3 — Lineups/on-off** (Track B, the big one): unit minutes and on/off
   from the validated spine; internal-labeled net ratings per the campaign's
   standing verdict.
4. **P4 — Projections** (PROJECTIONS-SCOPE): foundation artifacts → §11
   ridge+age+lags → panel only after a gate passes.
5. **Cross-cutting polish** between passes: responsive/component pass, empty
   states, export-as-image visuals, the odds line-movement charts before the
   loop ends.

Nothing here re-opens the RAPM gate (§8 closure stands) or renders
unlabeled judgment; every new number ships descriptive with league context,
per METRICS.md.
