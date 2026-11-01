"""rapm_priors.py — §5: the §4 xPTS ridge with box-score prior rows.

    python pipeline/rapm_priors.py --season 2025

Design per the §5 pre-registration (RESULTS-HOOPS.md): identical to §4
(type-rich xPTS response, λ grid + game-margin CV) plus one PRIOR row per
player — response = the player's centered Game Score per possession
(prior/100 scale), predictor = +1 on that player only, weight τ = 250
(fixed). The prior rows pull each coefficient toward its box-score prior
instead of zero; they are excluded from the stability gate (which uses the
real possession rows only).

Writes results/rapm_priors.json + results/rapm_priors_players.csv.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT, MART  # noqa: E402

RESULTS = ROOT / "pipeline" / "results"
DERIVED = ROOT / "data" / "derived"
LAMBDA_GRID = [100, 300, 1000, 3000, 10000, 30000, 100000]
TAU = 250.0


def fit_ridge(X, y, w, lam):
    XtW = X.T * w
    P = XtW @ X
    reg = lam * np.eye(X.shape[1])
    reg[-1, -1] = 0.0  # home-effect column: unpenalized
    beta = np.linalg.solve(P + reg, XtW @ y)
    return beta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    a = ap.parse_args()

    pr = pd.read_parquet(DERIVED / f"rapm_xrows_{a.season}.parquet").reset_index(drop=True)
    pr = pr[pr.on10.map(len) == 10].reset_index(drop=True)
    print(f"possession rows: {len(pr):,}")

    players = sorted({p for row in pr.on10 for p in row})
    pidx = {p: i for i, p in enumerate(players)}
    nP = len(players)

    # ---- box prior: Game Score per 100 (the season's own box) --------------
    pg = pd.read_parquet(MART / "player_game.parquet")
    gg = pd.read_parquet(MART / "games.parquet")
    season_games = set(gg[(gg.season_year == a.season) & (gg.season_type == 2)].game_id)
    pg = pg[(pg.game_id.isin(season_games)) & pg.pts.notna()].copy()
    gsc = (pg.pts + 0.4 * pg.fgm - 0.7 * pg.fga - 0.4 * (pg.fta - pg.ftm)
           + 0.7 * pg.oreb + 0.3 * pg.dreb + pg.stl + 0.7 * pg.ast
           + 0.7 * pg.blk - 0.7 * pg.pf - pg["to"])
    pg["gmsc"] = gsc
    agg = pg.groupby("athlete_id").agg(gmsc=("gmsc", "sum"), min=("min", "sum"))
    agg = agg[agg["min"] >= 100]
    agg["prior100"] = 100.0 * agg.gmsc / (agg["min"] * 2.0)
    league_mean = agg.prior100.mean()
    agg["prior_c"] = agg.prior100 - league_mean
    pg_name = pg.set_index("athlete_id").name.dropna().to_dict()
    pg["aid_str"] = pg.athlete_id.astype(str)
    pc = pg.groupby("aid_str").gmsc.sum()
    # bridge ESPN athlete ids -> nba.com pids via normalized names (the
    # register is the pt endpoint's id space; validated 0 unmapped in §1)
    import re as _re
    import unicodedata as _ud
    def _norm(s):
        s = _ud.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
        s = _re.sub(r"[.'\u2019-]", " ", s.lower())
        return " ".join(t for t in s.split() if t and t not in {"jr", "sr", "ii", "iii", "iv"})
    pg["name_norm"] = pg.name.map(_norm)
    reg = pd.read_parquet(Path.home() / "Projects/vt_baseball/hoops_mart/data/pbpstats/players.parquet")
    pid_by_norm = {r.name_norm: str(r.id) for r in
                   reg.assign(name_norm=reg.name.map(_norm)).itertuples()}
    prior_of = {}
    for a, v, mn in zip(agg.index.astype(str), agg.prior_c, agg["min"]):
        nm = pg_name.get(a)
        nba = pid_by_norm.get(_norm(nm)) if nm else None
        if nba:
            prior_of[nba] = (float(v), float(mn))
    print(f"box priors: {len(prior_of)} players bridged to nba ids | league mean prior100 {league_mean:.2f}")

    # ---- design matrix -----------------------------------------------------
    X = np.zeros((len(pr) + len(players), nP + 1), dtype=np.float64)
    y = np.zeros(len(pr) + len(players), dtype=np.float64)
    w = np.ones(len(pr) + len(players), dtype=np.float64)
    gids = np.array([None] * (len(pr) + len(players)), dtype=object)
    for rix, row in enumerate(pr.itertuples()):
        on = list(row.on10)
        homes_set = set(on[:5])
        home_flag = bool(row.home)
        for aid in on:
            is_off = (aid in homes_set) == home_flag
            X[rix, pidx[aid]] = 1.0 if is_off else -1.0
        X[rix, nP] = 1.0 if home_flag else -1.0
        y[rix] = float(row.pts)
        gids[rix] = row.gid
    n_real = len(pr)
    y[:n_real] -= y[:n_real].mean()
    # prior rows
    n_prior_rows = 0
    for i, p in enumerate(players):
        if p not in prior_of:
            continue
        rix = n_real + n_prior_rows
        X[rix, pidx[p]] = 1.0
        y[rix] = prior_of[p][0] / 100.0
        w[rix] = TAU
        n_prior_rows += 1
    print(f"design: {n_real:,} possession rows + {n_prior_rows} prior rows")

    # ---- λ by 5-fold game-grouped CV (possession rows only) ----------------
    uniq = pd.unique(gids[:n_real])
    folds = {g: i % 5 for i, g in enumerate(sorted(uniq))}
    f = np.array([folds.get(g, 0) for g in gids])
    cv = {}
    for lam in LAMBDA_GRID:
        sse = 0.0
        for k in range(5):
            tr = (f != k) | (np.arange(len(y)) >= n_real)  # priors train always
            te = (f == k) & (np.arange(len(y)) < n_real)
            beta = fit_ridge(X[tr], y[tr], w[tr], lam)
            pred = X @ beta
            gg = pr.iloc[np.where(te)[0]].copy()
            gg["pred"] = pred[te]
            agg2 = gg.groupby(["gid", "team"]).agg(pred=("pred", "sum"),
                                                   actual=("pts", "sum"),
                                                   home=("home", "first")).reset_index()
            piv_p = agg2.pivot(index="gid", columns="home", values="pred")
            piv_a = agg2.pivot(index="gid", columns="home", values="actual")
            if True in piv_p.columns and False in piv_p.columns:
                sse += float(((piv_p[True] - piv_p[False]) - (piv_a[True] - piv_a[False])).pow(2).sum())
        cv[lam] = sse
        print(f"  λ={lam}: held-out game-margin SSE {cv[lam]:.0f}")

    # λ-sensitivity + gates (stability on real rows only)
    half = np.array([int(g) % 2 if g is not None else 0 for g in gids])
    ex = pd.DataFrame({"gid": gids[:n_real], "aid": pr.on10.tolist(), "half": half[:n_real]})
    ex = ex.explode("aid")
    ph = ex.groupby(["aid", "half"]).size().unstack(fill_value=0)
    sens_rows = []
    ratings = pd.DataFrame({"aid": players})
    for lam in LAMBDA_GRID:
        beta = fit_ridge(X, y, w, lam)
        ratings[f"rapm_{lam}"] = beta[:nP] * 100.0
        re_b = fit_ridge(X[half == 0], y[half == 0], w[half == 0], lam)
        ro_b = fit_ridge(X[half == 1], y[half == 1], w[half == 1], lam)
        dfe = pd.DataFrame({"aid": players, "r_e": re_b[:nP] * 100.0})
        dfo = pd.DataFrame({"aid": players, "r_o": ro_b[:nP] * 100.0})
        mg0 = dfe.merge(dfo, on="aid").merge(ph.rename(columns={0: "n_even", 1: "n_odd"}),
                                             on="aid", how="left")
        sel0 = mg0[(mg0.n_even >= 500) & (mg0.n_odd >= 500)]
        stab = float(sel0.r_e.corr(sel0.r_o)) if len(sel0) else float("nan")
        luma_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/luma/xpts_rapm_2025.parquet"
        lg = pd.read_parquet(luma_f)
        pcnt = pr.explode("on10").groupby("on10").size().rename("poss")
        tmp = pd.DataFrame({"aid": players, "r": beta[:nP] * 100.0})
        tmp["poss"] = tmp.aid.map(pcnt)
        mrg = tmp.merge(lg[["pid", "xpts_net"]], left_on="aid", right_on=lg.pid.astype(str),
                        how="inner")
        selb = mrg[mrg.poss >= 250]
        bench = float(selb.r.corr(selb.xpts_net)) if len(selb) else float("nan")
        sens_rows.append({"lam": lam, "stability": round(stab, 3), "benchmark": round(bench, 3),
                          "n_stab": int(len(sel0)), "n_bench": int(len(selb))})
        print(f"  λ={lam}: stability {stab:.3f} | LUMA benchmark {bench:.3f}")

    lam_sel = 30000  # the §4 stability-passing λ (§5 reads at the same slot)
    row_sel = next(r for r in sens_rows if r["lam"] == lam_sel)
    gate_stab = "PASS" if row_sel["stability"] >= 0.60 else "FAIL"
    gate_b = "PASS" if row_sel["benchmark"] >= 0.70 else "FAIL"
    print(f"VERDICT at λ={lam_sel}: stability {gate_stab} ({row_sel['stability']}) | "
          f"benchmark {gate_b} ({row_sel['benchmark']} on {row_sel['n_bench']} players)")

    RESULTS.mkdir(parents=True, exist_ok=True)
    ratings.to_csv(RESULTS / "rapm_priors_players.csv", index=False)
    verdict = {"season": a.season, "tau": TAU,
               "sensitivity": sens_rows, "gate_stability": gate_stab,
               "gate_benchmark": gate_b,
               "n_possessions": int(n_real), "n_players": nP,
               "n_prior_rows": int(n_prior_rows)}
    (RESULTS / "rapm_priors.json").write_text(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
