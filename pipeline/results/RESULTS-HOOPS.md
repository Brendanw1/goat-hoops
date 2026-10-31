
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
