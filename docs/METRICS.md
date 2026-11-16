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
| TO ratio | 100·TOV / (FGA + FT trips + AST + TOV); a trip = a PBP `Free Throw - 1 of 2` or `1 of 3` (and-ones, technicals, flagrants, clear paths excluded); lower is better — §0h-c gated (held out, 0.9997) | /leaders |
| Offensive Load | Ben Taylor: 0.75·(AST − 0.38·BoxCreation) + FGA + 0.44·FTA + BoxCreation + TOV, per 100 player possessions (minutes share × average team possessions) — §0j gated vs LUMA `load` (r 0.986), level with a plain plays-per-100 sum; volume, not quality | /leaders, player page |
| Box Creation | Taylor 2017 formula — **not rendered**: §0j FAIL (plain AST/100 tracks LUMA `lcreation` at 0.98 vs 0.86); computed only inside Offensive Load | — |
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

Attempt-based stats add an attempt floor on top (full season; scaled for
the live season): rim FG% 100 rim FGA, mid FG% 60, corner 3P% 40,
above-break 3P% 100, pull-up eFG% 100.

## 3c. Shot creation and playmaking (`pipeline/creation.py`, §0i)

From ESPN play-by-play (`shots` ⋈ `pbp` on `play_id`), regular season,
heaves excluded (the box stopped counting them as FGA in 2025-26).

| stat | definition | status |
|---|---|---|
| rim / mid / corner-3 rate | zone FGA / FGA; rim = 2PA within 4 ft, paint = other 2PA in the lane, mid = other 2PA, c3 = 3PA within 14 ft of the baseline, ab3 = other 3PA | gated §0i-A |
| rim / mid FG%, corner / above-break 3P% | zone FGM / FGA | gated §0i-A |
| self-created % | unassisted FGM / FGM (assisted = PBP assister on the make) | gated §0i-B |
| self-created FGM/36, 3PM/36 | unassisted makes (threes) per 36 min | gated §0i-B |
| AST points/36 | (2·assists on 2s + 3·assists on 3s) per 36 | gated §0i-B |
| AST to 3s/36, AST at rim/36 | assists by the receiver's shot (3PM; rim make) per 36 | gated §0i-B (rim: A+B) |
| pull-up rate, pull-up eFG% | ESPN "Pullup"/"Step Back" shot labels: share of FGA, eFG on them | descriptive |
| bad-pass / lost-ball TO/36 | PBP turnover types (incl. out-of-bounds variants) per 36 | descriptive |
| Game Score | Hollinger: PTS + 0.4FGM − 0.7FGA − 0.4(FTA−FTM) + 0.7ORB + 0.3DRB + STL + 0.7AST + 0.7BLK − 0.4PF − TOV, per game | box |
| 30/40-pt games, double/triple-doubles | counts; doubles over PTS/REB/AST/STL/BLK | box |

Shot types are exclusive, first match wins: putback/tip > alley-oop >
cutting > driving > step-back > pull-up > other. The player page's shot
creation panel shows zone makes split assisted vs self-created and the type
diet with eFG.

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
