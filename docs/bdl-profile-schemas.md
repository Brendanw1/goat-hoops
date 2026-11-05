# BDL profile-panel schemas — pinned 2026-11-02 (trial day 1)

Every shape below was verified against real rows (disk or probe), not docs.
This file is the contract for the player-profile build: panels code against
these keys, with one adapter file per panel so field surprises are mapping
fixes, not redesigns. IDs: BDL `player_id` ≠ ESPN athlete id — join through
the normalized-name bridge (same pattern as the LUMA RAPM join).

## Contract panel (data complete on disk)

`contracts_teams_2026.parquet` — 509 player-season salary rows:
`cap_hit, total_cash, base_salary, rank` + full bio (`player.position,
height, weight, jersey_number, college, country, draft_year/round/number`)
+ team. Current-season salaries, license-clean.

`contracts_agg` — 941 rows (multi-row per player: current + prior deals):
`contract_type, contract_status, contract_years, total_value,
average_salary, guaranteed_at_signing, total_guaranteed, signed_using
(Bird Rights et al.), free_agent_year, free_agent_status, contract_notes,
start_year, end_year` + embedded player/team.

`contracts/players` details (queued post-chain, +540 req): year-by-year
rows per player → the salary-bar visual columns.

## Season-average category rows (outer + verified inner keys)

Outer: `{player, season, season_type, stats:{...}}` — `stats` is a dict
whose keys differ per category. Verified:

- `tracking/drives`: `gp, min, drives, drive_pf, drive_ast, drive_fga,
  drive_fgm, drive_fta, drive_ftm, drive_pts, drive_tov, drive_fg_pct,
  drive_ft_pct, drive_passes, drive_pf_pct, drive_ast_pct` (siblings:
  speeddistance, touches→painttouch/posttouch/elbowtouch, passing,
  rebounding, catchshoot, pullupshot, possessions, efficiency, defense).
- `playtype/isolation`: `gp, poss, ppp, pts, fgm, fga, fg_pct, efg_pct,
  poss_pct, percentile, play_type, team_name, ft_poss_pct, tov_poss_pct`
  — **percentile is included per row** (vs-league bars for free).
  Siblings: prballhandler, spotup, transition, postup, cut, handoff,
  offscreen, offrebound, prrollman, misc.
- `shooting/5ft_range`: per-band keys `"<band>_ft._fga/_fgm/_fg_pct"` with
  bands `0-?, 5-9, 10-14, 15-19, 20-24, 25-29, 30-34, 35-39, 40+`.
  (`by_zone` sibling for the zone-tile visual.)

## v2 advanced per-game (probe row)

`id, period, player, team, game, pie, assist_percentage, assist_ratio,
assist_to_turnover, defensive_rating, defensive_rebound_percentage,
effective_field_goal_percentage, estimated_defensive_rating,
estimated_net_rating, ...` at `/nba/v2/stats/advanced` (direct path —
never the ../v2 rewrite).

## Panel build order

1. **Contract panel** — data already complete: current salary from the
   teams pull + deal list (type/years/value/guarantees/FA year/Bird
   rights) from aggregates. Salary bars light up fully once details land.
2. **Tracking + playtype + shooting-zone panels** — parquets land tonight
   (chain steps 2–4); adapters code against the keys above today.
3. **Advanced-rate panel** (PIE, ORtg/DRtg, est. net rating) — v2 advanced
   ×3 seasons, chain steps 5–7.
4. **Career arcs** — wait for phase 2 (1996–2022 history), then light up.

Republication rule unchanged: internal/research anytime; public surfaces
carry BDL numbers only while a subscription is active.

## Site-side derivatives (baked 2026-11-05, hoops_export.py)

**Season convention: BDL keys are the season's STARTING year (2025 =
2025-26); this site labels by ENDING year (2025 = 2024-25). `site_season =
bdl + 1`, applied at bake. Every doc below carries site labels.**

- **Box merge** (into players.json / player docs / team docs /
  games_{season}.json): BDL `stats_{2023,2025}` → site seasons **2024**
  (2023-24, partial 567 games — the walk never finished) and **2026**
  (2025-26, complete 1,230). Board rows gain `oreb/dreb/fgp/tpp/ftp` +
  `src: "bdl"`; player-doc seasons gain `shoot: {fg,tp,ft: [m,a],
  oreb, dreb}` (ESPN seasons too) and game rows carry `ext: 1` (BDL game
  id — no /games page). Cross-source gate: RESULTS-HOOPS §0b.
- **advagg.json.gz** — v2-advanced per-game rows (page dumps + snapshot
  parquets, deduped on (game.id, player.id), jsonl wins) rolled up per
  player-season, site seasons 2019-2026 (six complete through 2025;
  2026 ~half, flagged by `league[yr].rows < 20000`). Per player:
  `gp, min` + rate fields (minutes-weighted means; possessions-weighted
  where the box join has no minutes — seasons ≤2022) + per-36 counting
  fields + sum-rebuilt ratios (`matchup_fg_pct`, `contested_fg_pct`,
  `d_rim_fg_pct`, `matchup_3pt_pct`). `league[yr]` holds league means and
  `{field}|dist` = p10/p25/p50/p75/p90 of player-season values (gp ≥ 5);
  `lower_better` lists the allowance fields the site flips. Field maps
  live in hoops_export.py `ADV_RATE_COLS / ADV_COUNT_COLS / ADV_DERIVED`.
- **careers.json.gz** — `players[eid]` = rows `[season, age, gp, mpg, ppg,
  rpg, apg, ts_pct, usg_pct]`, seasons 2006-2026 site labels (seasavgs
  general base + advanced history pull), active-register bridge only.
- **standings.json** — `seasons[2024|2025|2026]` rows `{abbr(ESPN),
  conference, w, l, pct, conf_rank, home, road}`.

Republication rule unchanged: internal/research anytime; public surfaces
carry BDL numbers only while a subscription is active.
