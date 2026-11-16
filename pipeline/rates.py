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
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART, OUT, jwrite, jwrite_gz  # noqa: E402

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
# §0i (creation.py): stat -> round digits, and which gate it rides
# ("a" zones, "b" assisted share, "ab" both, None descriptive, "box" §0-gated box counts;
#  "c" / "l" = §0j Box Creation / Offensive Load vs LUMA; "p" = §16 BPM / VORP;
#  "f" = §18 fouls drawn / and-ones; "x" = §20 per-shot xeFG)
CREATION = {"rim_rate": (3, "a"), "mid_rate": (3, "a"), "c3_rate": (3, "a"),
            "rim_fg": (3, "a"), "mid_fg": (3, "a"), "c3_fg": (3, "a"), "ab3_fg": (3, "a"),
            "pct_unast": (3, "b"), "unast36": (2, "b"), "unast3_36": (2, "b"),
            "ast_pts36": (1, "b"), "ast3_36": (2, "b"), "ast_rim36": (2, "ab"),
            "pullup_rate": (3, None), "pullup_efg": (3, None),
            "badpass36": (2, None), "lostball36": (2, None),
            "xefg": (3, "x"), "smk": (3, "x"),
            "fdrawn36": (2, "f"), "andone36": (2, "f"), "andones": (0, "f"), "putback_rate": (3, None),
            "box_creation": (1, "c"), "off_load": (1, "l"), "bpm": (1, "p"), "vorp": (1, "p"), "obpm": (1, "o"), "dbpm": (1, "d"),
            "gmsc": (1, "box"), "g30": (0, "box"), "g40": (0, "box"), "dd": (0, "box"), "td": (0, "box")}
# attempt floors on top of the minutes floor (full season; the live season scales them)
FLOOR = {"rim_fg": ("rim_fga", 100), "mid_fg": ("mid_fga", 60), "c3_fg": ("c3_fga", 40),
         "ab3_fg": ("ab3_fga", 100), "pullup_efg": ("pu_fga", 100),
         "putback_rate": ("oreb_ev", 75), "xefg": ("sq_fga", 200), "smk": ("sq_fga", 200)}
LOWER_BETTER = ("to_ratio", "badpass36", "lostball36")
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
    # §0j: Ben Taylor's Box Creation / Offensive Load, per 100 player possessions
    per = 100 / a.d_stl.where(a.d_stl > 0)
    ast, pts, tov = a.ast * per, a.pts * per, a.tov * per
    prof = (2 / (1 + np.exp(-a.tpa * per)) - 1) * div(a.tpm, a.tpa).fillna(0)
    bc = 0.1843 * ast + 0.0969 * (pts + tov) - 2.3021 * prof + 0.0582 * (ast * (pts + tov) * prof) - 1.1942
    a["box_creation"] = bc.clip(lower=0)
    a["off_load"] = (0.75 * (ast - 0.38 * a.box_creation) + a.fga * per + 0.44 * a.fta * per
                     + a.box_creation + tov)
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
GATE_C = GATE_B.with_name("gate_rates_0hc.json")  # §0h-c: TO ratio from FT trips, held out
GATE_J = GATE_B.with_name("gate_creation_0j.json")  # §0j: Box Creation / Offensive Load vs LUMA
LUMA_CACHE = MART.parent / "luma" / "channels_load.parquet"  # validation only; never shipped
# stat -> (balldontlie field, match tolerance) — §0h-b; ftr withdrawn (no player-level field)
GATE_B_STATS = {"ts_pct": ("true_shooting_percentage", 0.0015),
                "efg_pct": ("effective_field_goal_percentage", 0.0015),
                "to_ratio": ("turnover_ratio", 0.15),
                "ast_to": ("assist_to_turnover", 0.015), "pie": ("pie", 0.0015)}


def bdl_full_game_rows(fields, season: int = 2024) -> dict:
    """balldontlie full-game v2-advanced rows for one BDL season (2024 = site
    2025), regular season, keyed (date, ESPN abbr, normalized name). Scans every
    recovered source; period != 0 rows are single quarters and are skipped."""
    from hoops_export import BDL, BDL_ABBR2ESPN, flatten_bdl_row, norm_name
    want = {"game.id", "player.id", "game.date", "game.season", "game.postseason", "period",
            "player.first_name", "player.last_name", "team.abbreviation", *fields}
    ref, seen = {}, set()

    def take(d):
        if d.get("period") not in (0, None) or d.get("game.season") != season or d.get("game.postseason"):
            return
        k = (d["game.id"], d["player.id"])
        if k in seen:
            return
        seen.add(k)
        nm = norm_name(f"{d.get('player.first_name', '')} {d.get('player.last_name', '')}")
        ab = BDL_ABBR2ESPN.get(d.get("team.abbreviation"), d.get("team.abbreviation"))
        ref[(str(d["game.date"])[:10], ab, nm)] = d

    from paths import open_pages   # the raw dump, else its .zst (paths.py)
    for fn in ("advanced_2024.pages.jsonl", "advanced_2025.pages.jsonl", "advanced_2026.pages.jsonl"):
        f = open_pages(BDL / fn)
        if f is not None:
            with f:
                for line in f:
                    try:
                        for r in json.loads(line).get("rows", []):
                            take(flatten_bdl_row(r))
                    except json.JSONDecodeError:
                        continue
    for fn in ("advanced_2024_salvaged.parquet", "advanced_v2_checkpoints_recovered.parquet",
               "advanced_2023.parquet", "advanced_2026.parquet"):
        p = BDL / fn
        if p.exists():
            df = pd.read_parquet(p)
            df = df[[c for c in df.columns if c in want]]
            for d in df.to_dict("records"):
                take(d)
    return ref


def espn_game_key(g: pd.DataFrame):
    """(game_id, team_id, name) -> the (date, abbr, normalized name) key above."""
    from hoops_export import norm_name
    date = {str(r.game_id): str(r.date_et)[:10] for r in g.itertuples()}
    abbr = {}
    for r in g.itertuples():
        abbr[(str(r.game_id), str(int(r.home_team_id)))] = r.home_abbr
        abbr[(str(r.game_id), str(int(r.away_team_id)))] = r.away_abbr
    return lambda gid, tid, name: (date.get(str(gid)), abbr.get((str(gid), str(tid))), norm_name(name))


def gate_b(pg, tg, g) -> dict:
    """§0h-b: per-(game, player) pure-box ratios vs balldontlie's full-game rows."""
    ref = bdl_full_game_rows([f for f, _ in GATE_B_STATS.values()])
    key_of = espn_game_key(g)
    t = team_games(tg, pg, g)
    p = pg[pg.pts.notna() & (pg["min"] > 0)].rename(columns={"to": "tov"})
    p = p.astype({"game_id": str, "team_id": str}).merge(t[t.season_year == 2025], on=["game_id", "team_id"])
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
        d = ref.get(key_of(r.game_id, r.team_id, r.name))
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


def gate_c(pg, g) -> dict:
    """§0h-c: game-level TO ratio with PBP free-throw trips vs balldontlie
    season 2025 (site 2026) — held out; the trip rule was fit on 2024-25."""
    from creation import pbp_flags
    ref = bdl_full_game_rows(["turnover_ratio"], season=2025)
    key_of = espn_game_key(g)
    gs = g[(g.season_type == 2) & (g.season_year == 2026)]
    tr = pbp_flags(gs).groupby(["game_id", "athlete_id"]).trips.sum()
    p = pg.astype({"game_id": str, "athlete_id": str, "team_id": str})
    p = p[p.game_id.isin(gs.game_id.astype(str)) & (p["min"] > 0)]
    p = p.join(tr, on=["game_id", "athlete_id"]).fillna({"trips": 0})
    diffs = []
    for r in p.itertuples():
        d = ref.get(key_of(r.game_id, r.team_id, r.name))
        if d is None or d.get("turnover_ratio") is None or pd.isna(d["turnover_ratio"]):
            continue
        den = r.fga + r.trips + r.ast + r.to
        diffs.append((100 * r.to / den if den > 0 else 0.0) - float(d["turnover_ratio"]))
    diffs = pd.Series(diffs).abs()
    rate = float((diffs <= 0.15).mean()) if len(diffs) else 0.0
    return {"label": "§0h-c TO ratio, FT trips, held-out site 2026", "rows": int(len(diffs)),
            "espn_rows": int(len(p)), "match_rate": round(rate, 4),
            "median_abs_diff": round(float(diffs.median()), 3) if len(diffs) else None,
            "pass": bool(len(diffs) >= 10_000 and rate >= 0.95)}


def luma_rows(select: str, cols: list[str], cache: Path) -> pd.DataFrame:
    """Page a LUMA SELECT (must ORDER BY a unique key) through the hoops_mart
    client's 50-row cap; cached outside the repo — validation only, never shipped."""
    if cache.exists():
        return pd.read_parquet(cache)
    sys.path.insert(0, str(MART.parents[1]))
    from luma_games_pull import rpc, sql
    sid, _ = rpc(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "goat-hoops", "version": "0.1"}})
    rpc(None, "notifications/initialized", session=sid)
    rows, off = [], 0
    while True:
        page = sql(sid, f"{select} LIMIT 50 OFFSET {off}")
        rows += page
        if len(page) < 50:
            break
        off += 50
        time.sleep(2)
    df = pd.DataFrame(rows, columns=cols)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def luma_load_channels() -> pd.DataFrame:
    """LUMA `load` / `lcreation`, window 1, seasons 2025-26, gp >= 40."""
    df = luma_rows("SELECT c.season AS season, c.pid AS pid, p.name AS name, c.channel AS channel, "
                   "c.value AS value, c.gp AS gp FROM channels c JOIN players p ON p.pid = c.pid "
                   "WHERE c.channel IN ('load', 'lcreation') AND c.\"window\" = 1 "
                   "AND c.season IN (2025, 2026) AND c.gp >= 40 ORDER BY c.season, c.channel, c.pid",
                   ["season", "pid", "name", "channel", "value", "gp"], LUMA_CACHE)
    return df.astype({"season": int, "pid": int, "value": float, "gp": float})


def gate_j(pg, tg, g) -> dict:
    """§0j: Pearson r of our Box Creation / Offensive Load vs LUMA's lcreation /
    load, each season, against a naive baseline (RESULTS-HOOPS §0j)."""
    from hoops_export import norm_name
    a = player_rates(pg, team_games(tg, pg, g))
    names = pg.astype({"athlete_id": str}).groupby("athlete_id").name.last()
    a["nm"] = a.athlete_id.map(names).map(norm_name)
    per = 100 / a.d_stl.where(a.d_stl > 0)
    a["ast100"] = a.ast * per
    a["plays100"] = (a.fga + 0.44 * a.fta + a.tov + a.ast) * per
    lu = luma_load_channels()
    lu["nm"] = lu.name.map(norm_name)
    out = {"box_creation": {"ref": "lcreation", "base": "ast100", "bar": 0.85},
           "off_load": {"ref": "load", "base": "plays100", "bar": 0.90}}
    for k, spec in out.items():
        ok, by = True, {}
        for season in (2025, 2026):
            ours = a[(a.season_year == season) & (a["min"] >= 500)]
            ours = ours[~ours.nm.duplicated(keep=False)]
            ref = lu[(lu.season == season) & (lu.channel == spec["ref"])]
            ref = ref[~ref.nm.duplicated(keep=False)]
            j = ours.merge(ref[["nm", "value"]], on="nm").dropna(subset=[k, spec["base"], "value"])
            r = float(np.corrcoef(j[k], j.value)[0, 1])
            rb = float(np.corrcoef(j[spec["base"]], j.value)[0, 1])
            p = r >= spec["bar"] and r >= rb - 0.02
            ok &= p
            by[str(season)] = {"n": int(len(j)), "r": round(r, 4), "r_baseline": round(rb, 4), "pass": bool(p)}
        spec.update(seasons=by, passed=ok)
        out[k] = {**spec, "pass": bool(ok)}
        out[k].pop("passed")
    out["credit"] = "LUMA Basketball Research (Lens: load, lcreation) — validation reference only"
    return out


def season_table(pg, tg, g, keep: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every site stat per (season_year, athlete_id): §0h rates, §0i features,
    §0h-c TO ratio, §16 BPM. `keep` (game_id, athlete_id) restricts the player
    side to those player-games; team context stays whole-season (§17 splits)."""
    from bpm import bpm_table
    from creation import features
    tgo = team_games(tg, pg, g)
    sub = pg if keep is None else pg.astype({"game_id": str, "athlete_id": str}).merge(
        keep[["game_id", "athlete_id"]].astype(str), on=["game_id", "athlete_id"])
    a = player_rates(sub, tgo)
    a["athlete_id"] = a.athlete_id.astype(str)
    f = features(pg, g, keep)
    f["pu_fga"] = f.t_pullup_fga + f.t_stepback_fga
    a = a.merge(f.drop(columns=["mins"]), on=["season_year", "athlete_id"], how="left")
    # §0h-c: NBA.com counts free-throw trips; the §0h record keeps 0.44·FTA
    den = a.fga + a.trips.fillna(0) + a.ast + a.tov
    a["to_ratio"] = (100 * a.tov / den).where(den > 0)
    b = bpm_table(sub, tgo)[["season_year", "athlete_id", "bpm", "obpm", "dbpm", "vorp", "pos_est", "role_est"]]
    return a.merge(b, on=["season_year", "athlete_id"], how="left")


def build(pg, tg, g, adv_path: Path) -> dict:
    a = player_rates(pg, team_games(tg, pg, g))
    gt = gate(a, adv_path)
    gate_c_doc = json.loads(GATE_C.read_text()) if GATE_C.exists() else {}
    if gate_c_doc:
        gt["c"] = gate_c_doc
        if gate_c_doc.get("pass") and "to_ratio" in gt.get("stats", {}):
            gt["stats"]["to_ratio"]["pass_0hc"] = True
    if GATE_B.exists():  # §0h-b re-test, run offline (it scans GBs): a pass overrides a §0h miss
        gt["b"] = json.loads(GATE_B.read_text())
        for k, v in gt["b"]["stats"].items():
            if v["pass"] and k in gt["stats"]:
                gt["stats"][k]["pass_0hb"] = True
    failed = {k for k, v in gt.get("stats", {}).items()
              if not (v["pass"] or v.get("pass_0hb") or v.get("pass_0hc"))}
    shown = [k for k in STATS if k not in failed]
    status = {k: ("gated (§0h-c)" if gt["stats"][k].get("pass_0hc") and not gt["stats"][k]["pass"]
                  else "gated (§0h)") if k in gt.get("stats", {}) else "descriptive" for k in shown}
    digits = {k: v[0] for k, v in STATS.items()}
    from creation import GATE as GATE_0I, ZONES, TYPES
    g0i = json.loads(GATE_0I.read_text()) if GATE_0I.exists() else {}  # offline; fail closed
    gpass = {"a": g0i.get("a", {}).get("pass", False), "b": g0i.get("b", {}).get("pass", False)}
    g0j = json.loads(GATE_J.read_text()) if GATE_J.exists() else {}  # offline; fail closed
    gpass |= {"c": g0j.get("box_creation", {}).get("pass", False),
              "l": g0j.get("off_load", {}).get("pass", False)}
    from bpm import GATE as GATE_16
    g16 = json.loads(GATE_16.read_text()) if GATE_16.exists() else {}
    gpass["p"] = g16.get("pass", False)
    from bpm import GATE_B as GATE_16B
    g16b = json.loads(GATE_16B.read_text()) if GATE_16B.exists() else {}
    gpass["o"] = gpass["p"] and g16b.get("obpm", {}).get("pass", False)
    gpass["d"] = gpass["o"] and g16b.get("dbpm", {}).get("pass", False)  # DBPM = BPM − OBPM
    from creation import GATE_F
    g18 = json.loads(GATE_F.read_text()) if GATE_F.exists() else {}
    gpass["f"] = g18.get("pass", False)
    from xefg import GATE as GATE_20, player_xefg
    g20 = json.loads(GATE_20.read_text()) if GATE_20.exists() else {}
    gpass["x"] = g20.get("pass", False)
    for k, (dp, gk) in CREATION.items():
        if gk in (None, "box") or all(gpass[c] for c in gk):
            shown.append(k)
            digits[k] = dp
            status[k] = {None: "descriptive", "box": "box score", "c": "gated (§0j)",
                         "l": "gated (§0j)", "p": "gated (§16)", "f": "gated (§18)",
                         "x": "gated (§20)", "o": "gated (§16-b)", "d": "gated (§16-b)"}.get(gk, "gated (§0i)")
    a = season_table(pg, tg, g)
    if gpass["x"]:  # §20: production refit on completed seasons, every shot scored
        a = a.merge(player_xefg(g), on=["season_year", "athlete_id"], how="left")
    from shrink import SHRINK, regress, wmean
    sk = json.loads(SHRINK.read_text()) if SHRINK.exists() else {}  # §17, offline; fail closed
    kmap = {k: v["k"] for k, v in sk.get("k", {}).items()
            if sk.get("gate", {}).get("pass") and sk["gate"]["stats"].get(k, {}).get("pass")}
    from shrink import SHRINK_B, add_expo
    sb = json.loads(SHRINK_B.read_text()) if SHRINK_B.exists() else {}  # §17-b, offline; fail closed
    expo = {k: "min" for k in kmap}
    for k, v in sb.get("gate", {}).get("stats", {}).items():
        if v.get("adopt") and sb["k"][k]["k"]:  # attempt exposure won, or a new rate beat raw
            kmap[k], expo[k] = sb["k"][k]["k"], sb["k"][k]["expo"]
    a = add_expo(a)
    types = [t for t, _ in TYPES] + ["other"]
    team_gp = g[g.season_type == 2].groupby("season_year").size() * 2 / 30  # games per team
    seasons, league = {}, {}
    for season, ss in a.groupby("season_year"):
        tgp = team_gp.get(season, 82)
        qual = round(min(FULL_QUAL_MIN, FULL_QUAL_MIN * tgp / 82))
        qual_gp = int(tgp // 2)  # half the team's games, like the NBA's leader floors
        q = ss[(ss["min"] >= qual) & (ss.gp >= qual_gp)]
        lg = {"qual_min": qual, "qual_gp": qual_gp, "n": len(q)}
        pct = {k: {} for k in shown}
        qk = {}
        for k in shown:
            hb = k not in LOWER_BETTER
            if k in FLOOR:
                col, base = FLOOR[k]
                lg[f"{k}|floor"] = fl = round(base * min(1, tgp / 82))
                qk[k] = ss[col] >= fl
            qq = q[qk[k].loc[q.index]] if k in qk else q
            v = qq[k].dropna()
            if len(v) >= 30:
                lg[f"{k}|dist"] = {f"p{p}": round(float(v.quantile(p / 100)), digits[k])
                                   for p in (10, 25, 50, 75, 90)}
                for e, pc in zip(qq.loc[v.index, "athlete_id"], pctile(v, hb)):
                    pct[k][e] = {"all": int(pc)}
            for pos, qp in qq.groupby("pos"):
                vp = qp[k].dropna()
                if len(vp) >= POOL_MIN:
                    for e, pc in zip(qp.loc[vp.index, "athlete_id"], pctile(vp, hb)):
                        pct[k].setdefault(e, {})["pos"] = int(pc)
        lg["pools"] = {p: int(n) for p, n in q.pos.value_counts().items()}
        mus = {k: wmean(q[k], q[expo[k]]) for k in shown if k in kmap and q[k].notna().any()}
        players = {}
        for r in ss.itertuples():
            row = {"gp": int(r.gp), "min": int(r.min), "pos": r.pos,
                   "q": bool(r.min >= qual and r.gp >= qual_gp)}
            for k in shown:
                v = getattr(r, k)
                row[k] = None if pd.isna(v) else round(float(v), digits[k])
                if r.athlete_id in pct[k]:
                    row[f"{k}|pct"] = pct[k][r.athlete_id]
                if k in qk:
                    row[f"{k}|q"] = bool(qk[k].at[r.Index])
                if k in mus and row[k] is not None and pd.notna(getattr(r, expo[k])):  # §17/§17-b
                    row[f"{k}|reg"] = round(float(regress(v, getattr(r, expo[k]), kmap[k], mus[k])), digits[k])
            # shot-diet panel: [fga, fgm, assisted fgm] by zone, [fga, fgm, 3pm] by type
            if gpass["a"] and gpass["b"] and getattr(r, "fga_sh", 0) > 0:
                row["zones"] = {z: [int(getattr(r, f"{z}_fga")), int(getattr(r, f"{z}_fgm")),
                                    int(getattr(r, f"{z}_ast"))] for z in ZONES}
                row["types"] = {t: [int(getattr(r, f"t_{t}_fga")), int(getattr(r, f"t_{t}_fgm")),
                                    int(getattr(r, f"t_{t}_tpm"))] for t in types}
            players[r.athlete_id] = row
        seasons[int(season)] = {"players": players}
        league[int(season)] = lg
    return {"seasons": seasons, "league": league, "lower_better": list(LOWER_BETTER),
            "stats": shown, "status": status, "gate_0h": gt, "gate_0i": g0i, "gate_0j": g0j, "gate_16": g16, "gate_16b": g16b, "gate_18": g18, "gate_20": g20,
            "shrink_k": kmap, "shrink_expo": {k: e for k, e in expo.items() if e != "min"}, "gate_17": {x: y for x, y in sk.get("gate", {}).items() if x != "stats"},
            "note": "§0h — NBA.com-definition rates rebuilt from the ESPN box; on-floor "
                    "team totals approximated by minutes share. Descriptive, not a forecast."}


def gates_meta() -> dict:
    """Per-gate verdict, run date and credit for meta.json (AGENTS: the bake carries
    the credit and the gate date). Reads the offline gate files; missing = absent."""
    from bpm import GATE as G16
    from creation import GATE as G0I, GATE_F as G18
    from wp import GATE as G19
    from bpm import GATE_B as G16B
    from xefg import GATE as G20
    from shrink import SHRINK
    bdl, luma = "balldontlie (reference)", None
    spec = {"0h-b": (GATE_B, bdl), "0h-c": (GATE_C, "ESPN box, held out"), "0i": (G0I, bdl),
            "0j": (GATE_J, luma), "16": (G16, luma), "16-b": (G16B, luma), "19-b": (G19.with_name("gate_wp_19b.json"), "ESPN play-by-play, held out"), "17": (SHRINK, "ESPN box, held out"),
            "18": (G18, bdl), "19": (G19, "ESPN play-by-play, held out"),
            "20": (G20, "ESPN shots, held out")}
    out = {}
    for sec, (f, credit) in spec.items():
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        ok = d.get("pass", d.get("gate", {}).get("pass"))
        if ok is None:  # multi-part gates: §0h-b per stat, §0i parts a/b, §0j per model
            parts = d.get("stats") or {k: v for k, v in d.items() if isinstance(v, dict) and "pass" in v}
            ok = {k: bool(v["pass"]) for k, v in parts.items()}
        ran = d.get("ran") or pd.Timestamp.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        out[f"§{sec}"] = {"pass": ok, "ran": ran, "credit": d.get("credit") or credit}
    return out


def rates_phase(out: Path, counts: dict) -> None:
    pg = pd.read_parquet(MART / "player_game.parquet")
    tg = pd.read_parquet(MART / "team_game.parquet")
    g = pd.read_parquet(MART / "games.parquet")
    doc = build(pg, tg, g[g.completed], out / "advagg.json.gz")
    jwrite_gz(out / "rates.json.gz", doc)
    counts["rates_seasons"] = sorted(doc["seasons"])
    counts["rates_gate_0h"] = doc["gate_0h"].get("verdict")
    from clutch import team_clutch  # §18 descriptive block: team clutch per season
    jwrite(out / "team_clutch.json", team_clutch(g[g.completed]))
    from rookies import race  # descriptive: weekly cumulative Game Score per rookie
    draft = json.loads((out / "draft.json").read_text())["players"] if (out / "draft.json").exists() else {}
    jwrite(out / "rookie_race.json", race(pg, g[g.completed], draft))


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
    if "--gate-j" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate_j(pd.read_parquet(MART / "player_game.parquet"),
                     pd.read_parquet(MART / "team_game.parquet"), gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE_J.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        sys.exit()
    if "--gate-c" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate_c(pd.read_parquet(MART / "player_game.parquet"), gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE_C.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        sys.exit()
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
