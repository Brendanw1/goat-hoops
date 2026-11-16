"""§17 — regressed percentiles: per-stat shrinkage toward the league mean, with
k (in minutes) from odd/even split-half reliability on site 2025, gated on
held-out site 2026 first half -> second half (RESULTS-HOOPS §17).

    python pipeline/shrink.py --gate   # fit k, run the gate, write SHRINK
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART  # noqa: E402

SHRINK = Path(__file__).resolve().parents[1] / "data" / "derived" / "shrink_17.json"
STATS = ["ts_pct", "efg_pct", "ftr", "tpar", "usg_pct", "ast_pct", "ast_to", "to_ratio", "orb_pct",
         "drb_pct", "reb_pct", "stl_pct", "blk_pct", "rim_rate", "mid_rate", "c3_rate", "rim_fg", "mid_fg",
         "c3_fg", "ab3_fg", "pct_unast", "pullup_rate", "pullup_efg", "unast36", "unast3_36", "ast_pts36",
         "ast3_36", "ast_rim36", "badpass36", "lostball36", "off_load", "bpm"]


def regress(x, mins, k: float, mu: float):
    """(min·x + k·μ) / (min + k)."""
    return (mins * x + k * mu) / (mins + k)


def wmean(x: pd.Series, w: pd.Series) -> float:
    ok = x.notna()
    return float((x[ok] * w[ok]).sum() / w[ok].sum())


def player_games(pg: pd.DataFrame, g: pd.DataFrame, season: int) -> pd.DataFrame:
    gs = g.loc[(g.season_type == 2) & (g.season_year == season), ["game_id", "date_et"]].astype({"game_id": str})
    p = pg[pg.pts.notna() & (pg["min"] > 0)].astype({"game_id": str, "athlete_id": str})
    return p.merge(gs, on="game_id")[["game_id", "athlete_id", "date_et", "min"]]


def fit_k(pg, tg, g) -> dict:
    """k = m·(1 − r)/r from odd/even games (date order) on site 2025."""
    from rates import season_table
    pgs = player_games(pg, g, 2025).sort_values(["athlete_id", "date_et", "game_id"])
    pgs["half"] = pgs.groupby("athlete_id").cumcount() % 2
    t = {h: season_table(pg, tg, g, pgs[pgs.half == h]).query("season_year == 2025").set_index("athlete_id")
         for h in (0, 1)}
    tot = pgs.groupby("athlete_id")["min"].sum()
    ids = tot[tot >= 500].index.intersection(t[0].index).intersection(t[1].index)
    m = float(((t[0].loc[ids, "min"] + t[1].loc[ids, "min"]) / 2).median())
    out = {}
    for s in STATS:
        a, b = t[0].loc[ids, s], t[1].loc[ids, s]
        ok = a.notna() & b.notna()
        r = float(np.corrcoef(a[ok], b[ok])[0, 1])
        out[s] = {"r_half": round(r, 4), "n": int(ok.sum()), "m_half": round(m, 1),
                  "k": round(m * (1 - r) / r, 1) if r > 0 else None}
    return out


def gate(pg, tg, g, ks: dict) -> dict:
    """Held-out: site 2026 split at the league's median game date."""
    from rates import season_table
    pgs = player_games(pg, g, 2026)
    d = pgs.drop_duplicates("game_id").date_et.astype(str).sort_values().to_numpy()
    cut = d[len(d) // 2]  # the league's median game date (string ISO dates sort correctly)
    pgs = pgs.assign(date_et=pgs.date_et.astype(str))
    t = {h: season_table(pg, tg, g, pgs[(pgs.date_et <= cut) if h == 0 else (pgs.date_et > cut)])
         .query("season_year == 2026").set_index("athlete_id") for h in (0, 1)}
    ids = t[0].index.intersection(t[1].index)
    ids = ids[(t[0].loc[ids, "min"] >= 300) & (t[1].loc[ids, "min"] >= 300)]
    first, second = t[0].loc[ids], t[1].loc[ids]
    res, red = {}, []
    for s in STATS:
        k = ks[s]["k"]
        if k is None:
            res[s] = {"pass": False, "note": "r <= 0, not regressed"}
            continue
        ok = first[s].notna() & second[s].notna()
        mu = wmean(first.loc[ok, s], first.loc[ok, "min"])
        x, y, mins = first.loc[ok, s], second.loc[ok, s], first.loc[ok, "min"]
        mse_raw = float(((x - y) ** 2).mean())
        mse_reg = float(((regress(x, mins, k, mu) - y) ** 2).mean())
        rr = 1 - mse_reg / mse_raw
        red.append(rr)
        res[s] = {"n": int(ok.sum()), "mse_raw": mse_raw, "mse_reg": mse_reg,
                  "reduction": round(rr, 4), "pass": bool(mse_reg < mse_raw)}
    share = sum(v["pass"] for v in res.values()) / len(STATS)
    med = float(np.median(red)) if red else 0.0
    return {"cut_date": str(cut)[:10], "players": int(len(ids)), "stats": res,
            "share_pass": round(share, 4), "median_reduction": round(med, 4),
            "pass": bool(share >= 0.80 and med >= 0.05)}


# §17-b: exposure column per stat (attempt stats); new stats with their exposure
EXPO = {"ts_pct": "tsa", "efg_pct": "fga", "ftr": "fga", "tpar": "fga", "rim_rate": "fga_sh",
        "mid_rate": "fga_sh", "c3_rate": "fga_sh", "pullup_rate": "fga_sh", "rim_fg": "rim_fga",
        "mid_fg": "mid_fga", "c3_fg": "c3_fga", "ab3_fg": "ab3_fga", "pullup_efg": "pu_fga",
        "pct_unast": "fgm_sh"}
NEW = {"fdrawn36": "min", "andone36": "min", "obpm": "min", "dbpm": "min",
       "putback_rate": "oreb_ev", "xefg": "sq_fga", "smk": "sq_fga"}
SHRINK_B = SHRINK.with_name("shrink_17b.json")


def add_expo(t: pd.DataFrame) -> pd.DataFrame:
    zf = sum(t[f"{z}_fgm"] for z in ("rim", "paint", "mid", "c3", "ab3"))
    return t.copy().assign(tsa=t.fga + 0.44 * t.fta, fgm_sh=zf)


def table_b(pg, tg, g, keep, sv, season):
    from rates import season_table
    from xefg import player_xefg
    t = season_table(pg, tg, g, keep).query(f"season_year == {season}")
    t = t.merge(player_xefg(sv=sv, keep=keep).query(f"season_year == {season}"),
                on=["season_year", "athlete_id"], how="left")
    return add_expo(t).set_index("athlete_id")


def gate_b(pg, tg, g, ks17: dict) -> dict:
    """§17-b: k in attempts from 2025 odd/even; held-out 2026 halves (the §17 split)."""
    from xefg import shot_values
    sv = shot_values(g)
    pgs = player_games(pg, g, 2025).sort_values(["athlete_id", "date_et", "game_id"])
    pgs["half"] = pgs.groupby("athlete_id").cumcount() % 2
    t = {h: table_b(pg, tg, g, pgs[pgs.half == h], sv, 2025) for h in (0, 1)}
    tot = pgs.groupby("athlete_id")["min"].sum()
    ids = tot[tot >= 500].index.intersection(t[0].index).intersection(t[1].index)
    stats = {**{s: e for s, e in EXPO.items()}, **NEW}
    ks = {}
    for s, e in stats.items():
        a, b = t[0].loc[ids, s], t[1].loc[ids, s]
        ok = a.notna() & b.notna()
        r = float(np.corrcoef(a[ok], b[ok])[0, 1])
        m = float(((t[0].loc[ids, e] + t[1].loc[ids, e]) / 2)[ok].median())
        ks[s] = {"expo": e, "r_half": round(r, 4), "m_half": round(m, 1),
                 "k": round(m * (1 - r) / r, 1) if r > 0 else None}
    p26 = player_games(pg, g, 2026)
    d = p26.drop_duplicates("game_id").date_et.astype(str).sort_values().to_numpy()
    cut = d[len(d) // 2]
    p26 = p26.assign(date_et=p26.date_et.astype(str))
    h = {i: table_b(pg, tg, g, p26[(p26.date_et <= cut) if i == 0 else (p26.date_et > cut)], sv, 2026)
         for i in (0, 1)}
    ids = h[0].index.intersection(h[1].index)
    ids = ids[(h[0].loc[ids, "min"] >= 300) & (h[1].loc[ids, "min"] >= 300)]
    first, second = h[0].loc[ids], h[1].loc[ids]
    res = {}
    for s, e in stats.items():
        k = ks[s]["k"]
        ok = first[s].notna() & second[s].notna() & (first[e] > 0)
        x, y = first.loc[ok, s], second.loc[ok, s]
        if k is None or ok.sum() < 30:
            res[s] = {"adopt": False, "note": "r <= 0 or n < 30"}
            continue
        mu = wmean(x, first.loc[ok, e])
        mse_att = float(((regress(x, first.loc[ok, e], k, mu) - y) ** 2).mean())
        mse_raw = float(((x - y) ** 2).mean())
        row = {"n": int(ok.sum()), "mse_raw": mse_raw, "mse_new": mse_att}
        if s in EXPO:  # vs the §17 minutes exposure
            k17 = ks17[s]["k"]
            mu17 = wmean(x, first.loc[ok, "min"])
            mse_min = float(((regress(x, first.loc[ok, "min"], k17, mu17) - y) ** 2).mean())
            row |= {"mse_min": mse_min, "adopt": bool(mse_att < mse_min and mse_att < mse_raw),
                    "vs_min": round(1 - mse_att / mse_min, 4)}
        else:
            row |= {"adopt": bool(mse_att < mse_raw), "vs_raw": round(1 - mse_att / mse_raw, 4)}
        res[s] = row
    return {"k": ks, "gate": {"cut_date": str(cut)[:10], "players": int(len(ids)), "stats": res}}


def _selfcheck() -> None:
    assert regress(0.6, 0, 500, 0.55) == 0.55 and regress(0.6, 1e9, 500, 0.55) > 0.5999
    assert abs(regress(0.6, 500, 500, 0.5) - 0.55) < 1e-12


if __name__ == "__main__":
    _selfcheck()
    if "--gate" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        gm = gm[gm.completed]
        pg, tg = pd.read_parquet(MART / "player_game.parquet"), pd.read_parquet(MART / "team_game.parquet")
        ks = fit_k(pg, tg, gm)
        res = {"k": ks, "gate": gate(pg, tg, gm, ks), "ran": pd.Timestamp.now().strftime("%Y-%m-%d")}
        SHRINK.write_text(json.dumps(res, indent=1))
        print(json.dumps({"k": {s: v["k"] for s, v in ks.items()},
                          **{k: v for k, v in res["gate"].items() if k != "stats"},
                          "per_stat": {s: v.get("reduction") for s, v in res["gate"]["stats"].items()}}, indent=1))
    elif "--gate-b" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        gm = gm[gm.completed]
        pg, tg = pd.read_parquet(MART / "player_game.parquet"), pd.read_parquet(MART / "team_game.parquet")
        res = gate_b(pg, tg, gm, json.loads(SHRINK.read_text())["k"])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        SHRINK_B.write_text(json.dumps(res, indent=1))
        print(json.dumps({s: {**{k: v for k, v in r.items() if k in ("adopt", "vs_min", "vs_raw", "n")},
                              "k": res["k"][s]["k"], "expo": res["k"][s]["expo"]}
                          for s, r in res["gate"]["stats"].items()}, indent=0))
    else:
        print("selfcheck ok")
