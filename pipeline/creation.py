"""§0i — shot creation, zones and playmaking from ESPN PBP (RESULTS-HOOPS §0i).

Per (season_year, athlete_id), regular season: zone attempts/makes and how
many makes were assisted, ESPN shot-type mix, assists by the receiver's zone,
turnover type split, and box milestones. `features()` feeds rates.build;
`--gate` runs Gate A (zones vs BDL shooting_by_zone) and Gate B (assisted
share vs BDL full-game rows) offline and writes GATE. Fail closed: a stat
whose gate is missing or failed never reaches the site.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from hoops_export import BDL, MART  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "data" / "derived" / "gate_creation_0i.json"
ZONES = ("rim", "paint", "mid", "c3", "ab3")
# exclusive, first match wins (a "Running Pullup" is a pull-up; a tip is a putback)
TYPES = (("putback", "Putback|Tip"), ("alleyoop", "Alley Oop"), ("cutting", "Cutting"),
         ("driving", "Driving"), ("stepback", "Step Back"), ("pullup", "Pullup"))


def zone(x, y, pa) -> np.ndarray:
    """§0i zones in the mart frame (rim at (25, 1)); 3PA by points_attempted."""
    d = np.hypot(x - 25, y - 1)
    return np.select(
        [(pa == 3) & (y <= 9.75), pa == 3, d <= 4, (abs(x - 25) <= 8) & (y <= 14.75)],
        ["c3", "ab3", "rim", "paint"], "mid")


def shot_type(t: pd.Series) -> np.ndarray:
    t = t.fillna("")
    return np.select([t.str.contains(p) for _, p in TYPES], [k for k, _ in TYPES], "other")


def load_shots(g: pd.DataFrame) -> pd.DataFrame:
    """Regular-season field-goal attempts with zone, type and assister."""
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    s = pd.read_parquet(MART / "shots.parquet",
                        columns=["game_id", "play_id", "shooter_id", "x", "y", "made",
                                 "points_made", "points_attempted", "is_ft", "shot_type"])
    s = s[~s.is_ft.astype(bool)].astype({"game_id": str}).merge(reg, on="game_id")
    # from 2025-26 the box no longer counts end-of-period heaves as FGA; ESPN labels them
    s = s[~s.shot_type.str.contains("Heave", na=False)]
    p = pd.read_parquet(MART / "pbp.parquet", columns=["play_id", "p2"])
    s = s.merge(p, on="play_id", how="left")
    s["made"] = s.made.astype(bool)
    s["zone"] = zone(s.x.to_numpy(float), s.y.to_numpy(float), s.points_attempted.to_numpy())
    s["type"] = shot_type(s.shot_type)
    s["assister"] = s.p2.where(s.made)  # p2 on a miss is the blocker
    s["shooter_id"] = s.shooter_id.astype("Int64").astype(str)
    s["assister"] = s.assister.astype("Int64").astype(str).replace("<NA>", None)
    return s


TRIP = r"^Free Throw - 1 of [23]$"  # §0h-c: and-ones, technicals, flagrants, clear paths are not trips


def clock_seconds(p: pd.DataFrame) -> pd.Series:
    """Seconds left in the period. The mart parses only "M:SS"; under a minute
    ESPN shows "SS.T" and `clock_sec` comes back null, so fill it from the display."""
    sub = pd.to_numeric(p.clock_display.where(~p.clock_display.astype(str).str.contains(":")), errors="coerce")
    return p.clock_sec.fillna(sub)


FOUL_TRIP = r"^Free Throw - (?:Flagrant |Clear Path )?1 of ([123])$"  # §18: a trip started = a foul drawn


def pbp_flags(g: pd.DataFrame) -> pd.DataFrame:
    """Regular-season PBP rows credited to p1, flagged by turnover type, FT trip
    (§0h-c), foul drawn / and-one / implied FTA (§18) and putback FGA."""
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    p = pd.read_parquet(MART / "pbp.parquet", columns=["game_id", "seq", "period", "clock_sec", "clock_display",
                                                       "type_text", "p1", "is_shooting", "is_scoring",
                                                       "points_attempted"])
    p = p.astype({"game_id": str}).merge(reg, on="game_id")
    p["clock_sec"] = clock_seconds(p)
    p = p[p.p1.notna()].sort_values(["game_id", "seq"])
    p["athlete_id"] = p.p1.astype("Int64").astype(str)
    p["badpass"] = p.type_text.str.contains("Bad Pass", na=False)
    p["lostball"] = p.type_text.str.contains("Lost Ball", na=False)
    p["trips"] = p.type_text.str.match(TRIP, na=False)
    n = p.type_text.str.extract(FOUL_TRIP, expand=False)
    p["fdrawn"] = n.notna()
    p["tech_fta"] = p.type_text.eq("Free Throw - Technical")
    p["fta_impl"] = n.astype(float).fillna(0) + p.tech_fta
    fg = p.is_shooting.fillna(False) & p.points_attempted.isin([2, 3])
    key = ["game_id", "period", "clock_sec", "athlete_id"]
    made = p.loc[fg & p.is_scoring.fillna(False), key].drop_duplicates().assign(_m=True)
    p = p.merge(made, on=key, how="left")
    p["andone"] = p.type_text.eq("Free Throw - 1 of 1") & p._m.fillna(False).astype(bool)
    # putback: the next shot event after an offensive rebound is the rebounder's own,
    # same period, within 3 s of game clock
    fg = p.is_shooting.fillna(False) & p.points_attempted.isin([2, 3])
    oreb = p.type_text.eq("Offensive Rebound")
    ev = p[fg | oreb]
    nxt = ev.groupby("game_id")[["athlete_id", "period", "clock_sec"]].shift(-1)
    nfg = (fg[ev.index]).groupby(ev.game_id).shift(-1).fillna(False).astype(bool)
    pb = oreb[ev.index] & nfg & nxt.athlete_id.eq(ev.athlete_id) & nxt.period.eq(ev.period) \
        & (ev.clock_sec - nxt.clock_sec).between(0, 3)
    p["oreb_ev"] = oreb
    p["putback"] = False
    p.loc[pb[pb].index, "putback"] = True
    return p.drop(columns="_m")


FLAGS = ["badpass", "lostball", "trips", "fdrawn", "andone", "fta_impl", "tech_fta", "oreb_ev", "putback"]


def turnovers(t: pd.DataFrame) -> pd.DataFrame:
    return t.groupby(["season_year", "athlete_id"])[FLAGS].sum().reset_index()


def gmsc(pg: pd.DataFrame) -> pd.Series:
    """Hollinger Game Score."""
    return (pg.pts + 0.4 * pg.fgm - 0.7 * pg.fga - 0.4 * (pg.fta - pg.ftm) + 0.7 * pg.oreb
            + 0.3 * pg.dreb + pg.stl + 0.7 * pg.ast + 0.7 * pg.blk - 0.4 * pg.pf - pg["to"])


def milestones(pg: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    p = pg[pg.pts.notna() & (pg["min"] > 0)].astype({"game_id": str, "athlete_id": str}).merge(reg, on="game_id")
    tens = (p[["pts", "reb", "ast", "stl", "blk"]] >= 10).sum(axis=1)
    p = p.assign(gmsc=gmsc(p), g30=p.pts >= 30, g40=p.pts >= 40, g50=p.pts >= 50,
                 dd=tens >= 2, td=tens >= 3)
    a = p.groupby(["season_year", "athlete_id"]).agg(
        gmsc=("gmsc", "mean"), g30=("g30", "sum"), g40=("g40", "sum"), g50=("g50", "sum"),
        dd=("dd", "sum"), td=("td", "sum"))
    return a.reset_index()


def counts(s: pd.DataFrame, sa: pd.DataFrame | None = None) -> pd.DataFrame:
    """Shooter-side counts from `s`, assister-side from `sa` (default `s`)."""
    k = ["season_year", "shooter_id"]
    s = s.assign(ast=s.made & s.assister.notna(), tp=s.made & (s.points_attempted == 3))
    out = []
    for z in ZONES:
        sz = s[s.zone == z].groupby(k).agg(**{f"{z}_fga": ("made", "size"), f"{z}_fgm": ("made", "sum"),
                                              f"{z}_ast": ("ast", "sum")})
        out.append(sz)
    for t, _ in (*TYPES, ("other", "")):
        st = s[s.type == t].groupby(k).agg(**{f"t_{t}_fga": ("made", "size"), f"t_{t}_fgm": ("made", "sum"),
                                              f"t_{t}_tpm": ("tp", "sum")})
        out.append(st)
    a = pd.concat(out, axis=1).fillna(0).astype(int)
    a.index = a.index.set_names(["season_year", "athlete_id"])
    # assister side: who they found, where, for how much
    m = (s if sa is None else sa)
    m = m[m.assister.notna()]
    by = m.assign(r3=m.points_made == 3, rrim=m.zone == "rim").groupby(["season_year", "assister"]).agg(
        a_n=("made", "size"), a_3=("r3", "sum"), a_rim=("rrim", "sum"))
    by.index = by.index.set_names(["season_year", "athlete_id"])
    return a.join(by, how="outer").fillna(0).astype(int).reset_index()


def features(pg: pd.DataFrame, g: pd.DataFrame, keep: pd.DataFrame | None = None) -> pd.DataFrame:
    """Counts + derived §0i stats per (season_year, athlete_id), regular season.
    `keep` (game_id, athlete_id) restricts every side to those player-games (§17 splits)."""
    s, t = load_shots(g), pbp_flags(g)
    sa = s
    if keep is not None:
        k = keep[["game_id", "athlete_id"]].astype(str).drop_duplicates()
        sa = s.merge(k.rename(columns={"athlete_id": "assister"}), on=["game_id", "assister"])
        s = s.merge(k.rename(columns={"athlete_id": "shooter_id"}), on=["game_id", "shooter_id"])
        t = t.merge(k, on=["game_id", "athlete_id"])
        pg = pg.astype({"game_id": str, "athlete_id": str}).merge(k, on=["game_id", "athlete_id"])
    c = counts(s, sa).merge(turnovers(t), on=["season_year", "athlete_id"], how="outer")
    c = c.merge(milestones(pg, g), on=["season_year", "athlete_id"], how="outer")
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    mins = pg.astype({"game_id": str, "athlete_id": str}).merge(reg, on="game_id") \
        .groupby(["season_year", "athlete_id"])["min"].sum().rename("mins")
    c = c.merge(mins.reset_index(), on=["season_year", "athlete_id"], how="left")
    n = [x for x in c.columns if x not in ("season_year", "athlete_id", "gmsc", "mins")]
    c[n] = c[n].fillna(0)
    fga = sum(c[f"{z}_fga"] for z in ZONES)
    fgm = sum(c[f"{z}_fgm"] for z in ZONES)
    ast = sum(c[f"{z}_ast"] for z in ZONES)
    per36 = 36 / c.mins.where(c.mins > 0)
    div = lambda a, b: a / b.where(b > 0)  # noqa: E731
    pu_fga = c.t_pullup_fga + c.t_stepback_fga
    pu_fgm = c.t_pullup_fgm + c.t_stepback_fgm
    pu_tpm = c.t_pullup_tpm + c.t_stepback_tpm
    tpm_un = c.c3_fgm + c.ab3_fgm - c.c3_ast - c.ab3_ast
    return c.assign(
        fga_sh=fga,
        rim_rate=div(c.rim_fga, fga), mid_rate=div(c.mid_fga, fga), c3_rate=div(c.c3_fga, fga),
        rim_fg=div(c.rim_fgm, c.rim_fga), mid_fg=div(c.mid_fgm, c.mid_fga),
        c3_fg=div(c.c3_fgm, c.c3_fga), ab3_fg=div(c.ab3_fgm, c.ab3_fga),
        pct_unast=div(fgm - ast, fgm), unast36=(fgm - ast) * per36, unast3_36=tpm_un * per36,
        ast_pts36=(2 * (c.a_n - c.a_3) + 3 * c.a_3) * per36, ast3_36=c.a_3 * per36,
        ast_rim36=c.a_rim * per36,
        pullup_rate=div(pu_fga, fga), pullup_efg=div(pu_fgm + 0.5 * pu_tpm, pu_fga),
        badpass36=c.badpass * per36, lostball36=c.lostball * per36,
        fdrawn36=c.fdrawn * per36, andone36=c.andone * per36, andones=c.andone,
        putback_rate=div(c.putback, c.oreb_ev),
    )


# ---------------------------------------------------------------- gates (offline)

BDL_ZONE = {"rim": ["restricted_area"], "paint": ["in_the_paint_(non-ra)"], "mid": ["mid-range"],
            "c3": ["left_corner_3", "right_corner_3"], "ab3": ["above_the_break_3"]}


def gate_a(f: pd.DataFrame, pg: pd.DataFrame, g: pd.DataFrame) -> dict:
    from hoops_export import norm_name
    z = pd.read_parquet(BDL / "seasavgs_2024_shooting_by_zone.parquet")
    z = z[(z.season == 2024) & (z.season_type == "regular")]
    b = pd.read_parquet(BDL / "seasavgs_2024_general_base.parquet")
    b = b[b.season_type == "regular"][["player.id", "stats.gp"]]
    z = z.merge(b, on="player.id")
    z["nm"] = [norm_name(f"{a} {c}") for a, c in zip(z["player.first_name"], z["player.last_name"])]
    z = z[~z.nm.duplicated(keep=False)]
    names = pg.astype({"athlete_id": str}).groupby("athlete_id").name.last()
    ours = f[(f.season_year == 2025) & (f.mins >= 500)].copy()
    ours["nm"] = ours.athlete_id.map(names).map(norm_name)
    ours = ours[~ours.nm.duplicated(keep=False)]
    gp = pg.astype({"game_id": str, "athlete_id": str}).merge(
        g.loc[(g.season_type == 2) & (g.season_year == 2025), ["game_id"]].astype(str), on="game_id")
    gp = gp[gp["min"] > 0].groupby("athlete_id").size().rename("gp_e")
    ours = ours.merge(gp, left_on="athlete_id", right_index=True)
    j = ours.merge(z, on="nm")
    res = {"n_players": int(len(j)), "zones": {}}
    tot_o = sum(ours[f"{k}_fga"].sum() for k in ZONES)
    tot_t = sum((z[f"stats.{c}_fga"] * z["stats.gp"]).sum() for k in ZONES for c in BDL_ZONE[k])
    ok = True
    for k in ZONES:
        t_fga = sum(j[f"stats.{c}_fga"] for c in BDL_ZONE[k])
        o_fga = j[f"{k}_fga"] / j.gp_e
        r = float(np.corrcoef(o_fga, t_fga)[0, 1])
        lt_fga = sum((z[f"stats.{c}_fga"] * z["stats.gp"]).sum() for c in BDL_ZONE[k])
        lt_fgm = sum((z[f"stats.{c}_fgm"] * z["stats.gp"]).sum() for c in BDL_ZONE[k])
        share_o, share_t = ours[f"{k}_fga"].sum() / tot_o, lt_fga / tot_t
        fg_o, fg_t = ours[f"{k}_fgm"].sum() / ours[f"{k}_fga"].sum(), lt_fgm / lt_fga
        p = r >= 0.95 and abs(share_o - share_t) <= 0.02 and abs(fg_o - fg_t) <= 0.02
        ok &= p
        res["zones"][k] = {"r_fga_pg": round(r, 4), "share_ours": round(share_o, 4),
                           "share_ref": round(share_t, 4), "fg_ours": round(fg_o, 4),
                           "fg_ref": round(fg_t, 4), "pass": bool(p)}
    res["pass"] = bool(ok)
    return res


def gate_b(s: pd.DataFrame, pg: pd.DataFrame, g: pd.DataFrame) -> dict:
    from rates import bdl_full_game_rows, espn_game_key
    ref = bdl_full_game_rows(["pct_assisted_fgm"])
    key_of = espn_game_key(g)
    s = s[s.season_year == 2025]
    m = s[s.made].assign(ast=lambda d: d.assister.notna()) \
        .groupby(["game_id", "shooter_id"]).agg(fgm=("made", "size"), ast=("ast", "sum")).reset_index()
    who = pg.astype({"game_id": str, "athlete_id": str, "team_id": str})[["game_id", "athlete_id", "team_id", "name"]]
    m = m.merge(who, left_on=["game_id", "shooter_id"], right_on=["game_id", "athlete_id"])
    diffs = []
    for r in m.itertuples():
        d = ref.get(key_of(r.game_id, r.team_id, r.name))
        if d is None or d.get("pct_assisted_fgm") is None or pd.isna(d.get("pct_assisted_fgm")):
            continue
        diffs.append(r.ast / r.fgm - float(d["pct_assisted_fgm"]))
    diffs = np.abs(np.array(diffs))
    rate = float((diffs <= 0.0015).mean()) if len(diffs) else 0.0
    return {"rows": int(len(diffs)), "match_rate": round(rate, 4),
            "median_abs_diff": round(float(np.median(diffs)), 4) if len(diffs) else None,
            "pass": bool(len(diffs) >= 10_000 and rate >= 0.95)}


GATE_F = ROOT / "data" / "derived" / "gate_fouls_18.json"


def gate_f(pg: pd.DataFrame, g: pd.DataFrame) -> dict:
    """§18: (a) implied FTA vs box FTA; (b) FT fouls drawn/36 vs BDL pfd/36, site 2026."""
    from hoops_export import norm_name
    t = turnovers(pbp_flags(g)).query("season_year == 2026").set_index("athlete_id")
    reg = g.loc[(g.season_type == 2) & (g.season_year == 2026), ["game_id"]].astype(str)
    p = pg[pg.pts.notna() & (pg["min"] > 0)].astype({"game_id": str, "athlete_id": str}).merge(reg)
    box = p.groupby("athlete_id").agg(fta=("fta", "sum"), mins=("min", "sum"), name=("name", "last"))
    j = box.join(t, how="inner")
    a = j[j.fta >= 100]
    within = ((a.fta_impl - a.fta).abs() / a.fta <= 0.02)
    ga = {"n": int(len(a)), "share_within_2pct": round(float(within.mean()), 4),
          "median_abs_rel": round(float(((a.fta_impl - a.fta).abs() / a.fta).median()), 4)}
    ga["pass"] = bool(ga["share_within_2pct"] >= 0.95)
    b = pd.read_parquet(BDL / "seasavgs_2025_general_base.parquet")
    b = b[(b.season == 2025) & (b.season_type == "regular")]
    b = b.assign(nm=(b["player.first_name"] + " " + b["player.last_name"]).map(norm_name),
                 bmin=b["stats.min"] * b["stats.gp"], pfd36=36 * b["stats.pfd"] / b["stats.min"])
    b = b[~b.nm.duplicated(keep=False)]
    e = j[j.mins >= 1000].assign(nm=lambda d: d.name.map(norm_name))
    e = e[~e.nm.duplicated(keep=False)]
    m = e.merge(b[b.bmin >= 1000][["nm", "pfd36"]], on="nm")
    r = float(np.corrcoef(36 * m.fdrawn / m.mins, m.pfd36)[0, 1])
    rb = float(np.corrcoef(36 * m.fta / 2 / m.mins, m.pfd36)[0, 1])
    gb = {"n": int(len(m)), "r": round(r, 4), "r_fta_half": round(rb, 4),
          "pass": bool(r >= 0.85 and r >= rb - 0.01)}
    return {"a": ga, "b": gb, "pass": bool(ga["pass"] and gb["pass"]),
            "credit": "balldontlie (NBA.com pfd) — validation reference only"}


def _selfcheck() -> None:
    x = np.array([25, 25, 25, 1, 25, 40, 12])
    y = np.array([1, 4, 12, 5, 30, 20, 10])
    pa = np.array([2, 2, 2, 3, 3, 2, 2])
    assert list(zone(x, y, pa)) == ["rim", "rim", "paint", "c3", "ab3", "mid", "mid"], zone(x, y, pa)
    t = shot_type(pd.Series(["Running Pullup Jump Shot", "Tip Dunk Shot", "Alley Oop Layup Shot",
                             "Driving Floating Jump Shot", "Jump Shot", None]))
    assert list(t) == ["pullup", "putback", "alleyoop", "driving", "other", "other"], t
    one = pd.DataFrame({"pts": [10], "fgm": [4], "fga": [8], "fta": [2], "ftm": [2], "oreb": [0],
                        "dreb": [0], "stl": [0], "ast": [0], "blk": [0], "pf": [0], "to": [0]})
    assert abs(gmsc(one)[0] - (10 + 1.6 - 5.6)) < 1e-9
    ft = pd.Series(["Free Throw - 1 of 2", "Free Throw - 1 of 1", "Free Throw - 1 of 3",
                    "Free Throw - Flagrant 1 of 2", "Free Throw - Technical", "Free Throw - 2 of 2"])
    c = clock_seconds(pd.DataFrame({"clock_sec": [65.0, None, None], "clock_display": ["1:05", "0.0", "12.4"]}))
    assert list(c) == [65.0, 0.0, 12.4], c
    assert list(ft.str.match(TRIP)) == [True, False, True, False, False, False]
    assert list(ft.str.extract(FOUL_TRIP, expand=False).fillna("-")) == ["2", "1", "3", "2", "-", "-"]


if __name__ == "__main__":
    _selfcheck()
    if "--gate" in sys.argv:
        g = pd.read_parquet(MART / "games.parquet")
        g = g[g.completed]
        pg = pd.read_parquet(MART / "player_game.parquet")
        f = features(pg, g)
        res = {"a": gate_a(f, pg, g), "b": gate_b(load_shots(g), pg, g),
               "ran": pd.Timestamp.now().strftime("%Y-%m-%d")}
        GATE.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    elif "--gate-f" in sys.argv:
        g = pd.read_parquet(MART / "games.parquet")
        res = gate_f(pd.read_parquet(MART / "player_game.parquet"), g[g.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE_F.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    else:
        print("selfcheck ok")
