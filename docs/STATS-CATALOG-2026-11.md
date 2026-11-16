# Stats catalog — what to add next (2026-11-15)

The owner's ask: more statistics, leaderboards and percentiles, sorted by what
we can honestly ship. `docs/METRICS.md` is the dictionary of what already
renders; this is the gap list on top of it. Every entry lands in METRICS.md
when it ships.

**Sources (KB, cited by path):** BBRef glossary + BPM 2.0
(`sources/basketball/basketball-reference-com-6af5e19612.md`, `-457a28b29d.md`),
NBAstuffer Analytics 101 (`nbastuffer-com-7295bf01b6.md`), Closing 5
methodology (`closingfive-com-bec67f8595.md`), bball-index LEBRON intro,
Synergy SSQ (`sportradar-com-410bbf9ec3b9.md`), squared2020 possession models,
the arXiv review "Modeling Player and Team Performance" (`arxiv-org-a1bbd62fda.md`),
Staude stabilization (`inbox/randomness-stabilization-...`), and the owner's
`notes/basketball-research-coverage.md`.

**Data check (2026-11-15, `hoops_mart/data/mart/pbp.parquet`):** ESPN PBP
carries shot types (Pullup, Step Back, Driving, Cutting, Putback, Alley Oop,
Floating, Turnaround, Fade Away…), turnover types (Bad Pass vs Lost Ball vs
Offensive Foul vs Shot Clock), the assister on made FGs (`p2`; 63.6% of made
FGs assisted, matching league norms), shot x/y, game clock. It does **not**
name the fouled player (only the fouler) or the charge-taker; shot clock and
defender distance are absent.

## 0. The finding that orders everything

The live season's USG%, AST%, ORB/DRB%, ORtg/DRtg and PIE come from BDL's v2
advanced feed, **frozen at the trial's end (Nov 9)** — commit 0bfdc34 flags
them as a dated snapshot. Every one of those is computable from the ESPN box
we ingest daily. So Batch 1 rebuilds them ourselves: live again, ours, and
BDL-independent. Tracking and play types stay frozen (no free source).

## A. Compute now from the ESPN feed (descriptive, live, every season)

Labelled "descriptive, not a forecast". Formulas are the BBRef/Oliver
published ones unless noted.

**A1. Rate rebuild (box-only)** — team possessions (Oliver estimate, both
teams averaged), pace, team ORtg/DRtg/Net; player USG%, AST%, TOV%, ORB%,
DRB%, TRB%, STL%, BLK%; FT rate (FTA/FGA), 3PA rate, AST/TO. Player per-100
on-court rates from the §0f-validated stints.

**A2. Shot creation (PBP)** — assisted % of makes by zone (rim / mid /
corner 3 / above-break 3); unassisted makes per 100; shot-type diet and eFG
per type (pull-up, step-back, driving, cutting, putback, alley-oop); rim rate
and rim FG% (x/y), corner-3 share, mid-range share. The pull-up/catch split is
the public proxy for tracking's touch-time split.

**A3. Playmaking (PBP)** — assists by the receiver's shot zone and points
created by assists (2s vs 3s weighted); assisted-teammate eFG; bad-pass vs
lost-ball turnover split (decision vs handle). Box Creation / Offensive Load
(Ben Taylor's published formulas, as Closing 5 computes them) — credited, labelled
an estimate of creation volume, not pass quality.

**A4. Fouls and free throws** — fouls committed per 36 by type; fouls
*drawn* inferred from the next free-throw shooter after a shooting foul
(verify against box FTA before shipping); and-ones (made FG + FT 1 of 1).
Charges drawn: **not recoverable** (B).

**A5. Rebounding** — putback rate (OREB followed by the same player's shot
within ~3 s of game clock); the zone-rate work is already Track C4.

**A6. Team four factors** — eFG, TOV%, ORB%, FT rate, offense and defense;
strength of schedule (opponent net, games-weighted); clutch net.

**A7. Splits** — rest/B2B, home/away, vs .500+, last 10/30, by month: already
named "next" in METRICS.md §3; built from the game-log grain only.

**A8. Achievements and game-level** — Game Score (Hollinger linear formula),
30/40/50-point games, double/triple-doubles, career highs. Cheap; good
leaderboard content.

## B. Needs data we don't have

| Want | Why not | Path back |
|---|---|---|
| Live tracking: drives, touches, passes, potential AST, deflections, contested shots, box outs, matchups, speed/distance, rebound chances | BDL v2 advanced, frozen Nov 9 (history 2019-20 → 2024-25 kept and still renders) | BDL paid tier (owner decision) |
| Play types (PnR handler, iso, post, spot-up, transition) | Synergy-derived via BDL, frozen | same |
| Shot clock, defender distance, catch-and-shoot by touch time | tracking-only | A2's pull-up proxy meanwhile |
| Charges drawn, screen assists | not named in ESPN PBP | tracking |
| Assisted-teammate eFG (how teammates shoot off a player's passes) | ESPN PBP names the passer only on makes; a pass leading to a miss leaves no record, so any eFG would count makes only | tracking "potential assists" |
| Box Creation as a standalone stat | §0j FAIL: against LUMA's pass-ended creation it loses to plain assists (0.86 vs 0.98); its extra scoring signal needs a reference for non-assist creation | tracking "opportunities created" |
| Coverage (blitz/ice/switch), rotations, VOSS | no public source (coverage note's open gap) | research note only |
| EPM / LEBRON / DARKO / RAPTOR | brand metrics, can't be re-hosted (Closing 5) | build our own families (C) |

## C. Models — pre-register in `pipeline/RESULTS-HOOPS.md` before reading

- **C1. Box plus-minus** (BPM 2.0 published coefficients, Myers) + VORP. Gate:
  correlation with LUMA `xpts_rapm` and next-season RAPM vs the Game Score
  baseline. Cheapest rating with a real chance to pass.
- **C2. Per-shot quality** — the §9 xeFG upgraded with shot type and zone
  (the Synergy SSQ/SSM pattern: expected points per shot excluding shooter
  identity + a making residual). Gate: held-out log loss vs §9.
- **C3. Regressed percentiles** — per-stat shrinkage constant k from
  split-half reliability (Staude); show the regressed value beside raw. Gate:
  regressed beats raw at predicting the second half / next season.
- **C4. Possession-start contexts** (transition, after OREB, after make) —
  needs possession segmentation, which AGENTS rule 6 gives to the RAPM build.
- **C5. Win probability / WPA** — gate on calibration (Brier) vs a
  score-and-time baseline.
- Already planned, by reference: gravity (§15b prereg), suppression (C3 in
  MODELS-ROADMAP), clutch persistence (D1), rebound conversion re-test (D2).

## Leaderboards and percentiles — the rules

- **One `/leaders` route**: stat picker, season, pool and minimum as GET
  params (the existing dynamic GET-form pattern).
- **Qualifiers from stabilization, not convention**: for each stat, the sample
  where odd/even-game split-half r reaches 0.5. Defaults until measured: 500
  min for rates, 100 FGA for FG%, 50 3PA for 3P%, 50 FTA for FT%.
- **Pools**: league-qualified, plus position (G/W/B from board `pos`, rendered
  only when ≥40 qualify).
- **Color**: the existing pos/neg league bands; low-is-good stats (TOV%, DRtg,
  fouls) invert; under-floor rows get `flag`. Never both.
- **Every board shows its n** and its label (gated or descriptive).

## Visuals (existing SVG components, no new dependencies)

Percentile bar cards for the new stats (the card exists); a league-distribution
strip/beeswarm with the player highlighted for each leaderboard; assisted vs
unassisted stacked bars by zone; four-factor diverging bars on team pages;
last-10/30 rolling sparklines. The figure repos stay reference-only
(figures4papers is CC BY-NC; polish-sci-figures is an app, not a library).

## Recommended order

1. **Batch 1 — A1 + A6 + `/leaders`.** Replaces the frozen BDL columns;
   everything else builds on it. **Shipped 2026-11-15** under §0h/§0h-b
   (RESULTS-HOOPS): 8 gated + 4 descriptive stats live; TO ratio and PIE
   held back (see the reads). Team four factors already ship from §0d.
2. **Batch 2 — A2 + A3 + A8**, with the creation and distribution visuals.
   **Shipped 2026-11-15** under §0i (both gates PASS): 13 gated zone/creation/
   playmaking stats, 4 descriptive, 5 box milestones; player-page shot
   creation panel. Follow-ups the same day: TO ratio from FT trips (§0h-c,
   held out, PASS), Offensive Load (§0j PASS vs LUMA `load`); Box Creation
   (§0j FAIL) and assisted-teammate eFG (not recoverable) moved to B.
3. **Batch 3 — C1 (BPM-style) and C3 (regressed percentiles)**, pre-registered.
   **Shipped 2026-11-15**: BPM 2.0 + VORP (§16 PASS, r 0.673 vs LUMA
   xPTS-RAPM, stability 0.79) and regressed values on 32 rates (§17 PASS,
   32/32, median −9.4% held-out error).
4. **Batch 4 — A4/A5/A7 + team context.** **Shipped 2026-11-16**: FT fouls
   drawn and and-ones (§18 PASS: implied FTA exact for 203/203 players, r
   0.958 vs NBA.com PFD, level with FTA/2), putback rate (descriptive), last
   10/30 and monthly splits with sparklines, four-factor diverging bars,
   strength of schedule and clutch on team pages (descriptive).
