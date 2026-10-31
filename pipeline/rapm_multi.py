"""rapm_multi.py — §2 multi-season RAPM (2022-23 → 2024-25).

    python pipeline/rapm_multi.py --seasons 2025 2024 2023

Design per the §2 pre-registration (RESULTS-HOOPS.md): possession-level ridge,
player coefficients GLOBAL across seasons, y centered WITHIN each season
(scoring environments absorbed), home-court fixed effect per row, λ grid from
the §1 amendment chosen by 5-fold game-grouped CV on team-game aggregate
margins. Reads once, then:
  - benchmark gate: r vs LUMA xpts_net season-2025 on shared players with
    >=250 possessions — bar 0.70
  - stability gate: split-half (even/odd game ids, pooled) r on players with
    >=500 possessions in both halves — bar 0.60
Writes results/rapm_multi.json + results/rapm_multi_players.csv.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

RESULTS = ROOT / "pipeline" / "results"
DERIVED = ROOT / "data" / "derived"
LAMBDA_GRID = [100, 300, 1000, 3000, 10000, 30000, 100000]


def fit_ridge(X, y, w, lam):
    W = w[:, None]
    XtW = X.T * w
    P = XtW @ X
    reg = lam * np.eye(X.shape[1])
    reg[-1, -1] = 0.0  # home-effect column: unpenalized
    beta = np.linalg.solve(P + reg, XtW @ y)
    return beta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=[2025, 2024, 2023])
    a = ap.parse_args()

    frames = []
    for season in a.seasons:
        f = DERIVED / f"rapm_rows_{season}.parquet"
        df = pd.read_parquet(f)
        df["season"] = season
        frames.append(df)
        print(f"season {season}: {len(df):,} rows")
    pr = pd.concat(frames, ignore_index=True)
    pr = pr[pr.on10.map(len) == 10].reset_index(drop=True)
    print(f"pooled: {len(pr):,} possessions")

    players = sorted({p for row in pr.on10 for p in row})
    pidx = {p: i for i, p in enumerate(players)}
    nP = len(players)
    print(f"players: {nP}")

    X = np.zeros((len(pr), nP + 1), dtype=np.float64)
    y = np.zeros(len(pr), dtype=np.float64)
    gids = pr.gid.to_numpy()
    seasons = pr.season.to_numpy()
    homes = pr.home.to_numpy()
    for rix, row in enumerate(pr.itertuples()):
        on = list(row.on10)
        homes_set = set(on[:5])
        home_flag = bool(row.home)
        for aid in on:
            is_off = (aid in homes_set) == home_flag
            X[rix, pidx[aid]] = 1.0 if is_off else -1.0
        X[rix, nP] = 1.0 if home_flag else -1.0
        y[rix] = float(row.pts)
    # per-season centering (scoring environments)
    for season in a.seasons:
        m = seasons == season
        y[m] -= y[m].mean()

    # λ by 5-fold game-grouped CV on team-game aggregate margins
    uniq = pd.unique(gids)
    folds = {g: i % 5 for i, g in enumerate(sorted(uniq))}
    f = np.array([folds[g] for g in gids])
    cv = {}
    for lam in LAMBDA_GRID:
        sse = 0.0
        for k in range(5):
            tr, te = f != k, f == k
            beta = fit_ridge(X[tr], y[tr], np.ones(tr.sum()), lam)
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

    # λ-sensitivity table + the verdict slot (criterion per §2: the amended
    # game-margin CV; sensitivity across the grid reported alongside)
    sens = {}
    half = np.array([int(g) % 2 for g in gids])
    ex = pr[["gid"]].copy()
    ex["aid"] = pr.on10
    ex["half"] = half
    ex = ex.explode("aid")
    ph = ex.groupby(["aid", "half"]).size().unstack(fill_value=0)
    sens_rows = []
    ratings = pd.DataFrame({"aid": players})
    for lam in LAMBDA_GRID:
        beta = fit_ridge(X, y, np.ones(len(y)), lam)
        ratings[f"rapm_{lam}"] = beta[:nP] * 100.0
        r_e = fit_ridge(X[half == 0], y[half == 0], np.ones((half == 0).sum()), lam)
        r_o = fit_ridge(X[half == 1], y[half == 1], np.ones((half == 1).sum()), lam)
        dfe = pd.DataFrame({"aid": players, "r_e": r_e[:nP] * 100.0})
        dfo = pd.DataFrame({"aid": players, "r_o": r_o[:nP] * 100.0})
        mg0 = dfe.merge(dfo, on="aid").merge(ph.rename(columns={0: "n_even", 1: "n_odd"}),
                                             on="aid", how="left")
        sel0 = mg0[(mg0.n_even >= 500) & (mg0.n_odd >= 500)]
        stab = float(sel0.r_e.corr(sel0.r_o)) if len(sel0) else float("nan")
        # benchmark at this λ
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

    # verdict slot: λ by the amended CV criterion
    lam_sel = min(cv, key=cv.get)
    row_sel = next(r for r in sens_rows if r["lam"] == lam_sel)
    gate_stab = "PASS" if row_sel["stability"] >= 0.60 else "FAIL"
    gate_b = "PASS" if row_sel["benchmark"] >= 0.70 else "FAIL"
    print(f"λ selected: {lam_sel} | GATE stability: {gate_stab} ({row_sel['stability']}) | "
          f"GATE benchmark: {gate_b} ({row_sel['benchmark']} on {row_sel['n_bench']} players)")

    RESULTS.mkdir(parents=True, exist_ok=True)
    ratings.to_csv(RESULTS / "rapm_multi_players.csv", index=False)
    verdict = {"seasons": a.seasons, "lambda_selected": lam_sel, "cv": cv,
               "sensitivity": sens_rows, "gate_stability": gate_stab,
               "gate_benchmark": gate_b,
               "n_possessions": int(len(pr)), "n_players": nP}
    (RESULTS / "rapm_multi.json").write_text(json.dumps(verdict, indent=2))
    print(json.dumps({k: v2 for k, v2 in verdict.items() if k != "cv"}, indent=2))


if __name__ == "__main__":
    main()
