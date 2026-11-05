# Explorations — 2026-11 (descriptive reads, no gates claimed)

Everything here comes from `pipeline/explore.py` over the already-validated
site docs (advagg / seasavgs / players board / contracts / careers). House
rule honored in both directions: nothing below is a gated model verdict, and
nothing below claims predictive power. The one number that *looks* like a
skill claim — rebound conversion — carries its own stability read, and it
**fails** the read (that result is the finding).

## 1. Player vectors, similarity, archetypes (`similar.json.gz`)

Vector: 30 z-scored v2-advanced fields (efficiency, load, playmaking, glass,
impact, activity; DRtg inverted), season 2025-26 pool (gp ≥ 15, 250+ min,
n=337). Missing fields impute to the pool mean; DRtg inverted so every axis
is higher=more.

- **k-means (k=7, seed 7)** produces readable roles: usage-heavy creators
  (Jokić, Giannis, Wembanyama, Sengun, AD), playmakers (Luka, SGA, Curry,
  Edwards), perimeter shooters, paint finishers (Bona, Drummond), off-ball
  finishers (Caruso, A. Wiggins), self-created scorers, 3-and-D role players.
- **Neighbors pass the eye test**: Luka → Brunson (.828), Harden (.809),
  J. Murray, D. Mitchell, Reaves, Maxey, Fox, LeBron — a pure
  primary-creator cluster; no noise entries in the top 8.
- Standing caveat: 2025-26 advanced coverage is ~half a season; vectors use
  rate fields only, but rotation-context fields (matchups aside) can shift
  when the walk's remainder lands. Re-run `explore.py` after the advanced
  walk finishes (Nov 9) — the bake is deterministic from the doc, so this is
  one command.

## 2. Contract surplus (`surplus.json.gz`)

production percentile (mean z of ts/usg/ast/drb/net/pie/deflections/
screen_ast within the season pool) − cap-hit percentile (2026-27 salaries).
One-season offset by design (2025-26 production vs 2026-27 pay); the site
line states this in the contract card.

- Extremes pass the smell test: best surplus = rookie-scale and minimum
  producers (Ighodaro +0.82, Thybulle, Queta, Bagley III, Cam Spencer);
  worst = LaVine ($49.0M, −0.75), Keegan Murray, Gary Trent Jr., Poole
  ($34.0M), Scoot Henderson.
- Known limits, stated on the surface: the composite is one transparent
  choice (eight pillars), defense enters only through activity proxies
  (drb/deflections), and a healthy-scratched star's production percentile is
  computed from games played. Not a valuation model — a descriptive lens.

## 3. Clutch deltas (`clutch.json.gz`)

clutch-category minus overall season rates (BDL season averages), 2023-24 →
2025-26, surfaced as chips with the clutch-games count and a small-sample
flag under 25 games.

- Deltas are **small samples by construction**: 35/398 players in 2025-26
  show |net Δ| > 50 — real runs of tiny-sample basketball, not signal.
- Luka reads +28.7 net (23 clutch games, flagged). Conley's +0.793 TS Δ
  (2025-26) is the kind of outlier the flag exists for.
- No persistence analysis yet — until one exists, the panel is a descriptive
  delta, "not a clutch gene" (the site says so in the footnote).

## 4. Rebound conversion (`rebound.json.gz`) — the negative result

reb36 ÷ rebound chances per 36 (both from the validated layers). Plausibly a
skill (chances are the tracking input the spec wanted) — so it got the
inline stability read before any claim:

- **Year-over-year stability, 2023-24 → 2024-25, n=289 shared players:
  r = 0.221.** That is far below what a stable skill shows; conversion as
  measured is mostly context (team, role, position of the chances) plus
  noise.
- Consequence: the site chip ships as "conversion of chances" vs league
  bands, never as a skill grade. Follow-ups that could change the verdict:
  restrict to players with stable teams/roles across the pair, or split-half
  within a season once game-level chances are rolled per game (they are —
  advagg can be rebuilt per-game). Until then: context, not skill.

## 5. Aging curves (`aging.json.gz`)

Per-age career-line averages 2005-2025 (gp ≥ 20 rows), mean + p25/p75 per
metric. **The curves rise monotonically with age (ppg 9.6 at 20 → 16.5 at
36) — pure survivorship:** 38-year-olds are the players who were good enough
to still be playing. These are cohort curves, useful as league context per
age, and useless as individual trajectories until properly conditioned.
Nothing on the site renders them yet; any future "aging adjustment" (spec §6)
must model the selection explicitly (Mirajan-style cohort + trajectory
decomposition) before it gates.

## What this foundation enables next

- **RAPM lane (model lane's call):** the tracking tier §5 wanted is now a
  doc away — advagg fields as priors/features. §5's gates re-open when the
  model lane claims it.
- **Marcel-style projections** from careers + aging (with the selection
  caveat handled properly), feeding spec §6's projections page.
- **Player comps page** — similarity is player-page-level now; a dedicated
  compare view (two players side-by-side, shared-field deltas) is the natural
  next surface.
- **Surplus board** — team-level surplus rollups from the same doc.

Re-run bookkeeping: `python pipeline/explore.py` (fast, deterministic);
`hoops_export.py --check` excludes the exploration keys
(`EXPLORE_KEYS`) so the bake's no-op gate stays meaningful.
