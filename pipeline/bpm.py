"""§16 — Box Plus/Minus 2.0 (Daniel Myers, published coefficients) + VORP from
the ESPN box, season level per (season, team, athlete) stint. RESULTS-HOOPS §16
fixes every rule below; `--gate` runs the benchmark against LUMA offline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART  # noqa: E402

GATE = Path(__file__).resolve().parents[1] / "data" / "derived" / "gate_bpm_16.json"
LISTED = {"PG": 1, "SG": 2, "G": 1.5, "SF": 3, "F": 3.5, "PF": 4, "C": 5}
# (position-1 coef, position-5 coef); FGA/FTA interpolate by offensive role instead
COEF = {"pts_adj": (0.860, 0.860), "tpm": (0.389, 0.389), "ast": (0.580, 1.034),
        "tov": (-0.964, -0.964), "oreb": (0.613, 0.181), "dreb": (0.116, 0.181),
        "stl": (1.369, 1.008), "blk": (1.327, 0.703), "pf": (-0.367, -0.367)}
ROLE_COEF = {"fga": (-0.560, -0.780), "fta": (-0.246, -0.343)}
PTS_PER_TSA_BASE = 1.00  # reconstructed from Myers' 2017 LeBron example (§16)


def team_constrain(v: pd.Series, w: pd.Series, team: pd.Series) -> pd.Series:
    """Shift each team's values by one constant so the minutes-weighted mean of
    clip(v + c, 1, 5) is 3.0 (bisection; the clip makes it non-linear)."""
    out = pd.Series(index=v.index, dtype=float)
    for _, ix in v.groupby(team).groups.items():
        vv, ww = v.loc[ix].to_numpy(), w.loc[ix].to_numpy()
        lo, hi = -6.0, 6.0
        for _ in range(60):
            c = (lo + hi) / 2
            m = (np.clip(vv + c, 1, 5) * ww).sum() / ww.sum()
            lo, hi = (c, hi) if m < 3 else (lo, c)
        out.loc[ix] = np.clip(vv + (lo + hi) / 2, 1, 5)
    return out


def raw_bpm(x: pd.DataFrame) -> pd.Series:
    """Raw BPM from per-100 stats, position `pos`, offensive role `role`."""
    t, tr = (x.pos - 1) / 4, (x.role - 1) / 4
    raw = sum((a + (b - a) * t) * x[k] for k, (a, b) in COEF.items())
    raw += sum((a + (b - a) * tr) * x[k] for k, (a, b) in ROLE_COEF.items())
    raw += np.where(x.pos < 3, (3 - x.pos) * (-0.818 / 2), 0.0)
    return raw + (3 - x.role) * (-2.774 / 2)


def bpm_table(pg: pd.DataFrame, tgo: pd.DataFrame) -> pd.DataFrame:
    """Per (season_year, athlete_id): bpm, vorp, pos_est, role_est, min."""
    p = pg[pg.pts.notna() & (pg["min"] > 0)].rename(columns={"to": "tov"})
    p = p.astype({"game_id": str, "team_id": str, "athlete_id": str}).merge(tgo, on=["game_id", "team_id"])
    s = p["min"] / (p.tm_tmin / 5)
    p = p.assign(poss=s * 0.5 * (p.tm_poss + p.o_poss), e_reb=s * p.tm_reb, e_stl=s * p.tm_stl,
                 e_pf=s * p.tm_pf, e_ast=s * p.tm_ast, e_blk=s * p.tm_blk,
                 e_tsa=s * (p.tm_fga + 0.44 * p.tm_fta), lpos=p.position.map(LISTED).fillna(3))
    k = ["season_year", "team_id", "athlete_id"]
    box = ["min", "pts", "fga", "fta", "tpm", "ast", "tov", "oreb", "dreb", "reb", "stl", "blk", "pf"]
    st = p.groupby(k).agg(**{c: (c, "sum") for c in box + ["poss", "e_reb", "e_stl", "e_pf", "e_ast",
                                                         "e_blk", "e_tsa"]},
                          lpos=("lpos", "mean")).reset_index()
    tm = tgo.groupby(["season_year", "team_id"]).agg(
        t_pts=("tm_pts", "sum"), t_fga=("tm_fga", "sum"), t_fta=("tm_fta", "sum"), o_pts=("o_pts", "sum"),
        t_poss=("tm_poss", "sum"), o_poss=("o_poss", "sum"), t_min=("tm_tmin", "sum"),
        t_gp=("game_id", "nunique")).reset_index()
    tm["ptsa"] = tm.t_pts / (tm.t_fga + 0.44 * tm.t_fta)
    tm["net"] = 100 * (tm.t_pts - tm.o_pts) / (0.5 * (tm.t_poss + tm.o_poss))
    st = st.merge(tm, on=["season_year", "team_id"])
    st["tkey"] = st.season_year.astype(str) + "|" + st.team_id
    sh = lambda n, d: (n / d).where(d > 0, 0.0)  # noqa: E731
    pos = (2.130 + 8.668 * sh(st.reb, st.e_reb) - 2.486 * sh(st.stl, st.e_stl) + 0.992 * sh(st.pf, st.e_pf)
           - 3.536 * sh(st.ast, st.e_ast) + 1.667 * sh(st.blk, st.e_blk))
    st["pos"] = team_constrain((st["min"] * pos + 50 * st.lpos) / (st["min"] + 50), st["min"], st.tkey)
    tsa = st.fga + 0.44 * st.fta
    thr = st.pts - tsa * (st.ptsa - 0.33)
    role = 6.00 - 6.642 * sh(st.ast, st.e_ast) - 8.544 * sh(thr, 0.33 * st.e_tsa)
    st["role"] = team_constrain((st["min"] * role + 50 * 4.0) / (st["min"] + 50), st["min"], st.tkey)
    per = 100 / st.poss.where(st.poss > 0)
    x = st.assign(**{c: st[c] * per for c in ["fga", "fta", "tpm", "ast", "tov", "oreb", "dreb", "stl",
                                               "blk", "pf"]})
    x["pts_adj"] = (st.pts + tsa * (PTS_PER_TSA_BASE - st.ptsa)) * per
    st["raw"] = raw_bpm(x).fillna(0)
    st["w"] = st["min"] / (st.t_min / 5)
    adj = (st.groupby("tkey").apply(lambda d: (d.net.iat[0] - (d.raw * d.w).sum()) / d.w.sum(),
                                    include_groups=False).rename("team_adj"))
    st = st.join(adj, on="tkey")
    st["bpm"] = st.raw + st.team_adj
    st["vorp"] = (st.bpm + 2.0) * st.w * st.t_gp / 82
    out = st.assign(bm=st.bpm * st["min"], pm=st.pos * st["min"], rm=st.role * st["min"]).groupby(
        ["season_year", "athlete_id"]).agg(min=("min", "sum"), bm=("bm", "sum"), pm=("pm", "sum"),
                                           rm=("rm", "sum"), vorp=("vorp", "sum"),
                                           team_adj=("team_adj", "mean")).reset_index()
    return out.assign(bpm=out.bm / out["min"], pos_est=out.pm / out["min"], role_est=out.rm / out["min"]) \
        .drop(columns=["bm", "pm", "rm"])


def _selfcheck() -> None:
    # Myers' worked example: 2017 LeBron, position 2.3, role 1.0 -> raw BPM 15.6
    x = pd.DataFrame({"pts_adj": [30.4], "tpm": [2.2], "ast": [11.5], "tov": [5.4], "oreb": [1.7],
                      "dreb": [9.7], "stl": [1.6], "blk": [0.8], "pf": [2.4], "fga": [24.0], "fta": [9.5],
                      "pos": [2.3], "role": [1.0]})
    r = float(raw_bpm(x).iat[0])
    assert abs(r - 15.6) < 0.15, r
    # the team constraint lands the minutes-weighted mean on 3.0
    v = pd.Series([0.5, 2.0, 6.0, 4.0]); w = pd.Series([30.0, 20.0, 25.0, 25.0])
    c = team_constrain(v, w, pd.Series(["a"] * 4))
    assert abs((c * w).sum() / w.sum() - 3) < 1e-6 and c.between(1, 5).all(), c


def gate(pg: pd.DataFrame, tg: pd.DataFrame, g: pd.DataFrame) -> dict:
    """§16: benchmark vs LUMA xpts_rapm 2026 net_rapm (beat Game Score/36 by
    0.03) and year-to-year stability 2025 -> 2026."""
    from creation import gmsc
    from hoops_export import norm_name
    from rates import luma_rows, team_games
    b = bpm_table(pg, team_games(tg, pg, g))
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    p = pg[pg.pts.notna() & (pg["min"] > 0)].astype({"game_id": str, "athlete_id": str}).merge(reg)
    gs = p.assign(gs=gmsc(p)).groupby(["season_year", "athlete_id"]).gs.sum().reset_index()
    b = b.merge(gs, on=["season_year", "athlete_id"], how="left")
    two = b[b.season_year.isin([2025, 2026])].assign(bm=lambda d: d.bpm * d["min"])
    pool = two.groupby("athlete_id").agg(min=("min", "sum"), bm=("bm", "sum"), gs=("gs", "sum"))
    pool = pool[pool["min"] >= 1000].assign(bpm=lambda d: d.bm / d["min"], gs36=lambda d: 36 * d.gs / d["min"])
    names = pg.astype({"athlete_id": str}).groupby("athlete_id").name.last()
    pool["nm"] = pool.index.map(names).map(norm_name)
    pool = pool[~pool.nm.duplicated(keep=False)]
    lu = luma_rows("SELECT x.pid AS pid, p.name AS name, x.net_rapm AS net_rapm, x.poss AS poss "
                   "FROM xpts_rapm x JOIN players p ON p.pid = x.pid WHERE x.season = 2026 "
                   "AND x.poss >= 2500 ORDER BY x.pid", ["pid", "name", "net_rapm", "poss"],
                   MART.parent / "luma" / "xpts_rapm_2026_net.parquet")
    lu = lu.astype({"net_rapm": float, "poss": float})
    lu["nm"] = lu.name.map(norm_name)
    lu = lu[~lu.nm.duplicated(keep=False)]
    j = pool.merge(lu[["nm", "net_rapm"]], on="nm")
    r = float(np.corrcoef(j.bpm, j.net_rapm)[0, 1])
    rb = float(np.corrcoef(j.gs36, j.net_rapm)[0, 1])
    y = b[b["min"] >= 1000].pivot_table(index="athlete_id", columns="season_year", values="bpm")
    y = y[[2025, 2026]].dropna()
    ry = float(np.corrcoef(y[2025], y[2026])[0, 1])
    g1 = r >= 0.60 and r >= rb + 0.03
    g2 = ry >= 0.60
    return {"benchmark": {"n": int(len(j)), "luma_rows": int(len(lu)), "r": round(r, 4),
                          "r_gmsc36": round(rb, 4), "pass": bool(g1)},
            "stability": {"n": int(len(y)), "r_yoy": round(ry, 4), "pass": bool(g2)},
            "pass": bool(g1 and g2),
            "credit": "LUMA Basketball Research (xPTS-RAPM net_rapm) — validation reference only"}


if __name__ == "__main__":
    _selfcheck()
    if "--gate" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate(pd.read_parquet(MART / "player_game.parquet"), pd.read_parquet(MART / "team_game.parquet"),
                   gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    else:
        print("selfcheck ok")
