# MODELS-ROADMAP — isolating player impact and team impact

The program plan for models, grounded in what is ON DISK, the RAPM campaign's
own measured verdicts (pipeline/results/RESULTS-HOOPS.md §1–§7), the owner's
spec (docs/hoops-spec.md), and the knowledge base. KB citations follow the
clean-room rule: search before inventing methodology, cite what was used.

KB sources used here: arxiv "Modeling Player and Team Performance in
Basketball" (production curves §3.2, defense-as-suppression §3.4); arxiv
"Possession-Level Player Impact in the Pre-Play-by-Play NBA Era" (stint
responses, weights, RAPM extensions); closingfive.com (prior-informed RAPM
"IPM"; lineup chemistry = unit residual vs player prediction);
bball-index.com (LEBRON: box prior inside the RAPM ridge); jecutter.github.io
(SPM = linear estimators of RAPM); basketball-reference (BPM family, linear
box metrics).

## Where we stand (the measured ladder)

| Rung | Status | Evidence |
|---|---|---|
| 0. Data spine, two-source validated | done | §0 LUMA gate; §0b BDL-vs-ESPN (688/688 games, 11,326 boxes exact) |
| 1. Statistics foundation on the site | done | Phase 1b: 4 seasons, advanced roll-ups, /stats |
| 2. RAPM family at the raw tier | measured ceiling | §1 0.464 → §2 0.618 → §3 0.621 → §4 0.658 → §5 0.676 → §6 tie → §7 tracking-SPM prior FAIL. Bar: LUMA r ≥ 0.70. Diagnosis: the gap is INFORMATION (defender context), not estimation; τ handling was §7's suspect |
| 3. Exploration foundation | done | explore.py: similarity/archetypes, surplus, clutch deltas, rebound conversion (context, not skill), survivorship-flagged aging |
| 4. Tracking tier | LANDED (unused by models) | advagg: matchups, contested shots, box outs, charges, deflections, passes/touches, rebound chances — 6 complete seasons 2019-20 → 2024-25 |
| 5. Lineup inputs | ON DISK, unbuilt | BDL lineups parquets (2024-25, 2025-26), ESPN PBP stints (validated §1–§4 spine), pbpstats possessions |

## Track A — Player impact isolation: finish the RAPM campaign (§8)

The campaign said the gate re-opens when the tracking tier lands. It landed.
Two designs, both grounded in the KB, both pre-registered before any read:

- **A1. Prior-informed RAPM (the IPM/LEBRON pattern).** The same ridge the
  campaign built, but the shrinkage target is a *box+tracking profile
  rating* rather than Game Score alone: production composite + matchup FG%
  allowed, contested-shot rate, deflections, box outs, rebound chances.
  §5's prior added +0.018; §7's sparse tracking prior failed on τ handling —
  §8 uses the full profile and pre-registers the τ grid explicitly.
- **A2. Two-stage SPM calibrated on RAPM (the BPM family).** Fit a linear
  model whose TARGET is the §2/§4 multi-season RAPM and whose FEATURES are
  box + tracking rates; gates = out-of-sample stability and next-season RAPM
  forecast, benchmarked against the §5 Game Score prior baseline. A pass
  produces the stable per-player impact rating that can eventually carry a
  graded label on player pages.

Honest scope note (pre-register it this way): the true defender-context gap —
per-possession defender proximity inside the xPTS response — is still
tracking-gated (no public per-possession defender mapping). The tracking tier
moves the lever to the FEATURE side (who you are as a defender/creator), not
the response side (what happened at this possession). Benchmark bar unchanged:
LUMA xpts_rapm r ≥ 0.70, LUMA credited.

## Track B — On/off, lineups, WOWY (spec §5; the spec's named prerequisite)

- **B1. Lineup explorer** — unit possessions, net rating, stints from the
  validated spine; gate: LUMA `lineups`/`onoff` views.
- **B2. Per-player on/off + WOWY** — net, teammate 3PA rate/quality, rebound
  rate with/without.
- **B3. Lineup chemistry** (the closingfive pattern, worth copying exactly):
  each five-man unit's possession-weighted residual — actual net rating minus
  what the RAPM model predicts from its ten players. Opponent-adjusted by
  construction; the team-impact decomposition that separates "gels" from
  "talent." Depends on A (or §2's ratings) existing first.

## Track C — Role decomposition and gravity (spec §4)

- **C1. Gravity** — on/off differential on teammates' 3PA rate and
  catch-and-shoot quality; the playershots × stint merge is in hand.
- **C2. Load decomposition** — usage/assist/touches composition from advagg
  (already rendered per player); archetypes from explore.py are the vocabulary.
- **C3. Defense as suppression** (arxiv §3.4's "what does not happen" — the
  Dwight Effect): opponent shot-attempt rate by court zone while on vs off
  floor, from ESPN x/y shots + validated stints. The tracking-free version of
  suppression; LUMA's ARC channels are the reference.
- **C4. Rebounding zones** (spec §3) — zone rates from miss x/y; chances from
  advagg supply the denominator context (conversion itself already measured:
  context, not skill — docs/explorations-2026-11.md §4).

## Track D — Skill-claim gates (the exploration layer's debts)

- **D1. Clutch persistence** — do clutch deltas persist year-over-year with
  proper gp floors? The test that would earn (or strip) judgment colors on
  the clutch panel.
- **D2. Rebound conversion re-test** — per-game split-half (advagg rebuilt
  per game) or the team-stable subset; changes the chip's label only if it
  passes.

## Track E — Projections (spec §6, last)

- **E1. Marcel-style per-36 baselines** — recent-season weighted averages,
  regression to league mean by minutes class.
- **E2. Aging done honestly** — within-player (fixed-effects) age curves from
  the 2005-2025 careers history, NOT the survivorship-dominated cohort curves
  of docs/explorations-2026-11.md §5 (arxiv §3.2 production curves is the
  frame). Forecast gate vs naive (next = this) before any curve renders.
- **E3. Blend with impact ratings** — the VectorSSM pattern from baseball:
  state-space/blended projections once A and E1/E2 exist.

## Sequencing

1. **Next**: §8 preregistration (model lane's claim — A1/A2) in parallel with
   B1 lineups surface (stats lane). No file collisions; both are named in
   the spec's build order.
2. Then B2/B3 (needs §2/§4 ratings for chemistry), C1/C3, D1/D2 gates.
3. E last, per the spec. Each model: pre-register in RESULTS-HOOPS before
   the first read; descriptive-first; LUMA as the external reference, credited.
