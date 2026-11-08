# Visuals brainstorm — telling stories with the data (2026-11-08)

The ask: new visuals that are fun and creative but statistically correct, giving
coaches and a front office the high-end analytics feel. Every idea below maps
to data we ALREADY hold (the mart, the seasavgs pulls, the §9/§14 artifacts) —
no new pulls needed. Status: **built this pass** / queued with its data source.

## Built this pass

### 1 · Percentile radar (player page) — the identity profile
Eight axes from the baked percentiles (TS%, USG%, net rating, PIE, drive
scoring, AST points created, distance, deflections) drawn as a blue-filled
polygon on the league scale, with the position-pool overlay. Coaches read a
player's shape in one glance: pentagon of skill vs spikes. Data: `pct_ranks`
+ `pct_ranks_pos` in the seasavgs docs — no bake change. The radar is the
percentile scale made geometric: the polygon edge IS the blue/green/red
thresholds.

### 2 · Shot-quality quadrant (player page) — the §9 story as a picture
The shot-diet vs shot-making scatter: x = the league-expected eFG of the
zones the player actually takes (his DIET), y = his actual eFG minus that
expectation (his MAKING). The whole league pool renders dim; the player
renders bright with his FGA as the dot size. Quadrants: right-top "great
diet, makes it" (Durant), left-top "shot-maker carrying a hard diet"
(Kennard), right-bottom "feasting, not finishing the value" , left-bottom
"tough gig". Data: `shootmk {xefg, efg, diff, n_fga}` — already baked per
player by the §9 gate. Zero client JS: server-rendered SVG.

### 3 · Season margin sparkline (team page) — the season as one line
Game-by-game scoring margin, W/L ticked, zero line emphasized — the
streaks, the blowouts, the heartbreaks visible in one strip. Data: the team
doc's game list (already on the page). Descriptive by construction.

## Queued (with data readiness)

4 · **Game run chart** (games) — lead/margin timeline over possession time
from the game doc's play feed; period bands, run annotations. Data: the
game page's plays ✓. The most coach-relevant missing visual.
5 · **Usage-vs-efficiency league scatter** (/stats) — who scores well at
high volume; labeled outliers, season selector. Data: players.json ✓.
6 · **Lineup net diverging bars** (team page) — the /lineups table as a
picture, on the team page. Data: lineups.json ✓.
7 · **On/off waterfall** (player page) — on-court vs off net with the
diff as the bridge. Data: lineups.json onoff ✓.
8 · **Schedule-density strip** (team page) — rest days + B2B clusters as a
calendar ribbon. Data: game logs ✓.
9 · **Era-normalized career overlay** (compare) — careers.json vs the era
env from /eras (the §14 groundwork makes this statistically honest).
10 · **Matchup matrix** (team page) — season series vs each opponent,
margin-coded. Data: game logs ✓.
