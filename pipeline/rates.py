"""rates.json.gz — §0h: NBA.com-definition player rates rebuilt from the ESPN
mart, so the live season's advanced columns stay current after the
balldontlie trial froze them (pipeline/results/RESULTS-HOOPS.md §0h).

Called from the bake (hoops_export.bake → rates_phase, after advagg_phase,
whose 2025 roll-ups are the gate reference). Standalone:

    python pipeline/rates.py      # identity self-check, then the §0h gate read
"""

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART, OUT, jwrite_gz  # noqa: E402

BOX = {"fieldGoalsMade-fieldGoalsAttempted_made": "fgm",
       "fieldGoalsMade-fieldGoalsAttempted_att": "fga",
       "threePointFieldGoalsMade-threePointFieldGoalsAttempted_made": "tpm",
       "threePointFieldGoalsMade-threePointFieldGoalsAttempted_att": "tpa",
       "freeThrowsMade-freeThrowsAttempted_made": "ftm",
       "freeThrowsMade-freeThrowsAttempted_att": "fta",
       "points": "pts", "offensiveRebounds": "oreb", "defensiveRebounds": "dreb",
       "totalRebounds": "reb", "assists": "ast", "steals": "stl", "blocks": "blk",
       "totalTurnovers": "tov"}
PSUM = ["min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "reb",
        "ast", "stl", "blk", "tov", "pf"]
# stat -> (round digits, §0h gate: (min r, max median |diff|) or None = ungated)
STATS = {"ts_pct": (3, (0.995, 0.005)), "efg_pct": (3, (0.995, 0.005)),
         "ftr": (3, None),  # §0h-b: withdrawn — balldontlie has no player-level FT rate
         "to_ratio": (1, (0.995, 0.5)),
         "ast_to": (2, (0.99, None)), "usg_pct": (3, (0.97, None)),
         "ast_pct": (3, (0.97, None)), "orb_pct": (3, (0.97, None)),
         "drb_pct": (3, (0.97, None)), "reb_pct": (3, (0.97, None)),
         "pie": (3, (0.98, None)), "stl_pct": (3, None), "blk_pct": (3, None),
         "tpar": (3, None)}
LOWER_BETTER = ("to_ratio",)
POS = {"G": "G", "PG": "G", "SG": "G", "F": "F", "SF": "F", "PF": "F", "C": "C"}
FULL_QUAL_MIN = 500  # completed-season minutes floor; the live season scales it
POOL_MIN = 40        # a position pool renders only with this many qualifiers


def pie_expr(d, tov="tov"):
    return (d.pts + d.fgm + d.ftm - d.fga - d.fta + d.dreb + 0.5 * d.oreb
            + d.ast + d.stl + 0.5 * d.blk - d.pf - d[tov])


def team_games(tg: pd.DataFrame, pg: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """One row per regular-season (game, team): own box as tm_*, opponent as o_*."""
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    t = tg.rename(columns=BOX)[["game_id", "team_id", *BOX.values()]].copy()
    t[["game_id", "team_id"]] = t[["game_id", "team_id"]].astype(str)
    t = t.merge(reg, on="game_id")
    p = pg[pg["min"] > 0].astype({"game_id": str, "team_id": str})
    t = t.merge(p.groupby(["game_id", "team_id"]).agg(tmin=("min", "sum"), pf=("pf", "sum"))
                .reset_index(), on=["game_id", "team_id"])
    t["poss"] = t.fga - t.oreb + t.tov + 0.44 * t.fta
    t["pie"] = pie_expr(t)
    own = t.rename(columns=lambda c: c if c in ("game_id", "team_id", "season_year") else f"tm_{c}")
    opp = t.drop(columns="season_year").rename(
        columns=lambda c: "game_id" if c == "game_id" else f"o_{c}")
    both = own.merge(opp, on="game_id")
    return both[both.team_id != both.o_team_id]


def player_rates(pg: pd.DataFrame, tgo: pd.DataFrame) -> pd.DataFrame:
    """One row per (season, athlete): summed box + every §0h rate."""
    p = pg[pg.pts.notna() & (pg["min"] > 0)].rename(columns={"to": "tov"})
    p = p.astype({"game_id": str, "team_id": str, "athlete_id": str})
    p = p.merge(tgo, on=["game_id", "team_id"])  # inner: regular season only
    s = p["min"] / (p.tm_tmin / 5)
    p = p.assign(
        d_usg=s * (p.tm_fga + 0.44 * p.tm_fta + p.tm_tov), d_ast=s * p.tm_fgm,
        d_orb=s * (p.tm_oreb + p.o_dreb), d_drb=s * (p.tm_dreb + p.o_oreb),
        d_reb=s * (p.tm_reb + p.o_reb), d_stl=s * 0.5 * (p.tm_poss + p.o_poss),
        d_blk=s * (p.o_fga - p.o_tpa), n_pie=pie_expr(p), d_pie=p.tm_pie + p.o_pie)
    dens = ["d_usg", "d_ast", "d_orb", "d_drb", "d_reb", "d_stl", "d_blk", "n_pie", "d_pie"]
    a = p.groupby(["season_year", "athlete_id"]).agg(
        **{c: (c, "sum") for c in PSUM + dens}, gp=("game_id", "nunique"),
        pos=("position", lambda x: x.map(POS).mode().iat[0] if x.map(POS).notna().any() else None),
        team=("team_id", lambda x: x.mode().iat[0])).reset_index()

    def div(n, d):
        return (n / d).where(d > 0)

    a["ts_pct"] = div(a.pts, 2 * (a.fga + 0.44 * a.fta))
    a["efg_pct"] = div(a.fgm + 0.5 * a.tpm, a.fga)
    a["ftr"] = div(a.fta, a.fga)
    a["tpar"] = div(a.tpa, a.fga)
    a["ast_to"] = div(a.ast, a.tov)
    a["to_ratio"] = div(100 * a.tov, a.fga + 0.44 * a.fta + a.ast + a.tov)
    a["usg_pct"] = div(a.fga + 0.44 * a.fta + a.tov, a.d_usg)
    a["ast_pct"] = div(a.ast, a.d_ast - a.fgm)
    a["orb_pct"] = div(a.oreb, a.d_orb)
    a["drb_pct"] = div(a.dreb, a.d_drb)
    a["reb_pct"] = div(a.reb, a.d_reb)
    a["stl_pct"] = div(a.stl, a.d_stl)
    a["blk_pct"] = div(a.blk, a.d_blk)
    a["pie"] = div(a.n_pie, a.d_pie)
    return a


def pctile(vals: pd.Series, higher_better: bool) -> pd.Series:
    """0-100 percentile within the pool (ties share the average rank)."""
    r = vals.rank(pct=True, ascending=higher_better)
    return (100 * (r - 0.5 / len(vals))).round().astype(int)


def gate(a: pd.DataFrame, adv_path: Path) -> dict:
    """§0h read: our site-2025 rates vs balldontlie's advagg roll-ups."""
    if not adv_path.exists():
        return {"verdict": "NO-REFERENCE"}
    with gzip.open(adv_path, "rt") as f:
        ref = json.load(f)["seasons"].get("2025", {}).get("players", {})
    ours = a[(a.season_year == 2025) & (a["min"] >= 500)].set_index("athlete_id")
    both = [e for e in ours.index if e in ref]
    out = {"sample": len(both), "season": 2025, "stats": {}}
    for k, (_, bar) in STATS.items():
        if bar is None:
            continue
        x = pd.Series({e: ours.at[e, k] for e in both}, dtype=float)
        y = pd.Series({e: ref[e].get(k) for e in both}, dtype=float)
        ok_ = x.notna() & y.notna()
        r = float(x[ok_].corr(y[ok_]))
        med = float((x[ok_] - y[ok_]).abs().median())
        min_r, max_med = bar
        out["stats"][k] = {"n": int(ok_.sum()), "r": round(r, 4), "median_abs_diff": round(med, 4),
                           "pass": bool(r >= min_r and (max_med is None or med <= max_med))}
    out["verdict"] = "PASS" if all(v["pass"] for v in out["stats"].values()) else "PARTIAL"
    return out


GATE_B = Path(__file__).resolve().parents[1] / "data" / "derived" / "gate_rates_0hb.json"
# stat -> (balldontlie field, match tolerance) — §0h-b; ftr withdrawn (no player-level field)
GATE_B_STATS = {"ts_pct": ("true_shooting_percentage", 0.0015),
                "efg_pct": ("effective_field_goal_percentage", 0.0015),
                "to_ratio": ("turnover_ratio", 0.15),
                "ast_to": ("assist_to_turnover", 0.015), "pie": ("pie", 0.0015)}


def gate_b(pg, tg, g) -> dict:
    """§0h-b: per-(game, player) pure-box ratios vs balldontlie's full-game rows,
    BDL season 2024 = site 2025, regular season. Scans every recovered source;
    period != 0 rows are single quarters and are skipped."""
    from hoops_export import BDL, BDL_ABBR2ESPN, flatten_bdl_row, norm_name
    want = {"game.id", "player.id", "game.date", "game.season", "game.postseason", "period",
            "player.first_name", "player.last_name", "team.abbreviation",
            *(f for f, _ in GATE_B_STATS.values())}
    ref, seen = {}, set()

    def take(d):
        if d.get("period") not in (0, None) or d.get("game.season") != 2024 or d.get("game.postseason"):
            return
        k = (d["game.id"], d["player.id"])
        if k in seen:
            return
        seen.add(k)
        nm = norm_name(f"{d.get('player.first_name', '')} {d.get('player.last_name', '')}")
        ab = BDL_ABBR2ESPN.get(d.get("team.abbreviation"), d.get("team.abbreviation"))
        ref[(str(d["game.date"])[:10], ab, nm)] = d

    for fn in ("advanced_2024.pages.jsonl", "advanced_2025.pages.jsonl"):
        p = BDL / fn
        if p.exists():
            with open(p) as f:
                for line in f:
                    try:
                        for r in json.loads(line).get("rows", []):
                            take(flatten_bdl_row(r))
                    except json.JSONDecodeError:
                        continue
    for fn in ("advanced_2024_salvaged.parquet", "advanced_v2_checkpoints_recovered.parquet",
               "advanced_2023.parquet"):
        p = BDL / fn
        if p.exists():
            df = pd.read_parquet(p)
            df = df[[c for c in df.columns if c in want]]
            for d in df.to_dict("records"):
                take(d)

    t = team_games(tg, pg, g)
    p = pg[pg.pts.notna() & (pg["min"] > 0)].rename(columns={"to": "tov"})
    p = p.astype({"game_id": str, "team_id": str}).merge(t[t.season_year == 2025], on=["game_id", "team_id"])
    gi = g.astype({"game_id": str}).set_index("game_id")
    abbr = {}
    for r in g.itertuples():
        abbr[(str(r.game_id), str(int(r.home_team_id)))] = r.home_abbr
        abbr[(str(r.game_id), str(int(r.away_team_id)))] = r.away_abbr
    ours = {"ts_pct": lambda r: r.pts / (2 * (r.fga + 0.44 * r.fta)) if r.fga + r.fta > 0 else None,
            "efg_pct": lambda r: (r.fgm + 0.5 * r.tpm) / r.fga if r.fga > 0 else None,
            "to_ratio": lambda r: (100 * r.tov / (r.fga + 0.44 * r.fta + r.ast + r.tov)
                                   if r.fga + r.fta + r.ast + r.tov > 0 else None),
            "ast_to": lambda r: r.ast / r.tov if r.tov > 0 else None,
            "pie": lambda r: r.n_pie / r.d_pie if r.d_pie else None}
    p = p.assign(n_pie=pie_expr(p), d_pie=p.tm_pie + p.o_pie)
    hits = {k: [0, 0] for k in GATE_B_STATS}
    joined = 0
    for r in p.itertuples():
        key = (str(gi.at[r.game_id, "date_et"])[:10], abbr.get((r.game_id, r.team_id)), norm_name(r.name))
        d = ref.get(key)
        if d is None:
            continue
        joined += 1
        for k, (field, tol) in GATE_B_STATS.items():
            mine, theirs = ours[k](r), d.get(field)
            if mine is None or theirs is None or theirs != theirs:
                continue
            hits[k][1] += 1
            hits[k][0] += abs(mine - float(theirs)) <= tol
    out = {"registered": "§0h-b", "bdl_rows": len(ref), "espn_rows": len(p), "joined": joined, "stats": {}}
    for k, (m, n) in hits.items():
        rate = m / n if n else 0.0
        out["stats"][k] = {"compared": n, "match_rate": round(rate, 4),
                           "pass": bool(n >= 10_000 and rate >= 0.97)}
    return out


def build(pg, tg, g, adv_path: Path) -> dict:
    a = player_rates(pg, team_games(tg, pg, g))
    gt = gate(a, adv_path)
    if GATE_B.exists():  # §0h-b re-test, run offline (it scans GBs): a pass overrides a §0h miss
        gt["b"] = json.loads(GATE_B.read_text())
        for k, v in gt["b"]["stats"].items():
            if v["pass"] and k in gt["stats"]:
                gt["stats"][k]["pass_0hb"] = True
    failed = {k for k, v in gt.get("stats", {}).items() if not (v["pass"] or v.get("pass_0hb"))}
    shown = [k for k in STATS if k not in failed]
    team_gp = g[g.season_type == 2].groupby("season_year").size() * 2 / 30  # games per team
    seasons, league = {}, {}
    for season, ss in a.groupby("season_year"):
        tgp = team_gp.get(season, 82)
        qual = round(min(FULL_QUAL_MIN, FULL_QUAL_MIN * tgp / 82))
        qual_gp = int(tgp // 2)  # half the team's games, like the NBA's leader floors
        q = ss[(ss["min"] >= qual) & (ss.gp >= qual_gp)]
        lg = {"qual_min": qual, "qual_gp": qual_gp, "n": len(q)}
        pct = {k: {} for k in shown}
        for k in shown:
            hb = k not in LOWER_BETTER
            v = q[k].dropna()
            if len(v) >= 30:
                lg[f"{k}|dist"] = {f"p{p}": round(float(v.quantile(p / 100)), STATS[k][0])
                                   for p in (10, 25, 50, 75, 90)}
                for e, pc in zip(q.loc[v.index, "athlete_id"], pctile(v, hb)):
                    pct[k][e] = {"all": int(pc)}
            for pos, qp in q.groupby("pos"):
                vp = qp[k].dropna()
                if len(vp) >= POOL_MIN:
                    for e, pc in zip(qp.loc[vp.index, "athlete_id"], pctile(vp, hb)):
                        pct[k].setdefault(e, {})["pos"] = int(pc)
        lg["pools"] = {p: int(n) for p, n in q.pos.value_counts().items()}
        players = {}
        for r in ss.itertuples():
            row = {"gp": int(r.gp), "min": int(r.min), "pos": r.pos,
                   "q": bool(r.min >= qual and r.gp >= qual_gp)}
            for k in shown:
                v = getattr(r, k)
                row[k] = None if pd.isna(v) else round(float(v), STATS[k][0])
                if r.athlete_id in pct[k]:
                    row[f"{k}|pct"] = pct[k][r.athlete_id]
            players[r.athlete_id] = row
        seasons[int(season)] = {"players": players}
        league[int(season)] = lg
    return {"seasons": seasons, "league": league, "lower_better": list(LOWER_BETTER),
            "stats": shown, "gate_0h": gt,
            "note": "§0h — NBA.com-definition rates rebuilt from the ESPN box; on-floor "
                    "team totals approximated by minutes share. Descriptive, not a forecast."}


def rates_phase(out: Path, counts: dict) -> None:
    pg = pd.read_parquet(MART / "player_game.parquet")
    tg = pd.read_parquet(MART / "team_game.parquet")
    g = pd.read_parquet(MART / "games.parquet")
    doc = build(pg, tg, g[g.completed], out / "advagg.json.gz")
    jwrite_gz(out / "rates.json.gz", doc)
    counts["rates_seasons"] = sorted(doc["seasons"])
    counts["rates_gate_0h"] = doc["gate_0h"].get("verdict")


def _selfcheck() -> None:
    """Accounting identities on a toy game: within one team, usage shares sum to
    1 and OREB% shares sum to the team OREB rate; all ten PIEs sum to 1."""
    import random
    rnd = random.Random(7)
    rows = []
    for team in ("1", "2"):
        for i in range(5):
            fga = rnd.randint(5, 20)
            fgm, tpa = rnd.randint(1, fga), rnd.randint(0, fga)
            rows.append({"game_id": "g", "team_id": team, "athlete_id": f"{team}{i}",
                         "position": "G", "min": 48, "fga": fga, "fgm": fgm, "tpa": tpa,
                         "tpm": min(tpa, fgm), "fta": rnd.randint(0, 8), "ftm": 0,
                         "oreb": rnd.randint(0, 4), "dreb": rnd.randint(0, 8),
                         "ast": rnd.randint(0, 9), "stl": rnd.randint(0, 3),
                         "blk": rnd.randint(0, 3), "to": rnd.randint(0, 5),
                         "pf": rnd.randint(0, 5)})
    pg = pd.DataFrame(rows)
    pg["reb"] = pg.oreb + pg.dreb
    pg["pts"] = 2 * pg.fgm + pg.tpm + pg.ftm
    tg = (pg.groupby("team_id")[["fgm", "fga", "tpm", "tpa", "ftm", "fta", "pts", "oreb", "dreb",
                                 "reb", "ast", "stl", "blk", "to"]].sum().reset_index()
          .assign(game_id="g").rename(columns={v: k for k, v in BOX.items()} | {"to": "totalTurnovers"}))
    g = pd.DataFrame({"game_id": ["g"], "season_year": [2099], "season_type": [2]})
    a = player_rates(pg, team_games(tg, pg, g))
    t1 = a[a.athlete_id.str.startswith("1")]
    o1, d2 = pg[pg.team_id == "1"].oreb.sum(), pg[pg.team_id == "2"].dreb.sum()
    assert abs(t1.usg_pct.sum() - 1) < 1e-9, t1.usg_pct.sum()
    assert abs(t1.orb_pct.sum() - o1 / (o1 + d2)) < 1e-9
    assert abs(a.pie.sum() - 1) < 1e-9, a.pie.sum()
    print("self-check OK: usage, OREB% and PIE identities hold")


if __name__ == "__main__":
    _selfcheck()
    if "--gate-b" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate_b(pd.read_parquet(MART / "player_game.parquet"),
                     pd.read_parquet(MART / "team_game.parquet"), gm[gm.completed])
        GATE_B.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        sys.exit(0)
    pgm = pd.read_parquet(MART / "player_game.parquet")
    tgm = pd.read_parquet(MART / "team_game.parquet")
    gm = pd.read_parquet(MART / "games.parquet")
    d = build(pgm, tgm, gm[gm.completed], OUT / "advagg.json.gz")
    print(json.dumps(d["gate_0h"], indent=1))
    for s, lg in d["league"].items():
        print(f"season {s}: qualifier {lg['qual_min']} min, {lg['n']} qualified, pools {lg['pools']}")
