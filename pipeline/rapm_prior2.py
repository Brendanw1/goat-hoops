"""rapm_prior2.py — §6: the §4 xPTS ridge with prior rows pulling toward the
§2 multi-season rating (prior-the-prior).

    python pipeline/rapm_prior2.py --season 2025

Design per the §6 pre-registration: identical to §4 (type-rich xPTS response,
λ grid + game-margin CV) plus one PRIOR row per player — response = the
player's centered §2 rating (per-100 → per-possession), predictor = +1 on
that player only, weight τ = 250 (fixed). Prior rows excluded from the
stability gate (real possession rows only).

Writes results/rapm_prior2.json + results/rapm_prior2_players.csv.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"

RESULTS = ROOT / "pipeline" / "results"
LAMBDA_GRID = [100, 300, 1000, 3000, 10000, 30000, 100000]
TAU = 250.0


def fit_ridge(X, y, w, lam):
    XtW = X.T * w
    P = XtW @ X
    reg = lam * np.eye(X.shape[1])
    reg[-1, -1] = 0.0  # home-effect column: unpenalized
    return np.linalg.solve(P + reg, XtW @ y)


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

    # ---- the prior: §2 multi-season rating at its benchmark-peak λ ---------
    prior_src = pd.read_csv(RESULTS / "rapm_multi_players.csv")
    prior_of = {str(r.aid): float(r.rapm_30000) for r in prior_src.itertuples()}
    # center over the players the response season actually rates
    shared = [p for p in players if p in prior_of]
    center = np.mean([prior_of[p] for p in shared])
    prior_of = {k: v - center for k, v in prior_of.items()}
    print(f"priors: {len(shared)} of {len(players)} players covered | centered at {center:.2f}")

    # ---- design matrix + prior rows ----------------------------------------
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
    n_prior_rows = 0
    for i, p in enumerate(players):
        if p not in prior_of:
            continue
        rix = n_real + n_prior_rows
        X[rix, pidx[p]] = 1.0
        y[rix] = prior_of[p] / 100.0
        w[rix] = TAU
        n_prior_rows += 1
    print(f"design: {n_real:,} possession rows + {n_prior_rows} prior rows")

    # ---- λ by 5-fold game-grouped CV (priors train in every fold) ----------
    uniq = sorted({g for g in gids[:n_real] if g is not None})
    folds = {g: i % 5 for i, g in enumerate(uniq)}
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
            agg = gg.groupby(["gid", "team"]).agg(pred=("pred", "sum"),
                                                  actual=("pts", "sum"),
                                                  home=("home", "first")).reset_index()
            piv_p = agg.pivot(index="gid", columns="home", values="pred")
            piv_a = agg.pivot(index="gid", columns="home", values="actual")
            if True in piv_p.columns and False in piv_p.columns:
                sse += float(((piv_p[True] - piv_p[False]) - (piv_a[True] - piv_a[False])).pow(2).sum())
        cv[lam] = sse
        print(f"  λ={lam}: held-out game-margin SSE {cv[lam]:.0f}")

    # ---- λ-sensitivity + gates ---------------------------------------------
    half = np.array([int(g) % 2 if g is not None else 0 for g in gids])
    ex = pd.DataFrame({"gid": gids[:n_real], "aid": pr.on10.tolist(), "half": half[:n_real]})
    ex = ex.explode("aid")
    ph = ex.groupby(["aid", "half"]).size().unstack(fill_value=0)
    luma_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/luma/xpts_rapm_2025.parquet"
    lg = pd.read_parquet(luma_f)
    pcnt = pr.explode("on10").groupby("on10").size().rename("poss")
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
        tmp = pd.DataFrame({"aid": players, "r": beta[:nP] * 100.0})
        tmp["poss"] = tmp.aid.map(pcnt)
        mrg = tmp.merge(lg[["pid", "xpts_net"]], left_on="aid", right_on=lg.pid.astype(str),
                        how="inner")
        selb = mrg[mrg.poss >= 250]
        bench = float(selb.r.corr(selb.xpts_net)) if len(selb) else float("nan")
        sens_rows.append({"lam": lam, "stability": round(stab, 3), "benchmark": round(bench, 3),
                          "n_stab": int(len(sel0)), "n_bench": int(len(selb))})
        print(f"  λ={lam}: stability {stab:.3f} | LUMA benchmark {bench:.3f}")

    # the verdict at the §4 stability-passing λ (the §5 convention)
    lam_sel = 30000
    row_sel = next(r for r in sens_rows if r["lam"] == lam_sel)
    gate_stab = "PASS" if row_sel["stability"] >= 0.60 else "FAIL"
    gate_b = "PASS" if row_sel["benchmark"] >= 0.70 else "FAIL"
    peak = max(sens_rows, key=lambda r: r["benchmark"])
    print(f"VERDICT at λ={lam_sel}: stability {gate_stab} ({row_sel['stability']}) | "
          f"benchmark {gate_b} ({row_sel['benchmark']} on {row_sel['n_bench']} players) | "
          f"peak benchmark {peak['benchmark']} at λ={peak['lam']}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    ratings.to_csv(RESULTS / "rapm_prior2_players.csv", index=False)
    verdict = {"season": a.season, "tau": TAU, "cv": cv, "sensitivity": sens_rows,
               "gate_stability": gate_stab, "gate_benchmark": gate_b,
               "n_possessions": int(n_real), "n_players": nP,
               "n_prior_rows": int(n_prior_rows)}
    (RESULTS / "rapm_prior2.json").write_text(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
