# GOAT-Pro Hoops

Public NBA analytics: the basketball sibling of [goat-pro](https://goatpro.dev)
(baseball). ESPN's public feed is the data spine, LUMA Basketball Research is
the validation reference, and every model is pre-registered before its first
read. Linked with the baseball site by a sport switcher; deployed separately.

```
hoops_mart (vt_baseball)  ->  pipeline/hoops_export.py  ->  data/export/web
 ESPN feed + LUMA gate         bake (--check)               |
                                                            v
                              pipeline/r2_sync.py  ->  R2 (prefix hoops/)  ->  web (Next.js)
```

## Layout

```
web/          Next.js app (same design system as goat-pro)
pipeline/     hoops_export.py (the bake), r2_sync.py, paths.py
pipeline/results/RESULTS-HOOPS.md   pre-registrations, gates, verdicts
docs/         hoops-spec.md (owner requirements), basketball-site-plan.md
data/export/web/   baked JSON (gitignored; rebuildable by the bake)
```

## Status

Phase 1 shipped (see `docs/basketball-site-plan.md`): descriptive surfaces —
game reports with x/y shot charts, teams, players — over the validated
box-score spine. Models (RAPM, shot quality, lineups) are Phase 2, each
pre-registered in `pipeline/RESULTS-HOOPS.md`.

Live at https://hoops.goatpro.dev (Vercel project `goat-hoops`, root `web/`;
pushing `main` deploys). Player rates (TS%, eFG%, USG%, AST%, REB%s, AST/TO,
plus descriptive FT/3PA rates and STL%/BLK%) are rebuilt from the ESPN box by
`pipeline/rates.py` under the §0h/§0h-b gates and rank on `/leaders` with
percentiles by position pool. Shot zones, self-created vs assisted makes,
assists by receiver zone, turnover types and milestones come from ESPN
play-by-play in `pipeline/creation.py` (§0i; gates run offline with
`python pipeline/creation.py --gate`) and feed the same boards plus the
player page's shot creation panel. TO ratio counts free-throw trips from the
play-by-play (§0h-c); Offensive Load (Ben Taylor's formula) is benchmarked
against LUMA's `load` channel (§0j, `--gate-j`). Box Plus/Minus 2.0 + VORP
(`pipeline/bpm.py`, §16, benchmarked against LUMA xPTS-RAPM) and regressed
values beside every rate (`pipeline/shrink.py`, §17) render on `/leaders`
and player pages. Free-throw fouls drawn and and-ones (§18, `creation.py
--gate-f`, vs NBA.com PFD) and putback rate rank on `/leaders`; player pages
add last 10/30 and monthly splits with sparklines; team pages add four-factor
bars, strength of schedule and clutch (`pipeline/clutch.py`, descriptive).
Expected eFG and shot-making from a per-shot make model (`pipeline/xefg.py`,
§20) rank on `/leaders` and show on player pages. BPM splits into OBPM and
DBPM (§16-b, `bpm.py --gate-b`); regression uses attempts as exposure where
it predicts better (§17-b, `shrink.py --gate-b`) and `/leaders` can rank by
the regressed value. Player pages carry raw on/off from the §0f stint walk;
`/rookies` has the weekly rookie race, production vs minutes and standings
(`pipeline/rookies.py`, descriptive). Win probability (`pipeline/wp.py`,
§19, §19-b) failed its calibration bar twice and does not render.

Every stat's feed call, method, code path, gate and reference is in
`pipeline/sources.py`, baked to `sources.json` (rendered at
`/methods#sources`) and written to `docs/SOURCES.md` on each bake.

The LUMA cross-check gate (2026-10-29): 688/688 game scores 2024-25 exact,
52/52 current season, 324 player-game boxes with every stat exact except
assists (scorer judgment). Credit: LUMA Basketball Research (ARC v3.1,
LOKI v3.3).

## Environment

`.env` (gitignored): R2 keys (`R2_*`, prefix `hoops/`), `USE_LOCAL_DATA` for
dev against the local bake, `NEXT_PUBLIC_BASEBALL_URL` for the switcher pill.
The mart needs nothing from this repo; this repo reads it read-only.
