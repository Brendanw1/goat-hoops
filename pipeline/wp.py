"""§19 — in-game home win probability and player WPA from ESPN play-by-play.
RESULTS-HOOPS §19 fixes every rule; `--gate` runs the held-out test (fit site
2025, score site 2026).

    python pipeline/wp.py --gate
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART  # noqa: E402
from creation import clock_seconds  # noqa: E402

GATE = Path(__file__).resolve().parents[1] / "data" / "derived" / "gate_wp_19.json"
BASE, FULL = ["m_t", "sq"], ["m_t", "sq", "s_t", "b_t"]


def strength(g: pd.DataFrame) -> pd.DataFrame:
    """Per (game_id, team_id): season-to-date net per 100 over prior games, shrunk n/(n+10)."""
    from rates import team_games
    tg, pg = pd.read_parquet(MART / "team_game.parquet"), pd.read_parquet(MART / "player_game.parquet")
    t = team_games(tg, pg, g).merge(g[["game_id", "date_et"]].astype({"game_id": str}), on="game_id")
    t = t.sort_values(["season_year", "team_id", "date_et", "game_id"])
    t = t.assign(diff=t.tm_pts - t.o_pts, poss=0.5 * (t.tm_poss + t.o_poss))
    grp = t.groupby(["season_year", "team_id"])
    cd, cp = grp["diff"].cumsum() - t["diff"], grp.poss.cumsum() - t.poss
    n = grp.cumcount()
    t["net_pre"] = (100 * cd / cp.where(cp > 0)).fillna(0) * n / (n + 10)
    return t[["game_id", "team_id", "net_pre"]]


def states(g: pd.DataFrame) -> pd.DataFrame:
    """One row per regular-season PBP play: features after the play, outcome, credit columns."""
    reg = g[g.season_type == 2].astype({"game_id": str, "home_team_id": str, "away_team_id": str})
    p = pd.read_parquet(MART / "pbp.parquet", columns=[
        "game_id", "seq", "period", "clock_sec", "type_text", "team_id", "home_score", "away_score",
        "is_shooting", "points_attempted", "p1", "clock_display"]).astype({"game_id": str})
    p["clock_sec"] = clock_seconds(p)
    p = p[p.clock_sec.notna()]  # one 2025-26 game ships an "H:MM:SS" display (9 rows)
    p = p.merge(reg[["game_id", "season_year", "home_team_id", "away_team_id", "home_score", "away_score"]]
                .rename(columns={"home_score": "fh", "away_score": "fa"}), on="game_id")
    p = p.sort_values(["game_id", "seq"]).reset_index(drop=True)
    p["team"] = p.team_id.astype("Int64").astype(str)
    side = np.where(p.team == p.home_team_id, 1.0, np.where(p.team == p.away_team_id, -1.0, np.nan))
    tt = p.type_text.fillna("")
    uses = p.is_shooting.fillna(False) | (tt.str.contains("Turnover") & ~tt.eq("No Turnover")) \
        | tt.eq("Traveling")
    p["use"] = np.where(uses, side, np.nan)
    nxt = p.groupby(["game_id", "period"]).use.shift(-1)
    p["b"] = nxt.groupby([p.game_id, p.period]).bfill().fillna(0)
    p["m"] = (p.home_score - p.away_score).astype(float)  # the mart fills scores on every row
    t = np.where(p.period <= 4, (4 - p.period) * 720 + p.clock_sec, p.clock_sec)
    p["tau"] = np.maximum(t, 1) / 2880
    p["elapsed"] = np.where(p.period <= 4, (p.period - 1) * 720 + 720 - p.clock_sec,
                            2880 + (p.period - 5) * 300 + 300 - p.clock_sec)
    st = strength(g)
    h = st.rename(columns={"team_id": "home_team_id", "net_pre": "sh"})
    a = st.rename(columns={"team_id": "away_team_id", "net_pre": "sa"})
    p = p.merge(h, on=["game_id", "home_team_id"], how="left").merge(a, on=["game_id", "away_team_id"], how="left")
    p["s"] = p.sh.fillna(0) - p.sa.fillna(0)
    p["side"] = side
    p["y"] = (p.fh > p.fa).astype(int)
    p["w"] = 1 / p.groupby("game_id").seq.transform("size")
    return add_x(p)


def add_x(p: pd.DataFrame) -> pd.DataFrame:
    r = np.sqrt(p.tau)
    return p.assign(m_t=p.m / r, sq=r, s_t=p.s * r, b_t=p.b / r)


def fit(p: pd.DataFrame, cols):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=1e6, max_iter=1000).fit(p[cols], p.y, sample_weight=p.w)


def wcalib(pr, y, w, bins=10) -> float:
    o = np.argsort(pr)
    cw = (np.cumsum(w[o]) - w[o]) / w.sum()  # each state binned by where its weight starts
    q = np.minimum((cw * bins).astype(int), bins - 1)
    d = pd.DataFrame({"p": pr[o] * w[o], "y": y[o] * w[o], "w": w[o], "q": q}).groupby("q").sum()
    return float(((d.p - d.y) / d.w).abs().max())


def gate(g: pd.DataFrame) -> dict:
    p = states(g)
    tr, te = p[p.season_year == 2025], p[p.season_year == 2026]
    mb, mm = fit(tr, BASE), fit(tr, FULL)
    pb, pm = mb.predict_proba(te[BASE])[:, 1], mm.predict_proba(te[FULL])[:, 1]
    y, w = te.y.to_numpy(), te.w.to_numpy()
    bb, bm = (pb - y) ** 2, (pm - y) ** 2
    per = pd.DataFrame({"g": te.game_id.to_numpy(), "d": (bm - bb) * w}).groupby("g").d.sum()
    rng = np.random.default_rng(0)
    boots = [per.iloc[rng.integers(0, len(per), len(per))].mean() for _ in range(200)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    brier_b, brier_m = float((bb * w).sum() / w.sum()), float((bm * w).sum() / w.sum())
    cal = wcalib(pm, y, w)
    return {"games_train": int(tr.game_id.nunique()), "games_test": int(te.game_id.nunique()),
            "states_test": int(len(te)), "brier_base": round(brier_b, 5), "brier_model": round(brier_m, 5),
            "ci95_diff": [round(float(lo), 5), round(float(hi), 5)], "calib_max_gap": round(cal, 4),
            "calib_base": round(wcalib(pb, y, w), 4),
            "coef": dict(zip(FULL, np.round(mm.coef_[0], 4).tolist())), "intercept": round(float(mm.intercept_[0]), 4),
            "pass": bool(brier_m < brier_b and hi < 0 and cal <= 0.02)}


def production(g: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Refit M on completed seasons; return (player WPA per season, {game_id: [[elapsed, wp‰], ...]})."""
    p = states(g)
    m = fit(p[p.season_year < p.season_year.max()], FULL)
    p["wp"] = m.predict_proba(p[FULL])[:, 1]
    pre = add_x(p.groupby("game_id").first()[["s"]].assign(m=0.0, tau=1.0, b=0.0))
    p["prev"] = p.groupby("game_id").wp.shift(1).fillna(p.game_id.map(
        pd.Series(m.predict_proba(pre[FULL])[:, 1], index=pre.index)))
    tt = p.type_text.fillna("")
    ok = p.p1.notna() & p.side.notna() & ~tt.str.contains("Substitution|Timeout")
    c = p[ok].assign(athlete_id=lambda d: d.p1.astype("Int64").astype(str), wpa=lambda d: (d.wp - d.prev) * d.side)
    wpa = c.groupby(["season_year", "athlete_id"]).wpa.sum().reset_index()
    series = {gid: [[int(e), int(round(1000 * v))] for e, v in zip(d.elapsed, d.wp)]
              for gid, d in p.groupby("game_id")}
    return wpa, series


def _selfcheck() -> None:
    p = pd.DataFrame({"m": [0.0, 10.0], "tau": [1.0, 0.25], "s": [2.0, 0.0], "b": [1.0, -1.0]})
    x = add_x(p)
    assert list(x.m_t) == [0.0, 20.0] and list(x.sq) == [1.0, 0.5] and list(x.b_t) == [1.0, -2.0]
    assert abs(wcalib(np.array([.2, .2, .8, .8]), np.array([0, 1, 1, 1]), np.ones(4), 2) - 0.3) < 1e-9


if __name__ == "__main__":
    _selfcheck()
    if "--gate" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate(gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    else:
        print("selfcheck ok")
