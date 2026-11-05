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
