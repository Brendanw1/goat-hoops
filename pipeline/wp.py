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
from creation import clock_seconds, ordered  # noqa: E402

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
    p = p.merge(reg[["game_id", "season_year", "home_team_id", "away_team_id", "home_score", "away_score",
                     "neutral"]].rename(columns={"home_score": "fh", "away_score": "fa"}), on="game_id")
    p = ordered(p).reset_index(drop=True)
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
    # §19-b: a game whose last ordered state disagrees with the box final is dropped (26)
    last = p.groupby("game_id")[["home_score", "away_score", "fh", "fa"]].last()
    bad = last.index[(last.home_score != last.fh) | (last.away_score != last.fa)]
    p = p[~p.game_id.isin(bad)].copy()
    p["neutral"] = p.neutral.fillna(False).astype(int)
    p["w"] = 1 / p.groupby("game_id").seq.transform("size")
    return add_x(p)


def add_x(p: pd.DataFrame) -> pd.DataFrame:
    r = np.sqrt(p.tau)
    h = 1 - p.neutral if "neutral" in p else 1
    return p.assign(m_t=p.m / r, sq=r, s_t=p.s * r, b_t=p.b / r, h=h, sq_h=r * h)


# §19-b candidates: (features, kind); C1/C2 zero the home-court terms at neutral sites
C1 = ["m_t", "sq_h", "h", "s_t", "b_t"]
C2 = ["m", "tau", "m_t", "s", "s_t", "b", "b_t", "neutral"]
C2_MONO = [1, 0, 1, 1, 1, 1, 1, 0]


def fit_spec(p: pd.DataFrame, spec: str):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    if spec == "C0":
        return LogisticRegression(C=1e6, max_iter=1000).fit(p[FULL], p.y, sample_weight=p.w), FULL
    if spec == "C1":
        return LogisticRegression(C=1e6, max_iter=1000, fit_intercept=False).fit(
            p[C1], p.y, sample_weight=p.w), C1
    if spec == "B":
        return LogisticRegression(C=1e6, max_iter=1000).fit(p[BASE], p.y, sample_weight=p.w), BASE
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=0, monotonic_cst=C2_MONO)
    return m.fit(p[C2], p.y, sample_weight=p.w), C2


def deciles(pr, w, bins=10):
    o = np.argsort(pr, kind="stable")
    q = np.empty(len(pr), int)
    q[o] = np.minimum(((np.cumsum(w[o]) - w[o]) / w.sum() * bins).astype(int), bins - 1)
    return q


def cal_stats(pr, y, w, q):
    """(ECE, per-decile gaps) with fixed decile assignment q, equal-weight deciles."""
    d = pd.DataFrame({"p": pr * w, "y": y * w, "w": w, "q": q}).groupby("q").sum()
    gap = (d.p - d.y) / d.w
    return float((gap.abs() * d.w).sum() / d.w.sum()), gap.to_numpy()


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


def gate_b(g: pd.DataFrame) -> dict:
    """§19-b: select by 5-fold game-grouped CV on site 2026, test on site 2025, forward-check 2027."""
    from sklearn.model_selection import GroupKFold
    p = states(g)
    tr, te, fw = p[p.season_year == 2026], p[p.season_year == 2025], p[p.season_year == 2027]
    cv = {}
    for spec in ("C0", "C1", "C2"):
        oof = np.zeros(len(tr))
        for a, b in GroupKFold(5).split(tr, groups=tr.game_id):
            m, cols = fit_spec(tr.iloc[a], spec)
            oof[b] = m.predict_proba(tr.iloc[b][cols])[:, 1]
        y, w = tr.y.to_numpy(), tr.w.to_numpy()
        ece, gap = cal_stats(oof, y, w, deciles(oof, w))
        cv[spec] = {"brier": round(float(((oof - y) ** 2 * w).sum() / w.sum()), 5), "ece": round(ece, 4),
                    "max_gap": round(float(np.abs(gap).max()), 4)}
    ok = [k for k, v in cv.items() if v["max_gap"] <= 0.02]
    pick = min(ok, key=lambda k: cv[k]["brier"]) if ok else min(cv, key=lambda k: cv[k]["ece"])
    m, cols = fit_spec(tr, pick)
    mb, bcols = fit_spec(tr, "B")
    pm, pb = m.predict_proba(te[cols])[:, 1], mb.predict_proba(te[bcols])[:, 1]
    y, w, gid = te.y.to_numpy(), te.w.to_numpy(), te.game_id.to_numpy()
    q = deciles(pm, w)
    ece, gap = cal_stats(pm, y, w, q)
    per = pd.DataFrame({"g": gid, "d": ((pm - y) ** 2 - (pb - y) ** 2) * w}).groupby("g").d.sum()
    games = pd.Series(np.arange(len(te))).groupby(gid).apply(np.asarray)
    rng = np.random.default_rng(0)
    bd, bg = [], []
    for _ in range(200):
        pick_g = rng.integers(0, len(games), len(games))
        bd.append(per.iloc[pick_g].mean())
        ix = np.concatenate(games.iloc[pick_g].to_numpy())
        bg.append(cal_stats(pm[ix], y[ix], w[ix], q[ix])[1])
    lo, hi = np.percentile(bd, [2.5, 97.5])
    glo, ghi = np.percentile(np.vstack(bg), [2.5, 97.5], axis=0)
    overlap = bool(((ghi >= -0.02) & (glo <= 0.02)).all())
    brier_m = float(((pm - y) ** 2 * w).sum() / w.sum())
    brier_b = float(((pb - y) ** 2 * w).sum() / w.sum())
    # forward check (not gated): fit 2025 + 2026, score the live season
    both = p[p.season_year.isin([2025, 2026])]
    mf, fcols = fit_spec(both, pick)
    pf, yf, wf = mf.predict_proba(fw[fcols])[:, 1], fw.y.to_numpy(), fw.w.to_numpy()
    fece, fgap = cal_stats(pf, yf, wf, deciles(pf, wf))
    return {"dropped_games": int(g[g.season_type == 2].shape[0] - p.game_id.nunique()), "cv_2026": cv, "pick": pick,
            "test_2025": {"games": int(te.game_id.nunique()), "brier_model": round(brier_m, 5),
                          "brier_base": round(brier_b, 5), "ci95_diff": [round(float(lo), 5), round(float(hi), 5)],
                          "ece": round(ece, 4), "decile_gaps": np.round(gap, 4).tolist(),
                          "decile_ci_lo": np.round(glo, 4).tolist(), "decile_ci_hi": np.round(ghi, 4).tolist(),
                          "all_deciles_overlap_2pt": overlap},
            "forward_2027": {"games": int(fw.game_id.nunique()),
                             "brier": round(float(((pf - yf) ** 2 * wf).sum() / wf.sum()), 5),
                             "ece": round(fece, 4), "max_gap": round(float(np.abs(fgap).max()), 4)},
            "pass": bool(brier_m < brier_b and hi < 0 and ece <= 0.015 and overlap)}


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
    if "--gate-b" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate_b(gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE.with_name("gate_wp_19b.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    elif "--gate" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate(gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    else:
        print("selfcheck ok")
