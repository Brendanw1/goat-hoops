"""Team clutch and strength of schedule (RESULTS-HOOPS §18, descriptive block).

Clutch = the last 5:00 of the 4th or any OT with the margin <= 5 before the
play (NBA.com's definition). Clutch net = points differential per 100 clutch
possessions, possessions by the Oliver box estimate over clutch events (a box
estimate, not a possession segmentation — AGENTS rule 6). Descriptive.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART  # noqa: E402
from creation import clock_seconds  # noqa: E402


def clutch_events(p: pd.DataFrame) -> pd.Series:
    """True where the play starts in clutch time: period >= 4, <= 300 s left,
    |margin| <= 5 before the play. `p` sorted by (game_id, seq)."""
    prev = p.groupby("game_id")[["home_score", "away_score"]].shift(1).fillna(0)
    return (p.period >= 4) & (p.clock_sec <= 300) & ((prev.home_score - prev.away_score).abs() <= 5)


def team_clutch(g: pd.DataFrame) -> dict:
    """{season: {abbr: {g, w, l, min, pf, pa, net}}} over regular-season games."""
    reg = g[g.season_type == 2].astype({"game_id": str})
    p = pd.read_parquet(MART / "pbp.parquet", columns=[
        "game_id", "seq", "period", "clock_sec", "type_text", "team_id", "home_score", "away_score",
        "is_shooting", "points_attempted", "p1", "clock_display"]).astype({"game_id": str})
    p["clock_sec"] = clock_seconds(p)
    p = p[p.game_id.isin(reg.game_id)].sort_values(["game_id", "seq"]).reset_index(drop=True)
    p["clutch"] = clutch_events(p)
    prev = p.groupby("game_id")[["home_score", "away_score", "clock_sec"]].shift(1)
    p["d_home"] = (p.home_score - prev.home_score.fillna(0)).clip(lower=0)
    p["d_away"] = (p.away_score - prev.away_score.fillna(0)).clip(lower=0)
    p["dt"] = (prev.clock_sec - p.clock_sec).where(prev.clock_sec >= p.clock_sec, 0).fillna(0)
    c = p[p.clutch].merge(reg[["game_id", "season_year", "home_team_id", "home_abbr", "away_abbr",
                               "home_score", "away_score"]].rename(
        columns={"home_score": "fh", "away_score": "fa"}), on="game_id")
    c["home"] = c.team_id.astype(str) == c.home_team_id.astype(str)
    sh = c.is_shooting.fillna(False)
    tt = c.type_text.fillna("")
    c["fga"] = sh & c.points_attempted.isin([2, 3])
    c["fta"] = sh & c.points_attempted.eq(1)
    c["oreb"] = tt.eq("Offensive Rebound") & c.p1.notna()
    c["tov"] = (tt.str.contains("Turnover") & ~tt.eq("No Turnover")) | tt.eq("Traveling")
    c["poss"] = c.fga.astype(int) - c.oreb.astype(int) + c.tov.astype(int) + 0.44 * c.fta.astype(int)
    out: dict = {}
    for (season, gid), d in c.groupby(["season_year", "game_id"]):
        r = d.iloc[0]
        ph, pa_ = float(d.poss[d.home].sum()), float(d.poss[~d.home & d.team_id.notna()].sum())
        for side, abbr, pf, pa, own, opp, won in (
                ("h", r.home_abbr, d.d_home.sum(), d.d_away.sum(), ph, pa_, r.fh > r.fa),
                ("a", r.away_abbr, d.d_away.sum(), d.d_home.sum(), pa_, ph, r.fa > r.fh)):
            t = out.setdefault(int(season), {}).setdefault(abbr, {"g": 0, "w": 0, "l": 0, "sec": 0.0,
                                                                    "pf": 0.0, "pa": 0.0, "poss": 0.0})
            t["g"] += 1
            t["w" if won else "l"] += 1
            t["sec"] += float(d.dt.sum())
            t["pf"] += float(pf)
            t["pa"] += float(pa)
            t["poss"] += 0.5 * (own + opp)
    for teams in out.values():
        for t in teams.values():
            t["min"] = round(t.pop("sec") / 60, 1)
            poss = t.pop("poss")
            t["net"] = round(100 * (t["pf"] - t["pa"]) / poss, 1) if poss > 0 else None
            t["pf"], t["pa"] = int(t["pf"]), int(t["pa"])
    return out


def _selfcheck() -> None:
    p = pd.DataFrame({"game_id": ["a"] * 4, "period": [4, 4, 4, 3], "clock_sec": [400, 290, 100, 100],
                      "home_score": [100, 100, 108, 0], "away_score": [96, 96, 100, 0]})
    # 400 s left: not yet; 290 s, up 4 before: clutch; 100 s, up 4 before the 8-0 run: clutch; Q3: no
    assert list(clutch_events(p)) == [False, True, True, False], list(clutch_events(p))


if __name__ == "__main__":
    _selfcheck()
    print("selfcheck ok")
