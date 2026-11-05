# RESULTS-HOOPS — the evidence ledger

Basketball's version of goat-pro's `RESULTS-MLB.md`: every model gets a
pre-registered section here **before its first read**, then the verdict, the
gate numbers, and the caveats live here forever. House rules are in
`AGENTS.md`; the short form: pre-register, read once, diagnose failures as
data vs handling vs modeling, never reword a gate after the read.

## §0 — Validation gate (not a model): the LUMA cross-check, 2026-10-29

Not a model — the two-source bar every surface clears before it renders.
Built and run in `~/Projects/vt_baseball/hoops_mart/luma_check.py`; the
numbers live there and in the bake's `meta.json`:

- **Game-level, 2024-25**: 688/688 joined games, scores exactly equal.
  Join key: (US/Eastern date, unordered team pair) — ESPN timestamps are UTC;
  LUMA's `home` flag is false on both rows for 5 games, so the flag is never
  trusted. The one non-join is the NBA Cup final (LUMA classifies it outside
  `regular`).
- **Game-level, 2026-27 to date**: 52/52 exact (join rate 73% — LUMA's ingest
  lags ~3 days, not disagreement).
- **Player-game boxes**: 324 boxes, 16-game deterministic sample; every stat
  100% exact except assists (322/324 — scorer-assignment judgment). Name join
  after suffix-stripping: 0 unmapped players.
- **Internal ESPN consistency**: player points close to team points in every
  game; ESPN's per-play running scores drift on 8/831 games (score_value
  stream always closes); PBP-vs-box FGA differs ±1–2 on ~6% of team-games.
  Standing rule: **box columns are canonical for aggregates; plays/shots for
  locations and sequencing.**
- Credit: LUMA Basketball Research (ARC v3.1, LOKI v3.3).

## §0b — Second-source gate: balldontlie vs ESPN (passed 2026-11-05)

Not a model — the bar the balldontlie GOAT-trial box layers clear before their
seasons (2023-24 partial, 2025-26 complete) render on the site. Same shape as
§0: an independent source compared on the season both cover (BDL season key
2024 = the 2024-25 season = ESPN label 2025). Computed at bake time
(`hoops_export.py bdl_espn_check`) and carried in `meta.json`:

- **Game scores**: 688/688 joined games, home/away scores exactly equal
  (join key: date + unordered team pair, ESPN abbreviations).
- **Player boxes**: 11,326 bridged (player, date, team) lines — points,
  rebounds and assists 100% exact; minutes 99.82% exact (MAD 0.002 — the
  residual is ESPN rounding minutes to tenths).
- **Convention note**: balldontlie season keys are the season's STARTING
  year (2025 = 2025-26); this site labels by ending year. The hop
  (`site_season = bdl + 1`) is applied at bake — the pre-fix seasavgs docs
  were mislabeled by one year, corrected in the same change.
- Coverage shipped: 2025-26 complete (1,230 games), 2023-24 partial (567
  games — the stats walk did not finish; flagged "partial" on every surface).
- Credit: balldontlie (owner's GOAT-trial snapshot 2026-11; public surfaces
  carry these numbers only while a subscription is active).

## Next pre-registrations (planned, not yet written)

- **§1 RAPM from ESPN PBP stints** — stint-level possessions from the pbp
  spine (possession segmentation derived + documented first), ridge RAPM,
  benchmarked against LUMA `xpts_rapm` on shared seasons. The prereg must fix:
  the stint definition, the possession stitch, the ratings/OT handling, the
  lambda grid, the splits (train ≤2025, test 2026), and the agreement bar.
- Shot quality / xPTS from the x/y shots vs LUMA's channels.
- Lineup grades vs LUMA `lineups`/`onoff`.

## §9 — Zone shot-making vs expected (pre-registered 2026-11-05, before any bake or read)

**Why.** The site shows raw zone FG% (Shot zones table) and attempt-density
heat maps, but never answers the only interesting question: is this player
finishing better than a league-average shooter would on the same shots? The
KB carries the methodology (closingfive "shot-making over expected (xeFG)":
expected efficiency from the player's own shot-zone mix × league zone
efficiency — arxiv §3.3.2 shot selection is the frame; NBA.com glossary the
metric definitions). Descriptive benchmark against a defined reference, not a
forecast, not a possession-level model.

**The definition (fixed now).**
- League zone FG% = fga-weighted aggregation of the seasavgs
  `shooting_by_zone` player pool per season, per BDL zone (7 zones:
  restricted area, paint non-RA, mid-range, L/R corner 3, above break 3,
  backcourt). Computed at bake into each seasavgs doc as `leagueZones`.
- Player expected eFG (xefg) = Σ_player(zone fga × league zone FG%) / Σ fga —
  his real shot diet priced at league rates (2s/3s values differ per zone, so
  the zone percentages already carry the value dimension).
- Shot-making = real eFG − xefg (season eFG from the same category pull).
- Floors: a zone needs 20 league FGA and a player zone needs 10 FGA to enter
  the per-zone table; the player-level xefg needs 50 total FGA.
- Shipped fields: `leagueZones` (doc-level) and per-player `shootmk`
  {xefg, efg, diff, n_fga} in the seasavgs docs; player zones table gains the
  league column and advantage coloring.

**Gate (checked at bake, recorded here).** League zone FG% ordering must
respect court geometry: restricted area > non-RA paint, corners > above-break
3, backcourt lowest. A violation stops the render (fields stay unbaked).

**Reported.** League zone table per season; per-player chips; the zones
table's advantage coloring. Explicitly NOT claimed: predictive power,
shot-selection quality (xefg itself is the shot-diet summary — shown
alongside so difficulty and finishing never blur).

Caveat (carried from the KB): location-based, so it rewards tough
shot-making; a rim-running big's diet does most of his work in xefg itself.
