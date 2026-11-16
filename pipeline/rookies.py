"""Rookie race (descriptive, RESULTS-HOOPS §17-b block): per season, every
rookie's cumulative Game Score at the end of each week of the regular season.

Rookie = drafted the summer before (BDL draft bio, `draft.json`) or, from
2025-26 on, an undrafted player with no game in the ESPN spine's earlier
seasons. Game Score is Hollinger's published linear formula (creation.gmsc).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART  # noqa: E402


def rookie_ids(pg: pd.DataFrame, g: pd.DataFrame, draft: dict, season: int) -> set[str]:
    reg = g.loc[g.season_type == 2, ["game_id", "season_year"]].astype({"game_id": str})
    p = pg[(pg["min"] > 0)].astype({"game_id": str, "athlete_id": str}).merge(reg)
    first = p.groupby("athlete_id").season_year.min()
    played = set(p.loc[p.season_year == season, "athlete_id"])
    drafted = {e for e, d in draft.items() if d.get("dy") == season - 1}
    undrafted = {e for e in played if e not in draft and first.get(e) == season and season > first.min()}
    return (drafted & played) | undrafted


def race(pg: pd.DataFrame, g: pd.DataFrame, draft: dict) -> dict:
    from creation import gmsc
    reg = g.loc[g.season_type == 2, ["game_id", "season_year", "date_et"]].astype({"game_id": str})
    p = pg[pg.pts.notna() & (pg["min"] > 0)].astype({"game_id": str, "athlete_id": str}).merge(reg)
    p = p.assign(gs=gmsc(p), date=pd.to_datetime(p.date_et.astype(str)))
    out = {}
    for season, d in p.groupby("season_year"):
        ids = rookie_ids(pg, g, draft, int(season))
        r = d[d.athlete_id.isin(ids)]
        if r.empty:
            continue
        start = d.date.min()
        r = r.assign(wk=((r.date - start).dt.days // 7).astype(int))
        nw = int((d.date.max() - start).days // 7) + 1
        wk = r.pivot_table(index="athlete_id", columns="wk", values="gs", aggfunc="sum").reindex(
            columns=range(nw)).fillna(0).cumsum(axis=1)
        last = r.sort_values("date").groupby("athlete_id").last()
        out[int(season)] = {
            "start": str(start.date()), "weeks": nw,
            "players": {e: {"name": last.at[e, "name"], "team_id": str(last.at[e, "team_id"]),
                            "gp": int((r.athlete_id == e).sum()), "gs_total": round(float(wk.loc[e].iat[-1]), 1),
                            "cum": [round(float(v), 1) for v in wk.loc[e]],
                            **({"dn": draft[e].get("dn")} if e in draft and draft[e].get("dn") else {})}
                        for e in wk.index}}
    return out


def _selfcheck() -> None:
    w = pd.DataFrame({0: [2.0, 1.0], 1: [np.nan, 3.0]}).fillna(0).cumsum(axis=1)
    assert w.iloc[0].tolist() == [2.0, 2.0] and w.iloc[1].tolist() == [1.0, 4.0]


if __name__ == "__main__":
    _selfcheck()
    print("selfcheck ok")
    if "--show" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        dr = json.loads((Path(__file__).resolve().parents[1] / "data/export/web/draft.json").read_text())["players"]
        doc = race(pd.read_parquet(MART / "player_game.parquet"), gm[gm.completed], dr)
        for s, v in doc.items():
            top = sorted(v["players"].items(), key=lambda kv: -kv[1]["gs_total"])[:5]
            print(s, v["weeks"], len(v["players"]), [(x["name"], x["gs_total"]) for _, x in top])
