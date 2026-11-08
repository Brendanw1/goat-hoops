# Modeling audit — the senior-ML review (2026-11-08)

The owner asked for the whole modeling process re-evaluated the way a senior
machine-learning engineer would: clean and validate the data FIRST, then
features, then the pipeline. This doc is that review: findings severity-ranked
(H = wrong numbers possible, M = headroom, L = hygiene), each with its fix and
where the fix lands. The §13 read (RESULTS-HOOPS) executes H1-H3 and M1-M3;
the rest are recorded debts with owners.

## H — correctness findings

### H1 · Rookie/second-year rows are silently zero-imputed (BIAS in the shipped model)
The §11 ridge standardizes features and imputes missing to 0. For a veteran
that's harmless; for a **rookie's lag1_pts36 it asserts "he scored zero per-36
last season"** — a false statement the model then regresses from. ~60 training
rows per season are second-year players whose lags are NaN-but-real. The
model's rookie-sophomore forecasts are biased toward the league floor.
**Fix (§13):** zero-impute AND add explicit `has_lag1/has_lag2/rookie`
indicators so the intercept can absorb the unknown-vs-zero distinction.
**Verified the bias exists** before shipping (§13's fold table reports the
second-year slice).

### H2 · Games targets ignore schedule constants (2011-12 = 66, 2019-20 ≈ 71, 2020-21 = 72)
`next_gp` and its lags treat 55 games in a 66-game season the same as 55 in
82. The availability analysis (§10: MAE 17-21, r ≈ .2) and every gp feature
carry that noise. **Fix (§13):** `gp_frac = gp / team_games(season)` features
(schedule constants already recorded for §0e) alongside raw gp; the raw gp
target stays (the site renders games), but the model sees the normalized view
too.

### H3 · The seal claims per-36 is "pace-fair across eras" — it is not
Pace moved 93.2 → 101.8 across the span (the /eras table shows it). A
pts/36 forecast trained across that drift carries the env shift; the model
compensates only through the linear `era` term. The scope's own §1 said
"per-36 AND per-possession (pace-fair)"; the artifact shipped per-36 only.
**Fix (§13):** honest immediately — the seal's wording is corrected and
per-possession rate columns are added as features; **target-space migration
(per-possession or env-normalized targets, with baselines re-run in that
space) is §14**, preregistered separately, because changing the target space
changes §10's baselines and the shipped panel units with it.

### H4 · No data-validation artifact exists — the seal counts rows, it doesn't validate them
Nothing checks ranges (min_pg ≤ 48+, gp ≤ 83, ts ≤ 1.2), cross-field
consistency (Σgp plausible per season), or distribution drift year over
year. **Fix (§13):** `pipeline/data_validation.py` — assertion suite +
anomaly scan + drift report, run BEFORE the table builds; the build aborts
on any H-severity failure. The validation report is sealed with the table.

### H5 · Traded-player semantics never verified
One row per player-season (verified: zero duplicate ids), but nobody checked
whether that row is BDL's COMBINED season or a single stint — the difference
changes lag semantics for the ~50 traded players per season. **Fix (§13):**
verify against a known mid-season trade (gp > 41 with two teams implies
combined; the box parquets can confirm) and record the verdict in the seal.

## M — headroom findings

### M1 · Age enters only linearly
Aging is curved (the KB's aging notes; the site's own aging doc shows
survivorship-dominated curves). **Fix (§13):** age + age². The full
age-curve-relative feature (player vs his age-band expectation) is §14+.

### M2 · No momentum/trend features
lag1, lag2, rm2 exist; the classic signal `lag1 − rm2` (rising/falling) is
absent. **Fix (§13):** add it.

### M3 · The evaluation composite weights all targets equally
pts36 and min_pg contribute the same to the composite. Acceptable for now;
**deferred:** per-target gates (a model that trades min_pg accuracy for
pts36 must show it explicitly).

### M4 · Intervals don't exist
Point forecasts only. **Fix (§13):** split-conformal intervals from the
rolling-origin residuals (90% nominal), with the empirical-coverage gate
[0.85, 0.95] — cheap, distribution-free, honest.

## L — hygiene

- **L1 · λ reuse across folds:** fold S's λ was validated on S−1, which is
  fold S−1's test season. Accepted for a 6-point grid; documented, not fixed.
- **L2 · The table ignores 40 of 47 feature families** (clutch, defense
  dashboards, playtype PPP, shotdashboard). Deliberate at 7k rows (dimension
  discipline) — revisit only with a reason to believe they carry rate signal
  (§12b says tracking didn't).
- **L3 · random_state is fixed but the table build isn't versioned** — the
  seal now carries v1/v2/v3 notes; any future schema change bumps it.
- **L4 · §12's GBM read ran before the validation suite existed** — its FAIL
  verdict stands (the feature story, not dirt), noted for the record.

## What §13 executed (2026-11-08)

`pipeline/data_validation.py` (H4, H5) → `modeling_table.py` v3 (H1, H2,
H3-features, M1, M2) → §13 read: ridge v3 vs the §11 ridge on the identical
fold ladder, plus conformal intervals (M4).

**Outcome:** composite FAIL (0.990-0.999 — consistent small gains, under the
bar) and interval FAIL (conformal under-covers: .72-.84 at nominal .90 —
era drift breaks residual exchangeability). **Both FAILs are the process
working:** the ladder refused a sub-threshold claim, and the interval gate
caught what would have been overconfident public intervals. H1's fix
measured: sophomore pts36 MAE −4% (n=19). H5 resolved: trader rows are
combined seasons (the earlier contradiction was DNP rows in the box
parquets — now a codified validation rule). §14 (preregistered next):
drift-aware intervals + the env-normalized target space (H3's full fix).
The shipped model remains the §11 ridge; v3 is the training table.
