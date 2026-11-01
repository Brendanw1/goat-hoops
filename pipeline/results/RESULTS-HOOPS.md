
## §1 — RAPM from ESPN PBP stints (pre-registered 2026-10-30, before any derivation or fit)

**Why.** The spec's on/off, lineup and team-impact surfaces all need a
baseline-plus-minus spine, and LUMA's `xpts_rapm` gives an external
benchmark. First model of the program; the possession/stint derivation it
needs ships only under this registration.

**Data.** ESPN PBP 2024-25 regular season only (the full season of the
gate-passed spine; other seasons are later work, not part of this read).
Benchmark: LUMA `xpts_rapm` view, season 2025, pulled BEFORE the read into
`hoops_mart/data/luma/xpts_rapm_2025.parquet` and not looked at until step 4.

**The derivations (fixed rules).**
- *Possession*: a segment of plays controlled by one team. Control transfers
  on: defensive rebound (rebounding team = new offense), any turnover (offense
  = the other team), made FG (segment ends after the make; any and-one FTs
  append to the ending segment; opponent's next controlled play starts their
  possession), made last FT followed by opponent control, period start. FT
  misses are resolved by the rebound rule. Edge plays (jumpball, end-period)
  end segments. Every rule applied mechanically; no season-specific tuning.
- *Stint*: interval between consecutive substitution events (either team),
  within a period. On-court set starts each period from the box `starter`
  flag; OT periods (5+) inherit the previous period's final set (data
  limitation, accepted). Substitution plays apply p1 in / p2 out (99.99%
  carry both; the remainder are logged and skipped). Stints where either side
  cannot field exactly 5 known players are dropped (count reported).
- *Internal validation (handling gate, before any model read)*: derived
  per-team-game possession counts vs pbpstats' counts (independent source,
  in hand) — ≥95% of team-games within ±2, MAE < 1.5. Player stint-minutes
  vs box MIN: median |Δ| ≤ 0.5 min.

**The model (fixed).** Row = one stint, response = point margin (offense
minus defense) for the possessing side, predictors = ±1 indicators for the
10 on-court players (offense +1, defense −1) plus one home-court fixed
effect (home offense +1, away offense −1; no intercept), weights = stint
possessions. Ridge, λ grid {100, 300, 1000, 3000, 10000} on the
possession-weighted design; λ chosen by weighted 5-fold CV *within 2024-25*
(grouped by game, player-overlap folds ignored for v1 — documented). Ratings
reported per 100 possessions (ORAPM from the offense coefficient, DRAPM from
the negated defense coefficient).

**Judged (read once).**
1. *Benchmark*: Pearson r between our RAPM and LUMA `xpts_rapm` (season
   2025) over shared players with ≥250 possessions. **Gate: r ≥ 0.70.**
2. *Stability*: split-half (even vs odd ESPN game ids), r between halves on
   players with ≥500 possessions in both. **Gate: r ≥ 0.60.**
Failure diagnosis: data (possession/stint errors) vs handling (weights,
filters) vs modeling (λ, response choice), in that order.

**Shipping rule.** Both gates pass → ratings earn a "Phase 2 model" label
and a surface in a later session (still descriptive until a forecast gate
exists). Any gate fails → no surface; verdict and diagnosis recorded here.

**Expected.** r vs LUMA 0.70–0.85 (single-season ridge on ~240k possessions
should track their xPTS-based RAPM on the strong-minute players); the
weakest agreement on low-minute players, which the ≥250-possession filter
excludes. Risk: possession-definition mismatch vs pbpstats (gate 0 catches
it before the fit), and starters' OT inheritance biasing late-game stints.

### §1 handling-iteration log (2026-10-30, no model read has happened)

Gate status after five derivation iterations (689 games, 2024-25):

| Iteration | Possession gate | Minutes gate | Change |
|---|---|---|---|
| v1 naive | FAIL 34.6% / MAE 3.54 | — | baseline state machine |
| v2 +timeout/kicked non-control | FAIL 78.5% / MAE 1.60 | — | defensive timeouts were splitting possessions ~13×/game |
| v3 blanket dead-ball FT | FAIL 28.2% / MAE 4.15 | — | overcorrected: killed the FT team's possession |
| v4 exit-always subs | FAIL 36.8% / MAE 3.67 | FAIL 6.2 min | half the stints dropped (4-man windows) |
| v5 current (carryover + simple FT flip) | **FAIL 84.8% / MAE 1.37** | FAIL 14.7 min | best; MAE under the 1.5 bar, within±2 still short |

Diagnosed causes, each verified forensically:
1. **Timeouts/violations are non-control** (fixed, v2): a defensive timeout
   used to transfer possession.
2. **ESPN's sub log is direction-consistent but INCOMPLETE**: the play text's
   "enters" name matches participants[0] 3,280:0 (direction settled), yet
   re-entries appear without a logged exit+entry pair (forensic: Risacher out
   at idx 58, back on court by idx 73 with no sub row). Sub-classification
   over 100 games: 43% forward, 31% look-reversed, 16% both-on, 10% stale —
   the non-forward share is our state drifting against an incomplete feed,
   not direction ambiguity.
3. **Lineups carry across periods** (fixed): resetting Q2–Q4 to Q1 starters
   poisoned every later period (the hidden cascade behind v1's "0 skips").
4. Next fix (designed, not yet implemented): **evidence-based drift
   correction** — when a non-sub play's primary participant (shot/FT
   shooter, rebounder) is not in his team's on-court set, add him and split
   the stint at the correction; the set of five re-validates continuously
   from the play stream itself. Subs remain the primary signal; the play
   stream heals the gaps. This is the standard approach for incomplete PBP
   feeds and should clear both gates; the three-way check (ours vs pbpstats
   vs the classic FGA−OREB+TOV estimate) stays queued to attribute any
   residual convention difference.

### §1 read v1 (2026-10-30): FAIL on both gates — diagnosis: λ selector

The one read, as registered: 91,091 possession rows (69% coverage; the rest
involves 13 fringe players whose pbpstats intervals are empty), 515 players,
λ=10000 by possession-level MSE CV. **Stability r = 0.157 (bar 0.60) — FAIL.
LUMA benchmark r = 0.220 on 356 shared players ≥250 poss (bar 0.70) — FAIL.**

Diagnosis (data vs handling vs modeling): **handling — the λ selector.**
- The model itself is sound: the top-10 is real basketball (Jokic 1.33,
  Edwards, Tatum, KAT, Mobley; Kornet/Horford/Ellis role-player signal;
  Poole/Sarr/Giddey at the bottom) and the LUMA join verified player-aligned
  (Jokic 1.33 vs their 2.19).
- But possession-level held-out MSE is nearly flat across the whole grid
  (0.9826 → 0.9816): single-possession noise drowns the rating signal, so
  the criterion cannot see rating quality and picked the grid edge. At
  λ=10000 with ~1,500 possessions/player, each coefficient shrinks to
  n/(n+λ) ≈ 13% of OLS — the ordering partially survives (top-10 ok) but the
  correlation with a full-strength external RAPM collapses.
- Amended criterion (handling, pre-results for v2): λ chosen by the same
  5-fold game-grouped CV, but scored on **game-level aggregate margins**
  (sum of possession points per team-game) — the quantity ratings are judged
  on. Gates unchanged; the λ grid unchanged; this is the prereg's own
  failure-diagnosis loop, not a gate edit.

### §1 handling-iteration log, part 2 (2026-10-30, still no model verdict)

The v2 read (λ=300 verdict slot) never happened: forensic validation of the
response killed it first — **the possession points summed −54 to −77 per
team-game against the box scores, exact matches 0%**. Root cause chain:
1. `idx` only advanced on segment-opening plays, so every score-delta window
   read the wrong plays (fixed: uniform per-play indexing).
2. Boundary convention double-counted each scoring closer (fixed: the
   transfer play belongs to the new segment).
3. **ESPN's feed misorders plays around scoring sequences** (proven: a
   turnover row sits before the made basket that followed it; running-score
   evidence is authoritative, play order is not) — so ANY play-attribution
   of points to possessions is unreliable, however correct the bookkeeping.
   The five earlier possession-gate failures (±1.37 MAE floor) were the same
   disease showing in counts.

**Architecture change (v6, in flight): the RAPM response moves to pbpstats'
own possessions** (`get-possessions`, official NBA.com logs — immune to ESPN's
misordering): per-team-season pulls landed at the correct scale (ATL 8,426
offensive possessions) after fixing the 500-row page-cap truncation (7-day
date slices). Points derive as 2×FG2M + 3×FG3M + made FTs from the Events
text — validated −862/10,973 (−7.9%) for ATL, attributed to FT-attribution
phrasing (and-one/technical FTs); the parser fix is next, with the box-sum
check as its gate. On-court sets come from the same source's playing-time
intervals — **minutes gate PASSED (median |Δ| 0.28 min, 14,461
player-games)**. rapm.py (possession-level ridge, both gates, λ-sensitivity
diagnosis table) is committed and will read on the corrected response.

### §1 read v3 (2026-10-31, corrected response): FAIL on the benchmark gate — model family validated, bar not met

Response fixed (pbpstats possessions; points MAE 0.16 vs ESPN box, 99.8%
within ±2 — two-source agreement), rosters from official intervals (minutes
gate 0.28 min). Grid re-opened as a documented amendment (the original range
was calibrated against the broken response). 132,066 possession rows with
exact-5v5 rosters, 516 players.

| λ | split-half r | LUMA benchmark r |
|---|---|---|
| 100 | 0.054 | 0.294 |
| 300 | 0.098 | 0.321 |
| 1000 | 0.167 | 0.361 |
| 3000 | 0.278 | 0.407 |
| 10000 | 0.454 | 0.454 |
| 30000 | 0.575 | **0.464 (peak)** |
| 100000 | **0.631** | 0.455 |

**Verdict: FAIL — no λ meets both gates.** Stability crosses its 0.60 bar at
λ≈100000; the benchmark peaks at 0.464 (λ=30000) against the 0.70 bar.

The model is real: the λ=30000 top-10 is SGA, Jokic, Tatum, Mobley, then the
impact-role tier (Isaiah Joe, Horford, Dort, Kornet, Jarrett Allen), with
Washington's young core at the bottom — the ordering passes inspection. The
0.46 ceiling vs LUMA measures the design distance, not a data bug: their
xpts_rapm is a multi-season, shot-quality-expected (xPTS) model with priors;
ours is a single-season, raw-points, no-prior RAPM. Roadmap to the bar, in
order of expected gain:
1. **Multi-season fit** — the same backbone extends to 2022-23/2023-24 (the
   pt/possessions pulls are per-season); multi-season RAPM is the
   literature's main lever.
2. **xPTS response** — our Phase-2 shot-quality model replaces raw points
   (the "x" in LUMA's xpts is exactly this).
3. Priors/aging — last.
Shipping rule: no surface. The evidence file keeps the verdict and the table.

## §2 — Multi-season RAPM 2022-23 → 2024-25 (pre-registered 2026-10-31, before any fit)

**Why.** §1 v3's verdict: single-season raw-points RAPM peaks at 0.464 vs the
0.70 benchmark bar; the literature's main lever is multi-season data. The
backbone (pbpstats intervals + possessions) is per-season pullable and both
its gates passed for 2024-25 (minutes 0.28 min; points MAE 0.16).

**Data.** Three regular seasons on the identical lineage: 2022-23, 2023-24
(pulls in flight), 2024-25 (in hand). Response = possession points
(2×FG2M + 3×FG3M + made FTs by the (N PTS) marker), validated per season
against ESPN box sums (the §1 gate: MAE < 1.0/team-game). Rosters = official
interval spans containing the possession midpoint; exact-5v5 windows only.
Handling gates per season: minutes vs box (median |Δ| ≤ 0.5) and points vs
box (MAE < 1.0) — a season failing either is excluded and the failure
diagnosed before any fit.

**Model (fixed).** One row per possession across all three seasons; player
coefficients GLOBAL (one rating per player, shared across seasons); season
scoring environments absorbed by centering y within each season; home-court
fixed effect per row (unpenalized); ridge with the amended grid
{100 … 100000}, λ chosen by 5-fold game-grouped CV on team-game aggregate
margins (the §1-amended criterion, applied unchanged).

**Judged (read once).**
1. *Benchmark*: Pearson r vs LUMA `xpts_rapm` season-2025 `xpts_net` on
   shared players with ≥250 possessions — **bar 0.70** (unchanged; a
   multi-season rating must still track the most recent season for active
   players).
2. *Stability*: split-half (even/odd game ids, pooled) r on players with
   ≥500 possessions in both halves — **bar 0.60**.
Failure diagnosis: data (older-season backbone) vs handling (λ, pooling) vs
modeling (design), in that order.

**Shipping rule.** Both gates pass → the first shipped model surface (a
RAPM column on the players board, labelled with the gate date and LUMA
credit). Any gate fails → verdict + diagnosis recorded, no surface; the
next lever (xPTS response via the Phase-2 shot-quality model) is §3.

**Expected.** Benchmark 0.55–0.72: multi-season closes most of the
single-season noise gap; the residual distance is the xPTS-vs-points and
priors difference. Risk: 2022-23 roster churn (players with 1 season of
data) and λ landing at the grid edge again.

### §2 read (2026-10-31): FAIL on both gates — benchmark 0.464 → 0.618, the multi-season lever delivered

Backbone: three seasons on the traded-player-corrected lineage (one
interval pull per player-team stint; capture coverage jumped to 71–85% of
possessions per season from 39–54%). Pooled 554,869 possessions, 740
players, global coefficients, per-season centering.

| λ | split-half r | LUMA benchmark r |
|---|---|---|
| 100 | 0.284 | 0.528 |
| 1,000 | 0.323 | 0.554 |
| 10,000 (CV-selected) | 0.481 | 0.611 |
| 30,000 | 0.592 | **0.618 (peak)** |
| 100,000 | **0.671** ✓ | 0.596 |

**Verdict: FAIL — at the λ-selected row, stability 0.481 (bar 0.60) and
benchmark 0.611 (bar 0.70).** The single-season→multi-season move closed
roughly a third of the benchmark gap (0.464 → 0.618 peak) and the curves
keep climbing where §1's flattened. The remaining distance to 0.70 is the
xPTS-vs-raw-points difference and LUMA's priors — exactly §3's lever (the
Phase-2 shot-quality model replacing raw points as the response). No
surface ships. The spine assets (intervals, possessions, id joins, three
seasons deep) are permanent.

## §3 — xPTS response (pre-registered 2026-11-01, before any fit)

**Why.** §2's verdict: multi-season raw-points RAPM peaks at 0.618 vs the
0.70 bar; the remaining distance is the response — LUMA's xpts_rapm uses
expected points from shot quality, ours used raw points. §3 replaces the
response: same design, same backbone, xPTS instead of points.

**The shot-value surface (fixed).** League FG% by (distance-from-rim bucket
{0-4, 4-9, 9-14, 14-19, 19-22.5, 22.5-24.5, 24.5+} × shot value {2, 3}),
estimated per season from our validated ESPN shot table (the same table the
game reports render; x/y normalized to the attacking half, rim at
(25, 5.25) ft). xPTS per shot = FG% × shot value. FT xPTS = league FT% for
the season × FTAs in the possession. The surface is an in-sample descriptive
transformation (the league's own shot values), not a forecast model — the
registered quality claim stays with the RAPM gates.

**The response.** Possession xPTS = Σ the segment's FGA xPTS + FT xPTS.
Segments come from the same ESPN control walk (§1); shots join their segment
by play index (same feed — validated 100% match); the on10 come from the
pbpstats intervals as in §2 (validated minutes 0.28 min). Coverage gate: ≥95%
of FGA matched into exact-5v5 segments.

**Judged (read once).** The §2 gates unchanged:
1. *Benchmark*: r vs LUMA xpts_net season-2025, shared players ≥250
   possessions — **bar 0.70**.
2. *Stability*: pooled split-half r, players ≥500 possessions both halves —
   **bar 0.60**.
The xPTS response predicts: benchmark ≥ §2's 0.618 peak (the response is the
only change). Failure diagnosis: data vs handling vs modeling, in order.

**Shipping rule.** Both gates pass → the first shipped model surface (RAPM
column, gate-dated, LUMA credited). Otherwise verdict + diagnosis recorded;
the next lever is priors (multi-year shrinkage targets).
