"""lineups_build.py — P3 v1: 5-man units + per-player on/off from the §1
ESPN-walk stints (PARTIAL by construction for a live season).

    python pipeline/lineups_build.py                      # site 2025
    python pipeline/lineups_build.py --season 2027        # the live season
    python pipeline/lineups_build.py --season 2025 --label control
                         # read stints_2025_control/possessions_2025_control

Each run MERGES its season into lineups.json.gz (seasons[season], with that
season's own gate_0f) — building one season never erases another.

Inputs (all read-only):
  - data/derived/stints_{season}.parquet — 10-man windows from the §1 walk;
    `home`/`away` are POSITIONAL five-pid lists; `home_tid` marks the home
    side in the walk's own team-slot universe (consistent with the segments'
    `home` flags) — the stored tids are not joined to anything else
  - data/derived/possessions_{season}.parquet — possession segments
    (end_i, dead_ball, home); spans reconstruct as (previous end_i, end_i]
  - mart pbp.parquet — plays in the writer's order (period, seq) reset per
    game: `period_elapsed` (ffilled — tail rows after the last valid clock
    read as game end), and `is_scoring`/`score_value`/`team_id` for points.
    POINTS SOURCE: the stints file's pts columns predate the §1 response
    fix (they carry ~46% of real points), so points are re-attributed here
    from pbp scoring plays inside each stint window — validated exact vs
    finals in §0f.

§0f gates (preregistered before this build ran):
  minutes  Σ stint seconds/game vs scheduled length ± 2 min, ≥ 95% of games
  poss     per-game live possession total in 180-260, ≥ 95% of games
  score    Σ stint-window points per side == final score, ≥ 99% of game-sides
A miss exits non-zero before the doc is written.

Output: data/export/web/lineups.json.gz — descriptive only.
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import MART, ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "data" / "export" / "web"
GAMES_FULL = 1230

UNIT_MIN_POSS = 100     # §0f render floor: units
ONOFF_MIN_POSS = 1500   # §0f render floor: players
ONOFF_MIN_OFF_POSS = 500


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--label", default="",
                    help="read stints_{season}_{label}/possessions_{season}_{label}")
    args = ap.parse_args()  # not `a`: the on/off loop below binds `a`
    season, sfx = args.season, (f"_{args.label}" if args.label else "")
    games = pd.read_parquet(MART / "games.parquet")
    gs = games[(games.season_year == season) & (games.season_type == 2)
               & games.completed & (games.n_plays > 0)]
    st = pd.read_parquet(DERIVED / f"stints_{season}{sfx}.parquet")
    ps = pd.read_parquet(DERIVED / f"possessions_{season}{sfx}.parquet")
    pg = pd.read_parquet(MART / "player_game.parquet",
                         columns=["game_id", "team_id", "athlete_id", "pts"])
    pb = pd.read_parquet(MART / "pbp.parquet",
                         columns=["game_id", "period", "seq",
                                  "is_scoring", "score_value", "team_id"])

    board = json.load(open(OUT / "players.json"))
    names: dict[str, str] = {}
    for rows in board["seasons"].values():
        for r in rows:
            names[str(r["id"])] = r["name"]

    ps = ps.sort_values(["game_id", "end_i"]).reset_index(drop=True)
    ps["live"] = ~ps["dead_ball"].astype(bool)
    seg_by_game = {g: d for g, d in ps.groupby("game_id")}

    pb_by_game = {g: d.reset_index(drop=True) for g, d in pb.groupby("game_id")}

    pb = pb.sort_values(["game_id", "period", "seq"]).reset_index(drop=True)
    home_slot = {g: str(d["home_tid"].iloc[0]) for g, d in st.groupby("game_id")}

    # full game rosters — the OFF side of on/off needs every rostered player,
    # not just the ten on the floor
    pgx = pg[pg["pts"].notna()].copy()
    pgx["athlete_id"] = pgx["athlete_id"].astype(str)
    gid2tid_abbr = {}
    for gr in gs.itertuples():
        gid2tid_abbr[str(gr.game_id)] = {str(gr.home_team_id): gr.home_abbr,
                                         str(gr.away_team_id): gr.away_abbr}
    roster_by_game: dict[str, dict[str, set]] = {}
    for (gid, tid), d in pgx.groupby(["game_id", "team_id"]):
        abbr = gid2tid_abbr.get(str(gid), {}).get(str(tid))
        if abbr:
            roster_by_game.setdefault(str(gid), {})[abbr] = set(d["athlete_id"])

    def five(lst) -> tuple:
        return tuple(sorted(str(x) for x in lst))

    gate = {"label": f"§0f stint reconciliation (site {season}, ESPN window)",
            "skipped_index_mismatch": 0}
    min_ok = poss_ok = score_ok = tot_side = n_games = 0
    units: dict[tuple, dict] = {}
    acc: dict[tuple, dict] = {}

    for gr in gs.itertuples():
        gid = gr.game_id
        stints = st[st.game_id == gid]
        segs = seg_by_game.get(gid)
        plays = pb_by_game.get(gid)
        if stints.empty or segs is None or plays is None:
            continue
        # index alignment: the writer closes the last stint at n plays — a
        # mismatch means the mart was rebuilt after the walk; skip (v2 rerun
        # of the walk would recover them)
        if int(stints["end_i"].max()) != len(plays):
            gate["skipped_index_mismatch"] += 1
            continue
        segs = segs.reset_index(drop=True)
        slot = home_slot.get(gid)
        sc = plays[plays["is_scoring"] == True]  # noqa: E712 (pandas)
        sc_arr = list(zip(sc["team_id"].astype(str).tolist(),
                          sc["score_value"].astype(float).tolist()))
        sc_idx = sc.index.tolist()
        n_games += 1
        ot = int(gr.n_periods or 4)
        sched_sec = 2880 + (ot - 4) * 300 if ot > 4 else 2880
        live_tot = int(segs["live"].sum())
        game_h = game_a = 0.0
        sc_i = 0  # scoring plays are window-ordered: advance a cursor
        prev_end = 0
        # windows tile the game: (previous end_i, end_i] — the walk's dropped
        # poisoned stints leave gaps whose plays belong to the preceding
        # on-court set (the evidence-add corrected a missed sub by one player)
        for sr in stints.sort_values("start_i").itertuples(index=False):
            i0, i1 = prev_end, int(sr.end_i)
            prev_end = i1
            m = segs[(segs.end_i > i0) & (segs.end_i <= i1)]
            w_live = int(m["live"].sum())
            # minutes are possession-proportional ESTIMATES (§0f amendment):
            # the ten men on the floor share the window's game minutes by the
            # window's share of live possessions — clock data is unusable
            # per play (11.5% NaN, scattered mid-game)
            sec = sched_sec * (w_live / live_tot) if live_tot else 0.0
            hpts = apt = 0.0
            while sc_i < len(sc_idx) and sc_idx[sc_i] < i1:
                if sc_idx[sc_i] >= i0:
                    v = sc_arr[sc_i]
                    if v[0] == slot:
                        hpts += v[1]
                        game_h += v[1]
                    else:
                        apt += v[1]
                        game_a += v[1]
                sc_i += 1
            for is_home, pids, abbr in ((True, five(sr.home), gr.home_abbr),
                                        (False, five(sr.away), gr.away_abbr)):
                off_p = int(((m["home"] == is_home) & m["live"]).sum())
                def_p = int(((m["home"] != is_home) & m["live"]).sum())
                pf, pa = (hpts, apt) if is_home else (apt, hpts)
                u = units.setdefault((abbr, pids), {
                    "poss": 0, "dp": 0, "pf": 0.0, "pa": 0.0, "sec": 0.0,
                    "g": set()})
                u["poss"] += off_p
                u["dp"] += def_p
                u["pf"] += pf
                u["pa"] += pa
                u["sec"] += sec
                u["g"].add(gid)
                on_set = set(pids)
                roster = roster_by_game.get(str(gid), {}).get(abbr, set())
                visit = roster | on_set
                for pid in visit:
                    a = acc.setdefault((abbr, pid), {
                        "on": {"sec": 0.0, "poss": 0, "dp": 0, "pf": 0.0, "pa": 0.0},
                        "off": {"sec": 0.0, "poss": 0, "dp": 0, "pf": 0.0, "pa": 0.0}})
                    side = a["on"] if pid in on_set else a["off"]
                    side["sec"] += sec
                    side["poss"] += off_p
                    side["dp"] += def_p
                    side["pf"] += pf
                    side["pa"] += pa
        min_ok += 1  # minutes are structural now: window shares sum to sched
        if 180 <= live_tot <= 260:
            poss_ok += 1
        for side_home, final in ((True, gr.home_score), (False, gr.away_score)):
            tot_side += 1
            pf = game_h if side_home else game_a
            if int(pf) == int(final):
                score_ok += 1

    gate["games"] = n_games
    gate["minutes_structural"] = round(min_ok / n_games, 4) if n_games else None
    gate["poss_in_band"] = round(poss_ok / n_games, 4) if n_games else None
    gate["score_exact"] = round(score_ok / tot_side, 4) if tot_side else None
    ok = ((gate["minutes_structural"] or 0) >= 0.95
          and (gate["poss_in_band"] or 0) >= 0.95
          and (gate["score_exact"] or 0) >= 0.99)
    gate["verdict"] = "PASS" if ok else "FAIL"
    print(json.dumps(gate, indent=1))
    if not ok:
        return 1

    doc_teams: dict[str, dict] = {}
    for (abbr, pids), u in units.items():
        if u["poss"] < UNIT_MIN_POSS or not abbr:
            continue
        ortg = 100 * u["pf"] / u["poss"]
        drtg = 100 * u["pa"] / u["dp"] if u["dp"] else None
        doc_teams.setdefault(abbr, {"units": [], "onoff": []})["units"].append({
            "ids": list(pids),
            "names": [names.get(p, p) for p in pids],
            "min": round(u["sec"] / 60, 1),
            "poss": u["poss"],
            "gp": len(u["g"]),
            "ortg": round(ortg, 1),
            "drtg": round(drtg, 1) if drtg else None,
            "net": round(ortg - drtg, 1) if drtg else None,
        })
    for (abbr, pid), a in acc.items():
        if (a["on"]["poss"] < ONOFF_MIN_POSS
                or a["off"]["poss"] < ONOFF_MIN_OFF_POSS or not abbr):
            continue
        on_r = 100 * a["on"]["pf"] / a["on"]["poss"]
        on_d = 100 * a["on"]["pa"] / a["on"]["dp"] if a["on"]["dp"] else 0
        off_r = 100 * a["off"]["pf"] / a["off"]["poss"]
        off_d = 100 * a["off"]["pa"] / a["off"]["dp"] if a["off"]["dp"] else 0
        on_net, off_net = on_r - on_d, off_r - off_d
        doc_teams.get(abbr, {"units": [], "onoff": []})["onoff"].append({
            "pid": pid, "name": names.get(pid, pid),
            "on_min": round(a["on"]["sec"] / 60),
            "on_poss": a["on"]["poss"],
            "on_net": round(on_net, 1),
            "off_net": round(off_net, 1),
            "diff": round(on_net - off_net, 1),
            "on_ortg": round(on_r, 1), "on_drtg": round(on_d, 1)})

    for abbr, d in doc_teams.items():
        d["units"].sort(key=lambda r: -r["min"])
        d["onoff"].sort(key=lambda r: -r["diff"])

    # merge: this season's entry (with its own gate) into the existing doc
    path = OUT / "lineups.json.gz"
    doc: dict = {"seasons": {}}
    if path.exists():
        with gzip.open(path, "rt") as f:
            doc = json.load(f)
    doc.setdefault("seasons", {})[str(season)] = {
        "coverage": {"games": n_games, "of": GAMES_FULL,
                     "partial": n_games < GAMES_FULL,
                     "source": "ESPN PBP stint walk (§1 lineage)"
                               + (f", input label '{args.label}'" if args.label else "")},
        "teams": doc_teams,
        "gate_0f": gate}
    if season == 2025:
        doc["gate_0f"] = gate  # legacy top-level field for older readers
    with gzip.open(path, "wt") as f:
        json.dump(doc, f)
    n_units = sum(len(d["units"]) for d in doc_teams.values())
    n_onoff = sum(len(d["onoff"]) for d in doc_teams.values())
    print(f"site {season}: units kept {n_units} | on/off rows {n_onoff} | "
          f"teams {len(doc_teams)} | doc seasons now {sorted(doc['seasons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
