# Projections — scope and implementation plan (2026-11-05)

Owner focus: advanced analytics and basketball research on **current players**,
feeding the **projection / ML models** this program will build. Starting from
the base up. This doc fixes the scope of the projection tier, the foundation
artifacts it needs, and the implementation order. It sits beside
`MODELS-ROADMAP.md` (model tracks) and `RESULTS-HOOPS.md` (the read log where
every projection read will be preregistered).

## 0. What is in scope, and what is deliberately not

**In scope:** per-player **stat projections** — next-season per-minute /
per-possession rates, minutes (role), and games (availability) for current
players, with intervals and an as-of stamp. Later increments: in-season
rollforward, draft-class projections.

**Out of scope (fixed facts of the program):**
- **Impact projections** — the RAPM campaign closed at the response-side
  ceiling (§8: benchmark 0.658 vs the 0.70 bar; the gap is defender context
  the public feed lacks). The gate re-opens only with a new data tier; EPM's
  published shape (SPM on tracking features anchored on RAPM, KB synthesis
  2026-11-05) is the design to reach for *then*, not now.
- **Value/fantasy outputs** — projections of stats, never of worth.
- Anything gated on data the trial doesn't carry.

**Why stat projections are the right first tier:** their targets are directly
observable, so there is no external-benchmark ceiling like §4's 0.658 — the
honest gate is beating naive baselines on held-out future seasons. The
machinery (preregistration, sealed artifacts, fixed gates) already exists;
only the artifacts below are missing.

---

## 1. Foundation artifact #1 — the modeling table

`data/derived/modeling_table.parquet` + `modeling_table_SEALED.json`
(schema, coverage per season/decade, join rates, floors, seal date).
**One row per player-season**, all seasons 2005-06 → 2025-26, players ≥ the
preregistered minute floor (proposed: 250 season minutes; sensitivity at
100/400 reported).

Feature families — every one already on disk, none requiring new pulls:
- **Basic** (seasavgs base pulls 2005-2025 + board 2024-2026): gp/gs, min,
  pts/reb/ast/stl/blk/tov, shooting splits.
- **Advanced rates** (advagg 2019-2026 + seasavgs advanced pulls 2005-2025):
  ts%, efg%, usg%, ast%, orb%/drb%, ortg/drtg/net, pie.
- **Tracking counts per-36** (advagg 2019-2026): deflections, contested,
  boxouts, screen assists, charges, loose balls, touches, passes,
  speed/distance.
- **History categories** (seasavgs pulls 2005-2025): clutch, defense, usage,
  scoring, misc rates.
- **Context**: age, season (era index), role (starter flag / minute tier),
  team context from the mart (read-only), and the same features as **lags
  1/2/3** plus 2-3 season rolling means.
- **Targets** (next season): per-36 and per-possession rate versions of the
  core stats, minutes, games.

Grain decisions fixed at build time (recorded in the seal):
- Rate space is **per-36 and per-possession** (pace-fair across eras); raw
  per-game kept as context columns only.
- **Era handling**: features stored twice — raw and as season z-scores vs
  that season's league distribution (the advagg dist bands already carry
  this shape).
- **ID bridging**: BDL → ESPN via the validated register; retired players
  are first-class training rows (no site page needed to learn from them).

---

## 2. Foundation artifact #2 — the forecast-gate template

`pipeline/projection_baselines.py` (+ a reusable runner for model reads).
Rolling-origin evaluation, fixed once, used by every future read:

- **Folds (time only)**: train ≤ season S-1 → predict season S, for
  S ∈ {2021, 2022, 2023, 2024, 2025} (five origins). No random player folds —
  they leak era and role context.
- **Baselines (the gates every model must beat)**:
  1. *naive repeat* — last season's per-36 rates, minutes-weighted;
  2. *league-mean + age shrink* — regression to the positional mean weighted
     by age and minutes;
  3. *two-year weighted average* — 2:1 blend of the last two seasons.
- **Metrics per target per fold**: MAE, RMSE, correlation vs actual, interval
  calibration (when intervals exist). A preregistered composite ranks models.
- **Ship rule template**: a model renders on the site only if it beats the
  naive baseline on ≥ 4 of 5 folds by the preregistered composite margin.
- **Machine protocol**: training is small (tens of thousands of rows) — but
  any LightGBM run follows the shared-Mac protocol anyway (3 threads,
  `nice -n 10`, one job, ledger announcement).

---

## 3. The reads (preregistered, in order)

- **§10 — the foundation read**: build §1 + §2, run the three baselines, and
  *record how far each baseline is from truth per target per fold*. No
  pass/fail — this is the skill measurement that defines every later gate,
  and the aging/curve descriptive half (survivorship-corrected, per the KB's
  Bayesian-aging method) rides along. Preregistered before the table is
  queried for anything beyond coverage counts.
- **§11 — ridge with age + lags**: the first real model; must beat every §10
  baseline on the composite across the five folds.
- **§12+ — increments, each preregistered**: gradient boosting (LightGBM);
  tracking features on the 2019+ subset; a minutes/role model; an
  availability (games) model; intervals (quantile variants) once point
  forecasts pass.
- Every read's artifacts sealed under `pipeline/results/projection_*`.

---

## 4. Site surfaces (only after a gate passes)

- Player page: a **projection panel** — expected per-36/possession stats with
  intervals, as-of date, "forecast of stats, not value", the model's fold
  record linked from /research.
- /research: projection reads appear in the same reads index (same verdict
  chips).
- No league-wide projection leaderboard until a model passes and the owner
  asks for it.

---

## 5. Implementation order (each step one session-sized unit)

0. **Data-hygiene audit** (half session): join rates of the category pulls
   2005-2025 by decade; register-bridge coverage incl. retired players;
   feature coverage per season; floor sensitivity. Reported in §10's Why.
1. **Build + seal the modeling table** (`pipeline/modeling_table.py`).
2. **§10 preregistration**, then baselines (`pipeline/projection_baselines.py`)
   → seal `projection_baselines.json` → record the read.
3. **§11 preregistration** → ridge model read → verdict.
4. **Site panel** only on a pass; otherwise the diagnosis is recorded and the
   next increment preregistered.
5. Maintenance: each new season's pull extends the table; the advanced walk's
   2025-26 completion upgrades the newest feature rows.

---

## 6. Success criteria for the foundation

- The table sealed with documented coverage (the §10 Why section reads like a
  data spec, not an excuse).
- Baseline skill measured per target per fold — the gates exist as numbers,
  not intentions.
- §10 recorded in RESULTS-HOOPS; every later projection model is now an
  increment against a fixed, preregistered, honest base.

That is "base up": spine → table → gates → models → (only then) surfaces.
