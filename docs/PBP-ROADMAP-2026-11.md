# Play-by-play roadmap (2026-11)

What we will build from ESPN's play-by-play, in order, with the method, source, test and
acceptance criteria for each step. Every model here is pre-registered in
`pipeline/results/RESULTS-HOOPS.md` before its result is read (AGENTS.md rule 3). Every
possession definition ships only after its own pre-registration (rule 6). Anything without
a test ships labelled "descriptive, not a forecast".

Status keys: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` failed its test (recorded,
not shipped).

---

## 1. Sources

### Feeds (what we compute from)

| Feed | Call | Gives | Use here |
|---|---|---|---|
| ESPN game summary | `GET site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={id}` | every event: period, clock, wallclock, type (140 kinds), team, running score, up to 2 players; shots with x/y in feet, shooter, blocker | everything |
| ESPN scoreboard / team schedule | `.../scoreboard?dates=`, `.../teams/{id}/schedule?season=` | game list (the schedule is authoritative) | spine, backfill |
| pbpstats open endpoints | `api.pbpstats.com/get-possessions`, `/get-playing-time-distribution` | per-possession start type, timing and outcome; per-player on-floor intervals per game (2022-23 → 2024-25, in `hoops_mart/data/pbpstats`) | **independent reference** for Phases 0–2 |

Mart tables (`hoops_mart/data/mart`): `pbp` (1.41M events), `shots` (656k, every FGA with
x/y), `player_game`, `team_game`, `games` (2,930 games: 2024-25 and 2025-26 complete with
play-in and playoffs, 2026-27 live).

### Validation reference (never shown as our data)

LUMA Basketball Research: lineups, on/off and xPTS-RAPM, used where a phase benchmarks an
impact number. Credited wherever it touches a result.

### Published methods (knowledge-base copies in `LLM_knowledgeBase/library/sources/basketball/`)

| Topic | Reference | KB file |
|---|---|---|
| Possession definitions | Squared Statistics, *Analyzing NBA possession models* | `squared2020-com-de2cf0c646.md` |
| Possession start types, playing time | pbpstats | `pbpstats-com-0e76f74950.md` |
| Transition / start-type framing | Cleaning the Glass | `cleaningtheglass-com-1fc9c4c830.md` |
| Four factors, glossary formulas | Basketball-Reference glossary (Oliver, Hollinger) | `basketball-reference-com-6af5e19612.md` |
| Stat definitions | NBA.com stats glossary | `nba-com-307fac94d2.md` |
| Rebounding | Dan Frank, *How to measure rebounding*; Sloan, *Deconstructing the rebound* | `danfrank-ca-8e761bbc7a.md`, `sloansportsconference-com-0df649a300.md` |
| Passing | Squared Statistics, *Modeling the pass* | `squared2020-com-9f89ee0216.md` |
| Shot quality | Synergy Shot Quality | `sportradar-com-410bbf9ec3b9.md` |
| WOWY / on-off | *With or without you* | `americansocceranalysis-com-34fc07b4fe4b.md` |
| Adjusted plus-minus | Squared Statistics, RAPM I–III | `squared2020-com-220902e1f1.md` and siblings |
| Win probability, WPA | Closing 5 methodology | `closingfive-com-bec67f8595.md` |
| Officiating | NBA Last Two Minute reports; referee impact from ESPN data (arXiv 2605.17845) | `official-nba-com-*.md`, `arxiv-org-4bd3e53ce9.md` |
| Tracking (extensions) | Hawk-Eye coverage; matchup data | `espn-com-81951d7738.md`, `theguardian-com-034ca56793.md`, `medium-com-103c345a28.md`, `nbastuffer-com-45129a9b9a.md` |

**Candidate ingests** (not yet in the KB; add before the phase that needs them): a
timeout/run regression-to-the-mean study (Phase 5), Cervone et al. 2014 expected possession
value and Franks et al. 2015 defensive matchups (tracking extensions).

---

## 2. Known data defects and how every phase handles them

| Defect | Size | Handling (required in all new code) |
|---|---|---|
| `seq` is not time order (scorer corrections appended late) | score falls mid-feed in 2,634 / 2,921 games | sort with `creation.ordered()` (period, clock, running score) |
| `clock_sec` null under one minute (`SS.T` clocks) | 11.5% of rows | refill with `creation.clock_seconds()`; fix the mart parser at source |
| Free-throw x/y is a sentinel (`-214748340`) | all FTs | filter `is_ft` before any spatial work |
| After-the-fact shot labels ("bank", "reverse", "finger roll") | — | never a model input (§20 rule) |
| Substitution log incomplete (re-entries without rows) | — | evidence-based correction in the walk (players who act are on the floor) |
| Fouled player not reliably named | — | drawer = next free-throw shooter (§18) |
| Garbage time | — | pre-registered filter per phase (default: margin > 20 in the last 5:00 of Q4) |

**Open finding (2026-11-16):** `pipeline/possessions.py` (the §1 walk that feeds `/lineups`)
still sorts by `seq` (lines 221, 307). Its two failed §1 handling gates (possession counts
86.4% within ±2 of pbpstats vs a 95% bar; player minutes median |Δ| 7.2 vs a 0.5 bar) are
the signature of this defect. Phase 0 tests that.

---

## 3. Methods glossary

- **Clock order.** Events sorted by period, game clock descending, running score, then seq.
- **On-floor walk.** Q1 opens from box starters; substitutions swap players; any player who
  shoots, rebounds, assists, fouls or turns it over is evidence they are on the floor; later
  periods inherit the prior period's five. Output: per game, per player, on-floor intervals
  `[t0, t1)` in game seconds.
- **Possession.** One team's control segment, ending on a made FG (unless and-one), a
  defensive rebound, a turnover, or a period end. Fouls, timeouts, reviews and jump balls do
  not end it. (§1 rules, re-tested in Phase 0.)
- **Start type.** How a possession began: after an opponent made FG, made FT, defensive
  rebound (by miss zone), steal (live-ball turnover), dead-ball turnover, timeout, or period
  start; plus offensive-rebound continuations. Mapped to pbpstats' `StartType` labels.
- **Inferred shot clock.** Seconds since the possession started; reset to 14 after an
  offensive rebound or a kicked-ball/foul reset where the rules apply. Shot-clock
  turnovers must land at the end of it (validation, Phase 2).
- **Transition.** The possession's first shot, trip or turnover within 7 seconds of a steal
  or a defensive rebound.
- **Shrinkage.** Empirical Bayes toward the league mean with k from split-half reliability
  (§17 method).
- **Matched control.** For any "did X change Y" chart: compare against situations with the
  same game state (margin, period, clock, run length) where X did not happen.

---

## 4. Phases

Each phase lists what we build, the steps, and the acceptance criteria that decide whether
it ships. Bars are fixed when the pre-registration is committed and never move afterwards.

### Phase 0 — Fix the on-floor walk (foundation for everything below)

**Build:** the §1 walk re-run on clock-ordered events, with interval times on every stint.

- [x] 0.1 Pre-register **§21** in RESULTS-HOOPS before running: same bars as §1's handling
  gates, read on 2024-25 (site 2025), forward-checked on 2026-27.
- [x] 0.2 Patch `possessions.py` to load through `creation.ordered()` and
  `creation.clock_seconds()`; add `t0`, `t1` (game seconds) to every stint row. Log the change
  for the lineup lane in `COLLABORATION.md` (their file).
- [x] 0.3 Run 2024-25 and 2026-27; write `gate_possessions_*`, `gate_minutes_*` JSON.
- [x] 0.4 Run 2025-26 (missing from `/lineups` today).
- [x] 0.5 Diagnose any failure as data, handling or modeling before any change.

**Acceptance (all must hold):**
- Team-game possessions within ±2 of pbpstats in ≥ 95% of games; MAE < 1.5.
- Player stint minutes vs box MIN: median |Δ| ≤ 0.5 min.
- §0f still passes: score-exact ≥ 0.99, minutes structural ≥ 0.95.

**If it passes:** `/lineups` and on/off rebuild on the new walk (with a note to their owner),
and possessions become eligible for Phase 2's pre-registration.

**Result (2026-11-16): PASS on iteration 1.** Possessions 96.7% within ±2 (MAE 0.84),
minutes median |Δ| 0.35 min, §0f passes. Iteration 0 (clock order alone) reached 93.9%; the
diagnosis found jump balls, technicals, defensive goaltending, lane violations and reviews
splitting possessions, and making them non-control (H4) closed the gap. 2025-26 passes every
bar as an independent season and joins `/lineups`. Watch item: 2026-27 possessions 91.5% on
71 joined games (report only). Full read in RESULTS-HOOPS §21.

### Phase 1 — Rotation fingerprint and stint chart (Tier 1, #1)

**Build:**
- `pipeline/rotations.py` → `rotations.json.gz`: per team-season, the top 13 players by
  minutes, their share of games on the floor in each of the 48 regulation minutes, average
  stint length, typical stints per game, and the closing five (most frequent five on the floor
  in the last 5:00 of games within 5).
- Game docs gain per-player stints (`t0`, `t1`, plus-minus in stint) for the stint chart.
- `web/components/ui/rotation-fingerprint.tsx` (team page): players × minutes heatmap, closing
  block, stagger annotation.
- `web/components/ui/stint-chart.tsx` (game page): one row per player, stint bars colored by
  stint plus-minus, foul ticks, timeout rules.

**Steps:**
- [x] 1.1 Pre-register **§22**: our minute-by-minute on-floor share vs pbpstats'
  playing-time distribution, 2024-25, every player with ≥ 500 minutes.
- [x] 1.2 Build `rotations.py` on the Phase 0 stints (requires Phase 0 PASS).
- [x] 1.3 Read §22; diagnose any failure. **FAIL (2026-11-16).** Placement passes
  (r 0.958, Jaccard 0.985, shares sum to 5.00). Minutes fall short: 90.7% of player-games
  within 1.0 min (bar 95%), 79.2% of seasons within 1% (bar 95%). The cause is the ESPN
  substitution log. pbpstats' official-log intervals clear both bars on the same box.
  Two handling fixes shipped in `possessions.py` (stints tile every period; the walk is
  deterministic).
- [x] 1.3b **§22-b (2026-11-16):** the substitution walk rebuilt (evidence period starters, no
  technical/ejection evidence, look-ahead eviction, backdated swaps); held-out minutes 98.4% /
  97.9%; shipped on the owner's decision (placement passed on the corrected measure).
- [x] 1.4 Bake (team docs `rotation`, game docs `stints`), components, team and game pages,
  dev check at 1280 px and 375 px.
- [x] 1.5 Source registry row, METRICS entry, README page table.

**Acceptance:**
- Structural: each team's shares sum to 5.00 ± 0.01 in every minute bin.
- Season minutes from the fingerprint within 1% of box minutes for ≥ 95% of players.
- §22: per-player, per-minute share vs pbpstats, r ≥ 0.95 and mean absolute difference
  ≤ 0.03; per-game interval overlap (Jaccard) ≥ 0.95 median.
- Stint chart: each player's stint minutes within 0.5 min of box minutes in ≥ 95% of
  player-games.
- Payload ≤ 15 KB gzipped per team; no client JavaScript; legible at 375 px.

### Phase 2 — Possessions, start types and the inferred shot clock

**Build:** `possessions` with start type, inferred shot clock and transition flag →
`possession_anatomy` per team-season; visuals **Possession anatomy** (small multiples:
points per possession by inferred shot-clock second, one panel per start type, league band,
frequency bar) and **Crash or retreat** (offensive rebound rate vs opponent transition points
per 100 after our misses, break-even line).

**Steps:**
- [ ] 2.1 Pre-register **§23** (requires Phase 0 PASS).
- [ ] 2.2 Implement start types and inferred shot clock; map to pbpstats `StartType`.
- [ ] 2.3 Read §23 on 2024-25; forward-check 2026-27.
- [ ] 2.4 Bake, visuals, docs, source rows.

**Acceptance:**
- Start-type agreement with pbpstats on matched possessions ≥ 95%.
- Team points per possession by start type vs pbpstats: r ≥ 0.95.
- Inferred shot clock: ≥ 95% of shot-clock turnovers land at ≥ 23.0 s (or ≥ 13.0 s after an
  offensive-rebound reset).
- Transition share by team vs pbpstats' early-clock share: r ≥ 0.85.

### Phase 3 — Assist web and the opponent scouting sheet

**Build:**
- **Assist web** (player and team pages): arc diagram from passer to scorer, width = assisted
  makes, color = zone of the make. Descriptive.
- **Scouting sheet** `/teams/[abbr]/scout`: one printable page assembled from Phases 1–2 plus
  shot diet, late-clock options, top assist pairs, closing five, foul drawers, bonus
  tendencies, challenge habits.

**Steps and acceptance:**
- [ ] 3.1 Assisted makes per player match box AST in ≥ 99% of player-games (structural).
- [ ] 3.2 Assist web on player and team pages; top-N pairs only, small samples greyed.
- [ ] 3.3 Scouting sheet fits one US Letter page in print; every panel carries its source
  line and status.

### Phase 4 — Data depth: mart move, ESPN backfill, win probability §19-c

**Build:** five more seasons of ESPN play-by-play, then the win-probability retest.

- [ ] 4.1 Move `hoops_mart` to its own private repo (owner go-ahead pending); point
  `paths.py` and the 24 hardcoded paths at it; keep the daily refresh green.
- [ ] 4.2 Backfill 2019-20 → 2023-24 (≈ 6,150 games) with the existing ingestor; same
  resumable receipts and 1.5 s pause.
- [ ] 4.3 Per season: game-score exact vs the schedule ≥ 99.9%; §0f walk passes.
- [ ] 4.4 Pre-register **§19-c**: train on several seasons, strength prior shrunk by
  measured reliability, test on a season none of them saw. Bars unchanged from §19-b.

### Phase 5 — Tier 2 models (each its own pre-registration)

| Item | Build | Test / acceptance |
|---|---|---|
| 5.1 Rebound geography (§24) | offensive-rebound probability by miss x/y, shot type and possession context; half-court map with opponent fast-break arrows | held-out log loss beats a zone-only baseline; calibration max decile gap ≤ 0.02 |
| 5.2 Run autopsy (§25) | every 10-0 run: what fed it, what ended it; timeout effect vs matched no-timeout runs | pre-registered matched control; effect CI excludes 0 to claim anything, otherwise shown as "no measurable effect" |
| 5.3 Bonus clock | when each team enters the penalty per quarter and FT points earned in it | team fouls per quarter reconcile to box PF ≥ 99% |
| 5.4 Stint fatigue (§26) | efficiency and turnover rate by minutes into stint and real rest (wallclock) | split-half reliability reported; selection-aware design (within-player, matched game state) |
| 5.5 Foul-trouble ledger (§27) | minutes and net rating after early fouls vs matched controls | matched control; sample sizes on every cell |

### Phase 6 — Tier 3 (descriptive, quick)

- [ ] 6.1 End-of-quarter card: 2-for-1 chances taken and converted, last-possession points
  (counts always shown).
- [ ] 6.2 Challenge scorecard by team, quarter and call type (~65% of challenges overturned
  league-wide), with n.
- [ ] 6.3 Real-time strip on game pages: game time vs wallclock (median game 137 real minutes),
  stoppages by kind.

### Not building

Raw five-man net ratings as a leaderboard; "clutch gene" player rankings; any timeout or
momentum claim without a matched control; any WPA surface before §19-c passes.

---

## 5. Master checklist (every phase, before it ships)

- [ ] Pre-registration committed in RESULTS-HOOPS before the first read
- [ ] Clock-ordered events (`creation.ordered`) and refilled clocks
- [ ] Gate JSON written to `data/derived/`, verdict and date in `meta.json`
- [ ] Failure diagnosed as data, handling or modeling; recorded either way
- [ ] Row added in `pipeline/sources.py` (feed, method, code, gate, reference)
- [ ] METRICS.md, README and AGENTS.md updated in the same commit
- [ ] `hoops_export.py --check` shows 0 drift
- [ ] `r2_sync.py --dry-run`, then sync (prefix `hoops/` only)
- [ ] `next build` passes; dev check at 1280 px and 375 px with `USE_LOCAL_DATA=true`
- [ ] Copy says what the number is, the sample, and "descriptive, not a forecast" where ungated
- [ ] `COLLABORATION.md` row; commit only our own hunks in shared files
- [ ] The repo is public: nothing raw from LUMA, BDL or news feeds is committed

---

## 6. Extensions with tracking data

Play-by-play tells us *what* happened and *who* touched the ball. Tracking (x/y for all ten
players and the ball, 25 frames a second) tells us *where everyone was*. That opens the
questions play-by-play cannot reach.

**What is legitimately available:**
- **SportVU 2015-16 public sample.** One game is already in `hoops_mart/data/tracking_sample`
  (`0021500492`, 2016-01-01, 452 events); a public archive of about 600 games from that season
  exists. Terms are unclear, so research only and never republished.
- **NBA.com tracking aggregates** (drives, touches, closest-defender buckets, hustle). These
  are licensed data; available only through a licensed provider.
- **Second Spectrum / Hawk-Eye** (current league tracking, including pose). Commercial or team
  access only.

**What each would enable, with a measurable first goal:**

| Extension | Question | First measurable goal |
|---|---|---|
| Defender-aware shot quality | How open was the shot? | Add closest-defender distance to the §20 model on the 2015-16 sample; held-out log-loss gain over §20's features |
| Pick-and-roll detection | How does a team defend the screen (drop, switch, hedge, blitz)? | Screen-event detector precision ≥ 0.8 on a hand-labelled 200-event set |
| Defensive matchups | Who guarded whom, and how did they do? | Franks-style assignment model; agreement with NBA.com matchup minutes r ≥ 0.8 where both exist |
| Spacing and gravity | Does a shooter pull defenders? | Defender distance to a shooter off the ball vs his 3P% tier, controlled for position |
| Rebound positioning | Who wins position before the ball comes down? | Reproduce the Sloan rebound decomposition (positioning, hustle, conversion) on the sample |
| Expected possession value | What was each decision worth mid-possession? | Cervone-style EPV on the sample; calibration of possession outcomes by decile ≤ 0.02 |
| Physical load | Distance and speed per minute | Reconcile tracked distance with NBA.com's published per-game distance within 5% |

**Order if access appears:** defender-aware shot quality first (it upgrades a shipped
model), then matchups, then pick-and-roll. Each one gets a pre-registration like everything
above.
