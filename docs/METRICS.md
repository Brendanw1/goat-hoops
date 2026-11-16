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
| BPM | Myers' BPM 2.0, published coefficients, season level per team stint (`pipeline/bpm.py`): box per 100 player possessions, estimated position and offensive role (team-constrained to 3.0), points adjusted for team shooting (1.00 pts/TSA baseline, reconstructed), team adjustment to the team's net rating (no SOS / lead correction) — §16 gated: r 0.673 vs LUMA xPTS-RAPM, Game Score/36 0.470; year-to-year 0.79 | /leaders, player page |
| OBPM / DBPM | OBPM: Myers' published offensive coefficients and constant on the same inputs, team-adjusted so a team's minutes-weighted OBPM equals its ORtg − league ORtg; DBPM = BPM − OBPM, so the halves always add to BPM — §16-b gated: OBPM r 0.711 vs LUMA xPTS-RAPM offense (points/36 0.521), DBPM r 0.615 vs LUMA defense ((STL+BLK)/36 0.426) | /leaders, player page |
| VORP | (BPM + 2.0) · share of team minutes · team games / 82, summed over stints | /leaders |
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

**Regressed values (§17, `pipeline/shrink.py`).** Beside the raw value,
each rate shows (min·x + k·μ) / (min + k): μ = the qualified pool's
minutes-weighted mean that season, k (minutes) from odd/even split-half
reliability on 2024-25 (k = m·(1 − r)/r). Held out on 2025-26 first half →
second half, it cut prediction error on all 32 stats (median 9.4%). k ranges
from ~20 min (3PA rate, USG%) to ~7,300 (mid-range FG%). Percentiles stay on
the raw value; the board ranks by raw by default and by the regressed value
with **Rank by: Regressed** (`?rank=reg`), which discounts hot small samples.

**Attempt exposure (§17-b).** Where it predicted the second half better,
exposure is attempts rather than minutes (μ then attempt-weighted): 3PA rate
(FGA), corner-3 and pull-up rate (shot FGA), self-created % (shot FGM),
putback rate (offensive rebounds), xeFG and shot-making (shot FGA). Shooting
percentages keep minutes: skill and volume are correlated, so an
attempt-weighted mean sits above what low-volume shooters make and would
inflate them. FT fouls drawn/36, and-ones/36, OBPM and DBPM regress on
minutes. The board names the exposure it used.

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
| FT fouls drawn/36 | free-throw trips the player starts (`Free Throw - [Flagrant / Clear Path] 1 of N`, technicals excluded) per 36: ESPN names only the fouler, so the drawer is the next FT shooter. Counts only fouls that reach the line (no offensive or non-bonus fouls) | gated §18 (r 0.958 vs NBA.com PFD; implied FTA exact) |
| And-ones (count, /36) | a `Free Throw - 1 of 1` by a player who made a FG at the same game clock | gated §18 |
| Expected eFG (xeFG) | per-shot make probability from distance, |angle|, zone, 3PA flag and outcome-neutral ESPN shot families (finish: dunk/layup/hook/tip/jumper; ten action flags; "bank"/"reverse"/"finger roll" dropped as after-the-fact descriptors), gradient boosting, no shooter identity (`pipeline/xefg.py`); xeFG = mean of p·(1.5 for threes) over the player's FGA; FGA floor 200 | gated §20 (held-out log loss −2.9% vs the §9 zone table) |
| Shot-making | eFG − xeFG on the same (heave-excluded) shots | gated §20 |
| Putback rate | share of the player's offensive rebounds whose next shot event is their own FGA, same period, within 3 s of game clock | descriptive |

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
7. **Context windows**: last 10, last 30, by month (live on the player
   page's splits panel, cut at render from the baked game log), plus
   trailing 10-game sparklines for PTS/REB/AST — neutral color.
8. **Possession contexts**: overall vs clutch (BDL categories); by play type;
   by zone.

**Team context (team page, descriptive, §18 block):** four factors as
diverging bars vs the league (opponent FT rate added to the team grain);
strength of schedule = opponents' season net rating averaged over games
played (and net + SOS); clutch = last 5:00 of Q4/OT with the margin ≤ 5
before the play, W-L, points and net per 100 possessions estimated from the
box over clutch events (`pipeline/clutch.py` → `team_clutch.json`).

**Player on/off (player page, §0f, descriptive).** Team net rating per 100
possessions with the player on vs off the floor, on-court ORtg/DRtg, where
the swing ranks among teammates past the same floor, and the player's
most-used five-man units, all from the §0f stint walk of ESPN play-by-play
(events in clock order since §21: possessions within ±2 of pbpstats in 96.7%
of 2024-25 team-games, player minutes within a median 0.35 min of the box).
Floors: 1,500 on-court and 500 off-court possessions; under ~2,500 on-court is
flagged small; units under 500 possessions are labelled anecdotes. Raw, not
adjusted for teammates or opponents (RAPM, which would, has not passed its
gate).

**Rookie race (`/rookies`, descriptive, `pipeline/rookies.py`).** Rookies =
drafted the summer before the season (BDL draft bio) plus undrafted players
whose first ESPN-spine game is that season. Weekly cumulative Game Score as a
bump chart (rank each week, lead changes ringed); a scatter of regressed BPM
vs minutes; a standings table. Game Score is a volume measure: it rewards
minutes, which is why the scatter sits beside it.

Rules: splits render only from the game-log grain (never aggregated-then-cut);
any split cell under 10 games gets the `flag` color; a split never colors a
grade until its persistence is tested (the explorations lesson).

## 4b. Sources

Every stat family's feed call, method, code path, gate and reference live in
`pipeline/sources.py`, baked to `sources.json` (rendered at /methods#sources)
and written to `docs/SOURCES.md` at each bake.

## 5. What we deliberately do NOT render

- **Win probability / WPA** (§19 FAIL, then §19-b FAIL, 2026-11-16): after
  fixing the play-order defect it beats score-and-time on Brier by 8.5% but
  misses the calibration bar (ECE 0.0168 vs 0.015). Diagnosis: home-win rate
  drift between the two seasons and an overconfident pre-game strength
  slope. Next step is more seasons (ESPN PBP backfill 2019-20 → 2023-24) and a
  §19-c; no third test on the same two seasons.

- Zone-rebound "skill" (conversion is context — explorations §4).
- Cohort aging curves as trajectories (survivorship — explorations §5).
- Clutch deltas without the gp flag.
- Any rating without a RESULTS-HOOPS registration behind it.
