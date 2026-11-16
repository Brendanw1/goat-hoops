# METRICS — the canonical dictionary

What renders *everywhere*, in what form, with which splits — one dictionary so
two tables never show the same stat under two names. Sources: ESPN box spine
(§0-validated), balldontlie categories + v2-advanced (§0b-validated), and the
KB glossaries (NBA.com stats definitions; closingfive; Cleaning the Glass
conventions). Judgment-color rule everywhere: `pos`/`neg` against the
season's own league bands (baked p10/25/50/75/90), `flag` for partial or
small samples — never both at once.

## 1. The everywhere-set (basic; every player/team surface)

Shown per-game AND per-36 (per-game primary, per-36 as the context column;
"small sample" flagged under 15 GP / 250 min):

| metric | form | source |
|---|---|---|
| GP, GS | counts | ESPN box (GS null on BDL seasons) |
| MIN | per-game | both |
| PTS, REB, AST, STL, BLK, TOV, PF, +/- | per-game, 1dp | both |
| OREB, DREB | per-game | both (board rows + shoot block) |
| FG / 3P / FT | m–a and % | both (player docs `shoot`, board `fgp/tpp/ftp`) |

Team tables carry the same set minus GS/PF, plus PTS/opp PTS and
point differential (colored pos/neg at ±0 — wins do that job).

## 2. The derived canon (advanced; one definition each)

| metric | definition | rendered |
|---|---|---|
| eFG% | (FGM + 0.5·3PM)/FGA — ESPN-box rebuild, §0h-b gated | player page, /stats, /leaders |
| TS% | PTS / (2·(FGA + 0.44·FTA)); ESPN seasons from the §0h rebuild (regular season, Σ/Σ, §0h-b gated), earlier seasons BDL | advanced tables, chips, /leaders |
| USG% | (FGA + 0.44·FTA + TOV) / on-floor team total (minutes-share estimate); ESPN seasons §0h rebuild, earlier BDL | advanced tables (neutral — load, not grade), /leaders |
| AST% / ORB% / DRB% / REB% | NBA.com definitions, on-floor totals by minutes share; ESPN seasons §0h rebuild (r ≥ 0.991 vs BDL), earlier BDL | advanced table, /leaders |
| AST/TO | AST / TOV, season Σ/Σ — §0h-b gated | /leaders |
| FT rate / 3PA rate | FTA/FGA, 3PA/FGA — descriptive (no external counterpart) | /leaders |
| STL% / BLK% | STL / on-floor opp poss; BLK / on-floor opp 2PA — descriptive | /leaders |
| TO ratio | **not rendered live** — §0h-b FAIL (NBA counts FT trips; needs PBP) | — |
| ORtg / DRtg / NET | BDL ratings (minutes-weighted roll-up) + est. variants | advanced table, /stats |
| PIE | BDL pie, BDL seasons only — **not rebuilt**: §0h-b showed BDL's PIE is not the published formula | advanced table, /stats |
| Pace / est. pace | BDL | doc only (context, not rendered as grade) |
| Tracking per-36 | deflections, contested, charges, box outs, screen AST (+pts), loose balls, passes, touches, 2nd AST, FT AST, reb chances, blocks against | Defense & activity panel |
| Matchups | minutes matched, opp FG% / 3P%, rim FG% allowed (lower better) | Defense & activity panel |
| Conversion-of-chances | reb36 ÷ reb chances per 36 | defense panel chip — **context, not skill** (explorations §4) |

## 3. The advantage framework (where a player has an edge)

| split / reference | status | where |
|---|---|---|
| vs league bands (percentile) | **live** | percentile chips, advanced tables, /stats |
| by shot zone vs league FG% (±3 / ±10 pts coloring) | **live** | shot zones table |
| shot-making vs expected (xeFG) — RESULTS §9 | **live** | zones panel chips |
| vs play-type league percentile | **live** | play type bars (BDL percentile baked) |
| defensive matchup quality | **live** | defense panel |
| vs position pool (G/F/C percentiles) | next — position comes from board `pos`; pools need a floor of ~40 players | — |
| rest days (0/1/2+), B2B | computable now from game-log dates; next bake | — |
| home/away, W/L, vs .500+ teams | computable from game logs + standings; next bake | — |
| by month / pre-post deadline (traded players) | computable from game logs (BDL rows carry team changes implicitly via `team`) | — |
| clutch | live (deltas, gp-flagged) | clutch panel |
| schedule strength / opponent-adjusted scoring | needs opponent ratings (Track A/B) | MODELS-ROADMAP |

## 3b. Leaderboards (`/leaders`, §0h)

Qualified = minutes ≥ 500 scaled by the share of the season played (cap
500) AND games ≥ half the team's games. Percentiles rank within the chosen
pool: all qualified, or a position pool (G/F/C) when ≥ 40 qualify. Box stats
rank live in the page; rates carry baked percentiles. Every board states its
n and its status (box score / gated / descriptive). Stabilization-derived
floors replace these defaults once measured (catalog C3).

## 4. Splits canon (what "everywhere" means)

Every player-season table eventually carries these cut dimensions, built from
the game-log grain (the only honest place to cut):

1. **Season** (the unit everywhere).
2. **Venue**: home/away.
3. **Result**: wins/losses (descriptive context, never a grade).
4. **Rest**: 0 days (B2B), 1, 2+.
5. **Opponent tier**: vs winning / losing records (standings join).
6. **Role**: starter/bench; team tenure (games 1–15 post-trade vs rest).
7. **Context windows**: last 10, last 30 (rolling form for live seasons).
8. **Possession contexts**: overall vs clutch (BDL categories); by play type;
   by zone.

Rules: splits render only from the game-log grain (never aggregated-then-cut);
any split cell under 10 games gets the `flag` color; a split never colors a
grade until its persistence is tested (the explorations lesson).

## 5. What we deliberately do NOT render

- Zone-rebound "skill" (conversion is context — explorations §4).
- Cohort aging curves as trajectories (survivorship — explorations §5).
- Clutch deltas without the gp flag.
- Any rating without a RESULTS-HOOPS registration behind it.
