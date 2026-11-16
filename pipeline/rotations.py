"""rotations.py — rotation fingerprint and stint chart from the §21 clock walk (§22).

    python pipeline/rotations.py --gate            # §22 read, 2024-25 vs pbpstats
    python pipeline/rotations.py --season 2027     # structural gates 3-5 only

`build(season)` is what the bake calls: per team a minute-by-minute share of
games on the floor (top 13 players), stint length, stints per game and the
closing five; per game each player's stints with the plus-minus inside them.

Inputs: data/derived/stints_{season}.parquet (clock walk: `home`/`away` five
lists, `t0`/`t1` in period seconds, `start_i`/`end_i` into the clock-ordered
plays; `home_tid` is the walk's home slot, comparable to pbp `team_id`).
Points come from pbp scoring plays inside each stint window (§0f: exact vs
finals); the stints file's own pts columns are stale (lineups_build note).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import MART, ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
TOP = 13
CLOSE_FROM = 2580  # last 5:00 of regulation


def off(period: int) -> int:
    return (period - 1) * 720 if period <= 4 else 2880 + (period - 5) * 300


def load(season: int):
    g = pd.read_parquet(MART / "games.parquet")
    gs = load_games(season)
    st = pd.read_parquet(DERIVED / f"stints_{season}.parquet")
    pb = pd.read_parquet(MART / "pbp.parquet",
                         columns=["game_id", "period", "seq", "is_scoring", "score_value", "team_id",
                                  "clock_display", "clock_sec", "period_elapsed",
                                  "home_score", "away_score"])
    from creation import clock_frame  # same order as the walk, so start_i/end_i line up
    pb = clock_frame(pb[pb.game_id.isin(gs.game_id)])
    pg = pd.read_parquet(MART / "player_game.parquet",
                         columns=["game_id", "team_id", "athlete_id", "name", "min", "pts", "starter"])
    pg = pg[pg.game_id.isin(gs.game_id) & pg.pts.notna()].copy()
    pg["athlete_id"] = pg.athlete_id.astype(str)
    return gs, st, pb, pg


def player_stints(gs, st, pb) -> pd.DataFrame:
    """One row per continuous floor spell: game_id, home, pid, g0, g1 (game seconds), pm.
    Consecutive windows that touch (g1 == next g0) merge, across period breaks too."""
    pb_by = {g: d for g, d in pb.groupby("game_id", sort=False)}
    rows = []
    for gid, d in st.groupby("game_id", sort=False):
        plays = pb_by.get(gid)
        if plays is None or int(d.end_i.max()) > len(plays):
            continue  # mart rebuilt after the walk; a dropped final stint leaves end_i short (fine)
        slot = str(d.home_tid.iloc[0])
        sv = np.where(plays.is_scoring.fillna(False).to_numpy(bool),
                      plays.score_value.fillna(0).to_numpy(float), 0.0)
        sign = np.where(plays.team_id.astype(str).to_numpy() == slot, 1.0, -1.0)
        margin = np.cumsum(sv * sign)  # home margin after each play
        at = lambda i: float(margin[i - 1]) if i > 0 else 0.0  # noqa: E731
        live: dict[tuple, list] = {}
        prev_end = 0
        rows_d = list(d.sort_values("start_i").itertuples(index=False))
        for k, s in enumerate(rows_d):
            # windows tile: (previous end_i, end_i]; the last runs to the last play
            i0, i1 = prev_end, (len(plays) if k == len(rows_d) - 1 else int(s.end_i))
            prev_end = i1
            g0, g1 = off(int(s.period)) + float(s.t0), off(int(s.period)) + float(s.t1)
            dm = at(i1) - at(i0)
            for home, five in ((True, s.home), (False, s.away)):
                for pid in five:
                    k = (home, str(pid))
                    cur = live.get(k)
                    if cur is not None and abs(cur[1] - g0) < 1e-6:
                        cur[1] = g1
                        cur[2] += dm if home else -dm
                    else:
                        if cur is not None:
                            rows.append((gid, home, k[1], *cur))
                        live[k] = [g0, g1, dm if home else -dm]
        for (home, pid), cur in live.items():
            rows.append((gid, home, pid, *cur))
    ps = pd.DataFrame(rows, columns=["game_id", "home", "pid", "g0", "g1", "pm"])
    gmap = gs.set_index("game_id")
    ps["abbr"] = np.where(ps.home, ps.game_id.map(gmap.home_abbr), ps.game_id.map(gmap.away_abbr))
    return ps[ps.g1 > ps.g0]


def bin_seconds(ps: pd.DataFrame) -> pd.DataFrame:
    """(abbr, pid) x 48 regulation-minute bins of floor seconds."""
    a = ps[ps.g0 < 2880]
    g0, g1 = a.g0.to_numpy(), np.minimum(a.g1.to_numpy(), 2880)
    edges = np.arange(49) * 60.0
    cover = np.clip(np.minimum(g1[:, None], edges[1:]) - np.maximum(g0[:, None], edges[:-1]), 0, None)
    out = pd.DataFrame(cover, index=pd.MultiIndex.from_arrays([a.abbr, a.pid]))
    return out.groupby(level=[0, 1]).sum()


def closing_five(ps: pd.DataFrame, pb: pd.DataFrame, gs: pd.DataFrame) -> dict:
    """abbr -> (five pids, games, share of close-game closing seconds)."""
    # margin at 5:00 left of Q4 from the clock-ordered running score
    q4 = pb[(pb.period == 4) & (pb.period_elapsed <= 420)]
    last = q4.groupby("game_id")[["home_score", "away_score"]].last()
    close = set(last.index[(last.home_score - last.away_score).abs() <= 5])
    c = ps[ps.game_id.isin(close) & (ps.g1 > CLOSE_FROM) & (ps.g0 < 2880)].copy()
    c["sec"] = np.minimum(c.g1, 2880) - np.maximum(c.g0, CLOSE_FROM)
    out = {}
    for abbr, d in c.groupby("abbr"):
        # the five on the floor at each second-slice: split at every boundary
        cuts = sorted({CLOSE_FROM, 2880, *d.g0.clip(CLOSE_FROM, 2880), *d.g1.clip(CLOSE_FROM, 2880)})
        acc, games = {}, d.game_id.nunique()
        for gid, gd in d.groupby("game_id"):
            for lo, hi in zip(cuts, cuts[1:]):
                on = gd[(gd.g0 <= lo) & (gd.g1 >= hi)].pid
                if len(on) == 5:
                    k = tuple(sorted(on))
                    acc[k] = acc.get(k, 0.0) + hi - lo
        if acc:
            k, v = max(acc.items(), key=lambda kv: kv[1])
            out[abbr] = (list(k), games, v / (300.0 * games))
    return out


def build(season: int):
    """-> (teams: {abbr: rotation doc}, games: {gid: {abbr: [[name, [[g0, g1, pm], ...]]]}}, ps)."""
    gs, st, pb, pg = load(season)
    ps = player_stints(gs, st, pb)
    names = pg.drop_duplicates("athlete_id", keep="last").set_index("athlete_id").name.to_dict()
    bins = bin_seconds(ps)
    n_games = ps.groupby("abbr").game_id.nunique()
    closers = closing_five(ps, pb, gs)
    teams = {}
    for abbr, b in bins.groupby(level=0):
        b = b.droplevel(0)
        n = int(n_games[abbr])
        mine = ps[ps.abbr == abbr]
        tot = mine.assign(s=mine.g1 - mine.g0).groupby("pid").s.sum().sort_values(ascending=False)
        gp = mine.groupby("pid").game_id.nunique()
        players = []
        for pid in tot.index[:TOP]:
            sh = b.loc[pid].to_numpy() / (60.0 * n) if pid in b.index else np.zeros(48)
            sp = mine[mine.pid == pid]
            players.append({"id": pid, "name": names.get(pid, pid),
                            "mpg": round(tot[pid] / 60 / int(gp[pid]), 1), "gp": int(gp[pid]),
                            "stint": round((sp.g1 - sp.g0).mean() / 60, 1),
                            "spg": round(len(sp) / int(gp[pid]), 1),
                            "sh": [int(round(x * 100)) for x in sh]})
        cl = closers.get(abbr)
        teams[abbr] = {"games": n, "players": players,
                       "close": None if not cl else {"ids": cl[0], "names": [names.get(p, p) for p in cl[0]],
                                                     "games": cl[1], "share": round(cl[2], 3)}}
    games = {}
    for (gid, abbr), d in ps.sort_values("g0").groupby(["game_id", "abbr"]):
        rows = {}
        for r in d.itertuples():
            rows.setdefault(r.pid, []).append([int(round(r.g0)), int(round(r.g1)), int(r.pm)])
        games.setdefault(str(gid), {})[abbr] = [[names.get(p, p), s] for p, s in
                                                sorted(rows.items(), key=lambda kv: kv[1][0][0])]
    return teams, games, ps, bins, n_games, pg


def structural(ps, bins, n_games, pg) -> dict:
    """§22 gates 3-5 (every season)."""
    team_sum = bins.groupby(level=0).sum().div(60.0 * n_games, axis=0)
    g3 = float((team_sum - 5).abs().to_numpy().max())
    ours_pg = ps.assign(m=(ps.g1 - ps.g0) / 60).groupby(["pid", "game_id"]).m.sum()
    box = pg[pg["min"] > 0].set_index(["athlete_id", "game_id"])["min"]
    j = pd.concat([ours_pg.rename("ours"), box.rename("box")], axis=1).dropna()
    g5 = float(((j.ours - j.box).abs() <= 1.0).mean())
    season = j.groupby(level=0).sum()
    season = season[season.box >= 500]
    g4 = float(((season.ours - season.box).abs() / season.box <= 0.01).mean())
    return {"g3_max_bin_dev": round(g3, 4), "g3_pass": g3 <= 0.01,
            "g4_within_1pct": round(g4, 4), "g4_n": int(len(season)), "g4_pass": g4 >= 0.95,
            "g5_within_1min": round(g5, 4), "g5_n": int(len(j)), "g5_pass": g5 >= 0.95}


def jaccard(a: list, b: list) -> float:
    inter, i, k = 0.0, 0, 0
    while i < len(a) and k < len(b):
        lo, hi = max(a[i][0], b[k][0]), min(a[i][1], b[k][1])
        inter += max(0.0, hi - lo)
        if a[i][1] < b[k][1]:
            i += 1
        else:
            k += 1
    la, lb = sum(y - x for x, y in a), sum(y - x for x, y in b)
    return inter / (la + lb - inter) if la + lb - inter > 0 else 1.0


def gate(season: int = 2025) -> int:
    """§22 read: gates 1-2 vs pbpstats playing-time intervals, plus 3-5."""
    from model_rows import PT, spans_for
    from stints_from_pt import XWALK, norm
    teams, games, ps, bins, n_games, pg = build(season)
    res = structural(ps, bins, n_games, pg)
    gs = load_games(season)
    sstr = f"{season - 1}-{str(season)[2:]}"
    gs["home_x"] = gs.home_abbr.map(lambda x: XWALK.get(x, x))
    pbs = pd.read_parquet(PT / "games.parquet")
    pbs = pbs[(pbs.season == sstr) & (pbs.season_type == "Regular Season")]
    m = gs.merge(pbs, left_on=["date_et", "home_x"], right_on=["Date", "HomeTeamAbbreviation"])
    nba2espn = dict(zip(m.GameId.astype(str), m.game_id))
    joined = set(m.game_id)
    pg = pg[pg.game_id.isin(joined)].copy()
    pg["nm"] = pg.name.map(norm)
    nm2pid = pg.set_index(["nm", "game_id"]).athlete_id.to_dict()
    ref = {}
    for name, nid in json.load(open(PT / f"pt_ids_{sstr}.json")).items():
        for ngid, info in spans_for(int(nid), sstr).items():
            gid = nba2espn.get(str(ngid))
            pid = nm2pid.get((norm(name), gid)) if gid is not None else None
            if pid:
                ref.setdefault((pid, gid), []).extend(info["spans"])
    ours = {k: sorted([float(a), float(b)] for a, b in zip(d.g0, d.g1))
            for k, d in ps[ps.game_id.isin(joined)].groupby(["pid", "game_id"])}

    # population: (player, team) with >= 500 box minutes for that team in joined games
    abbr_of = dict(zip(zip(ps.game_id, ps.pid), ps.abbr))
    pg["abbr"] = [abbr_of.get((g, p)) for g, p in zip(pg.game_id, pg.athlete_id)]
    pop = pg.groupby(["athlete_id", "abbr"])["min"].sum()
    pop = pop[pop >= 500].index
    team_games = {a: len(set(ps[(ps.abbr == a) & ps.game_id.isin(joined)].game_id)) for a in n_games.index}

    edges = np.arange(49) * 60.0

    def binned(ivs):
        v = np.zeros(48)
        for a, b in ivs:
            v += np.clip(np.minimum(min(b, 2880), edges[1:]) - np.maximum(a, edges[:-1]), 0, None)
        return v

    xs, ys, jac = [], [], []
    for pid, abbr in pop:
        gids = pg[(pg.athlete_id == pid) & (pg.abbr == abbr)].game_id
        o, r = np.zeros(48), np.zeros(48)
        for gid in gids:
            a, b = ours.get((pid, gid), []), sorted(ref.get((pid, gid), []))
            o += binned(a)
            r += binned(b)
            la, lb = sum(y - x for x, y in a), sum(y - x for x, y in b)
            if max(la, lb) >= 300:
                jac.append(jaccard(a, b))
        n = 60.0 * team_games[abbr]
        xs.extend(o / n)
        ys.extend(r / n)
    xs, ys = np.array(xs), np.array(ys)
    r1, mad = float(np.corrcoef(xs, ys)[0, 1]), float(np.abs(xs - ys).mean())
    jm = float(np.median(jac))
    res.update({"season": season, "population": int(len(pop)), "cells": int(len(xs)),
                "g1_r": round(r1, 4), "g1_mad": round(mad, 4), "g1_pass": r1 >= 0.95 and mad <= 0.03,
                "g2_jaccard_median": round(jm, 4), "g2_n": len(jac), "g2_pass": jm >= 0.95,
                "jaccard_p10": round(float(np.percentile(jac, 10)), 4)})
    res["pass"] = all(res[k] for k in ("g1_pass", "g2_pass", "g3_pass", "g4_pass", "g5_pass"))
    (DERIVED / f"gate_rotations_{season}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0 if res["pass"] else 1


def load_games(season: int) -> pd.DataFrame:
    """Regular-season games between NBA teams (§22: the feed files All-Star
    exhibition sides as regular season; they play ≤ 3 games, NBA teams 10+ —
    a 40-game cut dropped CHI, which has PBP for only 39 games of 2025-26)."""
    g = pd.read_parquet(MART / "games.parquet")
    g = g[(g.season_year == season) & (g.season_type == 2) & g.completed & (g.n_plays > 0)]
    n = pd.concat([g.home_abbr, g.away_abbr]).value_counts()
    nba = set(n[n >= 10].index) if n.max() >= 10 else set(n.index)  # first days: no filter
    return g[g.home_abbr.isin(nba) & g.away_abbr.isin(nba)].copy()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--gate", action="store_true", help="§22 external read (2024-25 only)")
    a = ap.parse_args()
    if a.gate:
        sys.exit(gate(a.season))
    _, _, ps, bins, n_games, pg = build(a.season)
    r = structural(ps, bins, n_games, pg)
    print(json.dumps(r, indent=1))
    sys.exit(0 if all(v for k, v in r.items() if k.endswith("_pass")) else 1)
