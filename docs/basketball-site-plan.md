# Goat-Pro Hoops: the site plan (2026-10-30)

Phase plan for the basketball site, using everything verified in
`docs/basketball-gap-map.md` and the `hoops_mart`. Same rules as baseball:
public data, pre-registered models, descriptive labels until a gate passes,
sources validated against each other before anything ships.

## Where it lives

**Its own repo and app (this repo, since 2026-10-29):** `goat-hoops`, deployed
separately, linked to goat-pro by a sport-switcher pill in both navs (prod:
`hoops.goatpro.dev` next to `goatpro.dev`; dev: ports). Same design system and
culture as baseball, its own R2 prefix (`hoops/` — disjoint from goat-pro's
`goatpro/`, so neither site's exact-mirror sync can ever prune the other's
keys), its own ledger (`COLLABORATION.md`) and evidence file
(`pipeline/RESULTS-HOOPS.md`). The data layer stays in
`~/Projects/vt_baseball/hoops_mart`, read-only from here — the same shape as
goat-pro reading `savant_mart`.

## Verified sources (basketball-gap-map.md)

| source | carries | role |
|---|---|---|
| ESPN public API | scoreboard, game summaries: PBP (487 plays/game, x/y shots), box scores | the feed — built, running (`hoops_mart/ingest_daily.py`) |
| LUMA (CourtShare) MCP | box scores 1997–2027, ARC, xpts_rapm, lineups, on/off, WOWY, 113 channels | validation + long history + model benchmark |
| pbpstats API | possessions (events, start types), shot-level with depth filters, per-game lineups, team possessions per game | RAPM inputs + validation |
| balldontlie | plays, advanced stats incl. tracking (speed/distance/touches), lineups, **contracts** (terms §6: republication allowed) | advanced + tracking + D-44/D-46 unblock — needs the owner's free `BDL_KEY` |
| nba.com hosts | PBP, shot detail, tracking | **blocked from this network**; browser-route test pending |

## The owner's spec

`docs/hoops-spec.md` is the requirements document: all regular + per-36 +
advanced stats per player and team, impact isolation (shot creation,
playmaking, rim penetration; POA vs help defense), rebounding zones with
heatmaps and vs-average, team impact with role decomposition (gravity,
passing, screening), on/off everywhere, then projections/career curves and
Savant-style percentile cards. The phases below are reordered around it:
the statistics foundation and the on/off/lineup pipeline come first because
most of the spec builds on them; projections stay last.

## Phase 1 — the data spine + first surfaces (DONE locally 2026-10-29)

1. **ESPN backfill**: 830+ summaries (2024-25 in progress via the schedule
   sweep + 2026-27 to date), resumable receipts; continues daily.
2. **hoops mart tables** (vt_baseball/hoops_mart `build_mart.py`): `games`,
   `team_game`, `player_game`, `pbp` (the possession spine; possessions are
   DERIVED later with the pre-registered RAPM build), `shots` (x/y normalized
   to the attacking half, FTs flagged). Internal audits close player points to
   team points everywhere; ESPN noise floors recorded (running-score drift
   8/831, PBP-vs-box FGA ±1-2 on ~6% of team-games — boxes canonical for
   aggregates, plays/shots for locations).
3. **Validation gate PASSED** (hoops_mart `luma_check.py`): 688/688 exact game
   scores 2024-25, 52/52 to date 2026-27, 324 player-game boxes with every stat
   100% exact except assists (scorer judgment); LUMA credited in the bake's
   meta.json. LUMA home-flag defect recorded (5 games, both rows false).
4. **First surfaces** (descriptive, baked by `pipeline/hoops_export.py` to
   `hoops/...` keys, `--check` no-op verified, `next build` gated, verified in
   the browser against the local bake):
   - `/hoops` landing (validation note + recent games + season links)
   - `/hoops/games` finder (season/type/paged, query-string state)
   - `/hoops/games/[id]` — game report: boxes, team lines, x/y shot chart
     (filters + hover), full play feed
   - `/hoops/teams` + `/hoops/teams/[abbr]` — standings and club pages
   - `/hoops/players` + `/hoops/players/[id]` — leaderboard and game logs
   Ship step when the owner wants it live: `r2_sync.py --path hoops` (data
   files stay local until then, per the local-first call).

## Phase 1b — the BDL statistics foundation (DONE locally 2026-11-05)

The GOAT-trial harvest (2026-11) landed, and spec item 1 — "all regular
player statistics, per game and per season, basic + advanced, per player AND
per team" — is on the site:

1. **Second-source gate PASSED** (RESULTS-HOOPS §0b): BDL vs ESPN on the
   shared 2024-25 season — 688/688 game scores exact, 11,326 boxes with
   pts/reb/ast 100% exact. Season-convention hop (BDL starting-year → site
   ending-year label) applied at bake; the pre-fix seasavgs docs were
   mislabeled by one year and are corrected.
2. **Seasons on the site**: 2023-24 (BDL, partial 567 games — walk unfinished,
   flagged), 2024-25 (ESPN + the BDL cross-check), **2025-26 complete
   (BDL, 1,230 games — new)**, 2026-27 live (ESPN). Players board, player
   docs (season lines + game logs), team docs, game finders all gained the
   BDL seasons; balldontlie game ids carry `ext` and render without links.
3. **Advanced roll-ups** (`advagg.json.gz`): balldontlie v2-advanced per-game
   rows deduped and rolled up per player-season, 2018-19 → 2025-26 (six
   complete seasons through 2024-25; 2025-26 ~half covered, flagged). Rates
   are minutes-weighted, ratios rebuilt from sums, counting stats per-36;
   league mean + p10/25/50/75/90 bands per field power the good/bad coloring.
   Carries the tracking tier the spec thought tracking-gated: defensive
   matchups, contested shots, box outs, charges, deflections, screen assists,
   loose balls, passes/touches, rebound chances.
4. **Career arcs** (`careers.json.gz`): per-season lines 2005-06 → 2025-26
   from the seasavgs history pull (active-register bridge; retired stars have
   no ESPN page to hang an arc on).
5. **Standings** (`standings.json`): 2023-24 → 2025-26 from the BDL snapshot.
6. **Surfaces**: player page rebuilt (season statistics table, career arc,
   advanced rates by season vs league bands, defense & activity panel, BDL
   game logs); new `/stats` sortable leaderboard (basic + advanced merged,
   judged columns colored against the season's own bands); teams board got
   win% bars + point-differential colors. Semantic tokens (`pos`/`neg`/`flag`)
   replace ad-hoc judgment hexes app-wide.
7. Bake `--check` no-op verified (advagg intentionally drifts while the
   advanced walk still appends — re-synced per bake), `r2_sync` mirrored
   (1,651 keys; stale `seasavgs_2023.json.gz` pruned).

## Phase 2 — derived models (each pre-registered before the first fit)

- **RAPM** from ESPN PBP stints (+ pbpstats possessions as the segmentation
  check), benchmarked against LUMA's `xpts_rapm`.
- **Shot quality / xPTS** from the x/y shots, benchmarked against LUMA channels.
- **Lineup grades** (from ESPN-derived lineups), checked against LUMA's
  `lineups`/`onoff`.
- **Tracking-adjacent stats** once `BDL_KEY` lands (speed/distance/touches).

## Phase 3 — the deep surfaces

Player profiles with ARC-style rating decomposition (ours), lineup explorer,
WOWY, the matchup surface — each modeled on its baseball counterpart and
gated the same way.

## What's still open

- `BDL_KEY` (owner registers at balldontlie.io) — unlocks contracts
  (D-44/D-46 basketball-side) and tracking stats.
- nba.com direct (tracking raw): browser-route test, or the owner's
  impersonation call — not needed for Phases 1–2.
- LUMA cross-feed reconciliation at scale (the paged `box_game` pull).
