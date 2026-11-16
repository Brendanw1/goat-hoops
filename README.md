# GOAT-Pro Hoops

**NBA analytics where every model has to pass a test written before its result is read.**
Live at **[hoops.goatpro.dev](https://hoops.goatpro.dev)**. This is the basketball sibling of
[GOAT-Pro](https://goatpro.dev) (baseball).

The site covers players, teams, games, lineups, leaderboards and a rookie race. It is built
from ESPN's public game feed and refreshed every morning. Each model that reaches the site
was pre-registered in [`pipeline/results/RESULTS-HOOPS.md`](pipeline/results/RESULTS-HOOPS.md)
with a baseline to beat and a bar to clear. Models that fail stay off the site, and the
failures are recorded alongside the passes.

## What's on the site

| Page | What it shows |
|---|---|
| Players | Season and game logs, last 10/30 and monthly splits, percentile panels, shot charts and zones, shot creation, expected eFG and shot-making, Box Plus/Minus split into offense and defense, raw on/off with most-used lineups |
| Leaders | 50+ stats by position pool, each with its status (box score, gated, or descriptive), a percentile strip, and raw or regressed ranking |
| Rookies | A weekly rookie race, production vs playing time, and class standings |
| Teams | Four factors vs the league, strength of schedule, clutch record, team boards, a minute-by-minute rotation fingerprint |
| Games | Box scores, shot charts, play-by-play, a run-of-play chart and a who-played-when stint chart for every game |
| Lineups | Five-man units and on/off from our own substitution tracking |
| Methods | Every metric's definition, plus a [source table](https://hoops.goatpro.dev/methods#sources) tracing each stat to its feed call, code and test |

## The models and their tests

| Model | Result | Test |
|---|---|---|
| Player rates (TS%, eFG%, USG%, AST%, rebound shares, AST/TO) rebuilt from the box score | r 0.991–0.997 against NBA.com's published values; game-level TS/eFG match 99.96–99.99% | §0h, §0h-b |
| Shot zones and assisted vs self-created makes from play-by-play | zones r 0.993–0.9997 against NBA.com's zone splits; assisted share 0.9992 | §0i |
| Box Plus/Minus 2.0 + VORP (Myers' published method) | r 0.673 against an external impact model (Game Score/36 baseline: 0.470); year-to-year 0.79 | §16 |
| Offensive and defensive BPM | offense r 0.711 (points/36 baseline 0.521), defense r 0.615 (stocks/36 baseline 0.426) | §16-b |
| Regressed values (empirical Bayes toward the league mean) | lower held-out error on all 32 original stats (median −9.4%); attempts replace minutes as exposure only where they predicted better (4 of 14) | §17, §17-b |
| Free-throw fouls drawn and and-ones from play-by-play | r 0.958 against NBA.com's fouls-drawn; implied free-throw attempts exact | §18 |
| Per-shot expected eFG (gradient boosting on distance, angle, zone and shot family; no shooter identity) | held-out log loss 2.9% better than a zone-average table | §20 |
| Lineups and on/off from a substitution walk of the play-by-play | 99.92% of 1,199 games reconcile to the final score exactly | §0f |
| Substitution walk rebuilt (clock order, evidence starters, look-ahead eviction, backdated swaps) | held out: player minutes within 1.0 of the box in 98.4% of player-games (was 91.1%); placement vs pbpstats r 0.999 on games both hold. As registered, placement read r 0.922, because the reference is missing late-season games. The correction was made after the read and accepted by the owner | §21, §22, §22-b |
| Win probability | **Failed twice.** Beats score-and-time by 8.5% on Brier but misses the calibration bar (ECE 0.0168 vs 0.015). Not on the site | §19, §19-b |
| Adjusted plus-minus (RAPM) | **Failed** all eight pre-registered reads (best benchmark 0.676 against a 0.70 bar). Not on the site | §1–§8 |

The external impact reference for the BPM tests is LUMA Basketball Research's xPTS-RAPM. It
is used only to check our numbers and is never shown as site data.

## A data bug the tests caught

The first win-probability model missed its calibration bar. The diagnosis started with the
data. In a correctly ordered game the score never goes down, but in this feed it went down
mid-game in 2,634 of 2,921 games. The cause: ESPN appends a scorer's late correction to the
end of the play list with a new sequence number, so sequence order isn't time order. A second
issue was that clocks under one minute (`11.5` instead of `0:11`) parsed as blank, about
11.5% of rows.

Re-ordering every reader by period, game clock and running score fixed the win-probability
inputs. It also fixed the clutch stats (which were missing the last minute), putback timing,
and the play-by-play and run charts on every game page. The model still missed its bar on
calibration, and [the read](pipeline/results/RESULTS-HOOPS.md) explains why one more season
of training data wouldn't fix it: home-court advantage drifted between seasons, and the
pre-game strength prior was overconfident.

## How it's built

```
ESPN public API ──► ingestion mart ──► pipeline/ (Python) ──► baked JSON ──► Cloudflare R2 ──► Next.js on Vercel
(scoreboard,       (parquet,          rates, creation,      (no-op drift     (prefix hoops/)    (server-rendered,
 schedules,         daily refresh)     bpm, shrink, xefg,     check before                       5-minute ISR,
 game summaries)                       lineups, rookies)      every publish)                     pure-SVG charts)
```

- **Daily refresh.** A morning job ingests the night's games, re-runs the lineup
  reconciliation gate, re-bakes, and publishes. Any failed gate stops the publish.
- **The site never queries a database.** It reads pre-built JSON from object storage, so
  a page can't show a number the bake didn't check.
- **Traceable sources.** [`pipeline/sources.py`](pipeline/sources.py) records each stat
  family's feed call, method, code path, test and published reference. It is baked to the
  [Methods page](https://hoops.goatpro.dev/methods#sources) and to
  [`docs/SOURCES.md`](docs/SOURCES.md).
- **Built with coding agents under written rules.** [`AGENTS.md`](AGENTS.md) sets the
  rules: clean-room sourcing, pre-registration, commit only your own changes in a shared
  tree, docs travel with code. [`COLLABORATION.md`](COLLABORATION.md) is the work log.

## Data

- **ESPN's public API** for every live surface and the 2024-25 season: scoreboards,
  team schedules, and game summaries (box scores, play-by-play, shot coordinates).
- **NBA.com stats data** for the 2025-26 season, part of 2023-24, the 2006–2026
  season-average history, and draft slots. It was obtained through a licensed data API
  during a 2026 research window.
- **Reference-only:** NBA.com and Basketball-Reference glossaries for definitions;
  Myers (BPM 2.0), Hollinger (Game Score), Oliver (four factors) and Taylor (Offensive Load)
  for published formulas. Nothing is scraped.

## Repository layout

```
web/                          Next.js app
pipeline/                     the bake (hoops_export.py) and every model module
pipeline/results/RESULTS-HOOPS.md   pre-registrations, gates and verdicts
docs/                         metric canon (METRICS.md), sources, specs and plans
data/derived/                 committed gate results (JSON); bulk intermediates are ignored
data/export/web/              baked JSON (gitignored; rebuilt by the bake)
```

## Running it

```bash
python pipeline/hoops_export.py           # bake -> data/export/web/
python pipeline/hoops_export.py --check   # verify a re-bake changes nothing
python pipeline/r2_sync.py --dry-run      # then without --dry-run to publish (prefix hoops/)
cd web && npm install && USE_LOCAL_DATA=true npx next dev
```

The bake reads a separate ingestion mart that is not in this repo. Environment variables
(R2 credentials, `USE_LOCAL_DATA`, `NEXT_PUBLIC_BASEBALL_URL`) live in a gitignored `.env`.
Model gates run offline, for example `python pipeline/bpm.py --gate-b` or
`python pipeline/xefg.py --gate`.

## License

Copyright © 2026 Brendan Waterval. All rights reserved. The code is public for reading and
review. It is not licensed for reuse or redistribution without permission.
