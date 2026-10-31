"""rapm.py — §1 RAPM: possession-level ridge from the validated stint backbone.

    python pipeline/rapm.py --season 2025 [--luma-bench]

Implements §1's fixed model (RESULTS-HOOPS.md): one row per possession,
response = points scored by the offense, predictors = ±1 for the 10 on-court
players (offense +1, defense −1) plus a home-court fixed effect, weight 1.
Ridge, λ grid {100, 300, 1000, 3000, 10000} chosen by 5-fold CV grouped by
game (within 2024-25). Reads ONCE, then:
  - benchmark gate: Pearson r vs LUMA xpts_net (season 2025) on players with
    >=250 possessions — bar 0.70
  - stability gate: split-half (even/odd game ids) r on players with >=500
    possessions in both halves — bar 0.60
Writes results/rapm_2025.json + results/rapm_2025_players.csv.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

RESULTS = ROOT / "pipeline" / "results"
DERIVED = ROOT / "data" / "derived"
# grid re-opened on the corrected response (v3 amendment): the
# original range was calibrated against the broken ESPN-attributed
# response and both gate metrics still rise at its edge
LAMBDA_GRID = [100, 300, 1000, 3000, 10000, 30000, 100000]
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[.'\u2019-]", " ", s.lower())
    return " ".join(t for t in s.split() if t and t not in SUFFIXES)


def fit_ridge(X, y, w, lam):
    """Weighted ridge with the penalty NOT on the intercept column."""
    W = w[:, None]
    XtW = X.T * w
    P = XtW @ X
    reg = lam * np.eye(X.shape[1])
    if X.shape[1]:
        reg[-1, -1] = 0.0  # home-effect column: no penalty
    beta = np.linalg.solve(P + reg, XtW @ y)
    pred = X @ beta
    sse = float(np.sum(w * (y - pred) ** 2))
    return beta, sse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    a = ap.parse_args()
    pr = pd.read_parquet(DERIVED / f"rapm_rows_{a.season}.parquet").reset_index(drop=True)
    pr = pr[pr.on10.map(len) == 10]
    print(f"possession rows: {len(pr):,}")

    players = sorted({p for row in pr.on10 for p in row})
    pidx = {p: i for i, p in enumerate(players)}
    nP = len(players)
    print(f"players: {nP}")

    # design matrix (dense is fine at this size: ~130k x ~590)
    X = np.zeros((len(pr), nP + 1), dtype=np.float64)
    y = np.zeros(len(pr), dtype=np.float64)
    home_col = np.zeros(len(pr), dtype=np.float64)
    gids = pr.gid.to_numpy()
    for rix, row in enumerate(pr.itertuples()):
        off = row.team
        home_flag = bool(row.home)
        deft = "away" if home_flag else "home"
        on = list(row.on10)
        # team membership: first 5 = home, last 5 = away by construction
        homes = set(on[:5])
        for aid in on:
            is_off = (aid in homes) == home_flag
            X[rix, pidx[aid]] = 1.0 if is_off else -1.0
        X[rix, nP] = 1.0 if home_flag else -1.0
        y[rix] = float(row.pts)
        gids[rix] = row.gid
    y = y - y.mean()  # league scoring environment absorbed; ratings per-possession

    # λ by 5-fold CV grouped by game, scored on GAME-LEVEL aggregate margins:
    # single-possession MSE is flat in λ (noise-dominated) and cannot see
    # rating quality — the v1 diagnosis. Aggregating to team-game margins
    # makes the criterion sensitive to the ratings' actual quantity.
    uniq = pd.unique(gids)
    folds = {g: i % 5 for i, g in enumerate(sorted(uniq))}
    f = np.array([folds[g] for g in gids])
    game_sides = pd.DataFrame({"g": gids, "team": pr.team.to_numpy(),
                               "home": pr.home.to_numpy(), "y": y})
    cv = {}
    for lam in LAMBDA_GRID:
        sse = 0.0
        for k in range(5):
            tr, te = f != k, f == k
            beta, _ = fit_ridge(X[tr], y[tr], np.ones(tr.sum()), lam)
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
    # MSE selectors are degenerate for this problem (v1 + v2 diagnosis: both
    # possession-level and game-margin SSE decrease monotonically to the grid
    # edge, because player effects explain little of margin variance). Produce
    # the full λ-sensitivity table as the failure diagnosis; the registered
    # verdict uses λ=300 (the moderate-shrinkage convention anchor, ~80% of
    # OLS at typical n), with every grid value reported.
    print("λ-sensitivity (diagnostic):")
    sens = {}
    for lam in LAMBDA_GRID:
        beta_l, _ = fit_ridge(X, y, np.ones(len(y)), lam)
        sens[lam] = beta_l[:nP] * 100.0
    lam_best = 300

    beta = sens[lam_best] / 100.0
    ratings = pd.DataFrame({"aid": players,
                            **{f"rapm_{lam}": sens[lam] for lam in LAMBDA_GRID}})

    # split-half stability per λ (the gate statistic across the grid)
    half = np.array([int(g) % 2 for g in gids])
    res = {}
    for tag, mask in (("even", half == 0), ("odd", half == 1)):
        for lam in LAMBDA_GRID:
            beta_h, _ = fit_ridge(X[mask], y[mask], np.ones(mask.sum()), lam)
            res.setdefault(lam, {})[tag] = pd.DataFrame(
                {"aid": players, "r": beta_h[:nP] * 100.0})
    stab_by_lam = {}
    # possession counts per player per half for the >=500 filter
    ex = pr[["gid"]].copy()
    ex["aid"] = pr.on10
    ex["half"] = half
    ex = ex.explode("aid")
    ph = ex.groupby(["aid", "half"]).size().unstack(fill_value=0)
    for lam in LAMBDA_GRID:
        mg0 = res[lam]["even"].merge(res[lam]["odd"], on="aid", suffixes=("_e", "_o"))
        mg0 = mg0.merge(ph.rename(columns={0: "n_even", 1: "n_odd"}), on="aid", how="left")
        sel0 = mg0[(mg0.n_even >= 500) & (mg0.n_odd >= 500)]
        stab_by_lam[lam] = float(sel0.r_e.corr(sel0.r_o)) if len(sel0) else float("nan")
    mg = res[300]["even"].merge(res[300]["odd"], on="aid", suffixes=("_e", "_o"))
    mg = mg.merge(ph.rename(columns={0: "n_even", 1: "n_odd"}), on="aid", how="left")
    sel = mg[(mg.n_even >= 500) & (mg.n_odd >= 500)]
    stab_r = stab_by_lam[300]
    gate_stab = "PASS" if stab_r >= 0.60 else "FAIL"
    for lam in LAMBDA_GRID:
        print(f"  λ={lam}: split-half r {stab_by_lam[lam]:.3f}")
    print(f"GATE stability (λ=300): {gate_stab} — r {stab_r:.3f} on {len(sel)} players (≥500 poss both halves)")

    # benchmark vs LUMA — direct pid join (same nba.com id space)
    bench = None
    luma_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/luma/xpts_rapm_2025.parquet"
    if luma_f.exists():
        lg = pd.read_parquet(luma_f)
        ratings["pid_int"] = ratings.aid.astype(int)
        pcnt = pr.explode("on10").groupby("on10").size().rename("poss")
        ratings["poss"] = ratings.aid.map(pcnt)
        mrg = ratings.merge(lg[["pid", "xpts_net"]], left_on="pid_int", right_on="pid", how="inner")
        sel = mrg[mrg.poss >= 250]
        bench_by_lam = {lam: float(sel[f"rapm_{lam}"].corr(sel.xpts_net)) for lam in LAMBDA_GRID}
        for lam in LAMBDA_GRID:
            print(f"  λ={lam}: LUMA benchmark r {bench_by_lam[lam]:.3f}")
        bench_r = bench_by_lam[300]
        gate_b = "PASS" if bench_r >= 0.70 else "FAIL"
        print(f"GATE LUMA benchmark (λ=300): {gate_b} — r {bench_r:.3f} on {len(sel)} shared players (≥250 poss)")
        bench = {"r": bench_r, "n": int(len(sel)), "pass": gate_b == "PASS",
                 "by_lambda": {str(k): round(v2, 3) for k, v2 in bench_by_lam.items()},
                 "stability_by_lambda": {str(k): round(v2, 3) for k, v2 in stab_by_lam.items()}}

    RESULTS.mkdir(parents=True, exist_ok=True)
    ratings.to_csv(RESULTS / f"rapm_{a.season}_players.csv", index=False)
    verdict = {"season": a.season, "lambda": lam_best, "cv": cv,
               "stability_r": stab_r, "stability_pass": gate_stab == "PASS",
               "benchmark": bench,
               "n_possessions": int(len(pr)), "n_players": nP}
    (RESULTS / f"rapm_{a.season}.json").write_text(json.dumps(verdict, indent=2))
    print(json.dumps({k: v for k, v in verdict.items() if k != "cv"}, indent=2))


if __name__ == "__main__":
    main()
