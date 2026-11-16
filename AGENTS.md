# GOAT-Pro Hoops

The basketball program: a public NBA analytics site, sibling to `goat-pro`
(baseball). Same design system, same culture, its own repo and deploy.

Read before any work: `docs/hoops-spec.md` (the owner's requirements),
`docs/basketball-site-plan.md` (phases and sources), and
`~/Projects/vt_baseball/hoops_mart/README.md` (the data layer: ESPN feed,
LUMA validation gate, mart tables).

## Stats-catalog models (live; each gated in `pipeline/results/RESULTS-HOOPS.md`)

- Player rates rebuild — §0h / §0h-b / §0h-c (`pipeline/rates.py`)
- Shot creation, zones, playmaking — §0i (`pipeline/creation.py`)
- Offensive Load — §0j (`pipeline/rates.py`)
- Box Plus/Minus 2.0 + VORP — §16 (`pipeline/bpm.py`)
- Regressed values — §17 (`pipeline/shrink.py`)

## Clean-room rules (hard)

1. Everything shipped derives from public sources only: ESPN's public API
   (the feed), balldontlie once the owner's `BDL_KEY` exists (terms §6 grants
   republication), pbpstats' open endpoints. LUMA (CourtShare) is the
   validation reference — credited wherever its numbers touched a result,
   never republished as our data. Cot's/Spotrac/Sports Reference are
   reference-only, never scraped.
2. Keys live in `.env` (gitignored) or Vercel environment variables. Never in
   the repo, never in client code. `LUMA_KEY` and `BDL_KEY` live in the
   knowledge base `.env`.
3. No model is public without a test pre-registered in
   `pipeline/RESULTS-HOOPS.md` before its result is read. Every model is
   benchmarked against LUMA's published equivalents (xpts_rapm, ARC channels,
   lineups/on-off) as the external reference; a failed gate gets a data vs
   handling vs modeling diagnosis. Anything ungated ships labelled
   "descriptive, not a forecast".
4. Player identity is the ESPN athlete id (the feed's native key); LUMA joins
   run through (date, team, normalized name) — their home flag is defective
   and their game ids are their own.
5. The site reads baked JSON from R2 only (prefix `hoops/`). It never queries
   the mart, the knowledge base, or any local store at runtime.
6. Possessions are a derived table, not a parse artifact: any possession
   segmentation ships only after pre-registration (the RAPM build owns it).

## Working rules

- **Shared tree.** More than one agent may work here. Claim work and log what
  shipped in `COLLABORATION.md`; run `git status` before a bake and commit
  only your own hunks.
- **Bake, check, publish.** `pipeline/hoops_export.py --check` (no-op drift
  gate), then `pipeline/r2_sync.py --dry-run` and `pipeline/r2_sync.py`
  (prefix `hoops/` only — never touch the baseball app's `goatpro/` keys).
  A local `next build` gates every web push. Pushing `main` deploys.
- **Docs travel with the change.** A new stat, model or page updates this
  file's model list, `docs/` where there is a method, and the README in the
  same commit.
- **The gate is the bar.** Nothing renders from a source that hasn't passed
  the LUMA cross-check; the bake's `meta.json` carries the credit and the
  gate date.
