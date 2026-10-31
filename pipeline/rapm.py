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
LAMBDA_GRID = [100, 300, 1000, 3000, 10000]
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
    pr = pd.read_parquet(DERIVED / f"poss_rosters_{a.season}.parquet")
    pr = pr[~pr.dead_ball].reset_index(drop=True)
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
    gids = pr.game_id.to_numpy()
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
        gids[rix] = row.game_id
    y = y - y.mean()  # league scoring environment absorbed; ratings per-possession

    # λ by 5-fold CV grouped by game
    uniq = pd.unique(gids)
    folds = {g: i % 5 for i, g in enumerate(sorted(uniq))}
    f = np.array([folds[g] for g in gids])
    cv = {}
    for lam in LAMBDA_GRID:
        sse = 0.0
        wtot = 0.0
        for k in range(5):
            tr, te = f != k, f == k
            beta, _ = fit_ridge(X[tr], y[tr], np.ones(tr.sum()), lam)
            sse += float(np.sum((y[te] - X[te] @ beta) ** 2))
            wtot += te.sum()
        cv[lam] = sse / wtot
        print(f"  λ={lam}: held-out MSE {cv[lam]:.4f}")
    lam_best = min(cv, key=cv.get)
    print(f"λ chosen: {lam_best}")

    beta, _ = fit_ridge(X, y, np.ones(len(y)), lam_best)
    off = beta[:nP]
    # per-100 ratings
    ratings = pd.DataFrame({"aid": players, "rapm_per100": off * 100.0})

    # split-half stability (even/odd game ids)
    half = np.array([hash(g) % 2 for g in gids])
    res = {}
    for tag, mask in (("even", half == 0), ("odd", half == 1)):
        beta_h, _ = fit_ridge(X[mask], y[mask], np.ones(mask.sum()), lam_best)
        res[tag] = pd.DataFrame({"aid": players, "r": beta_h[:nP] * 100.0})
    mg = res["even"].merge(res["odd"], on="aid", suffixes=("_e", "_o"))
    # possession counts per player per half for the >=500 filter
    poss_cnt = {}
    for rix, row in enumerate(pr.itertuples()):
        for aid in row.on10:
            poss_cnt[(aid, gids[rix], int(half[rix]))] = 1
    pc = pd.Series(poss_cnt).rename("n").reset_index()
    pc.columns = ["aid", "game_id", "half", "n"]
    ph = pc.groupby(["aid", "half"]).n.sum().unstack(fill_value=0)
    mg = mg.merge(ph.rename(columns={0: "n_even", 1: "n_odd"}), on="aid", how="left")
    sel = mg[(mg.n_even >= 500) & (mg.n_odd >= 500)]
    stab_r = float(sel.r_e.corr(sel.r_o))
    gate_stab = "PASS" if stab_r >= 0.60 else "FAIL"
    print(f"GATE stability: {gate_stab} — r {stab_r:.3f} on {len(sel)} players (≥500 poss both halves)")

    # benchmark vs LUMA
    bench = None
    luma_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/luma/xpts_rapm_2025.parquet"
    if luma_f.exists():
        lg = pd.read_parquet(luma_f)
        # name join: our aids are ESPN athlete ids; use the box names
        pg = pd.read_parquet(Path.home() / "Projects/vt_baseball/hoops_mart/data/mart/player_game.parquet")
        nm = pg.dropna(subset=["name"]).set_index("athlete_id").name.to_dict()
        ratings["name"] = ratings.aid.map(nm)
        ratings["norm"] = ratings.name.map(norm)
        lg["norm"] = lg.pid.astype(str).map(
            pd.read_parquet(Path.home() / "Projects/vt_baseball/hoops_mart/data/pbpstats/players.parquet")
            .astype({"pid": str}).set_index("pid").name).map(norm)
        # possession counts for the >=250 filter
        pcnt = pr.explode("on10").groupby("on10").size().rename("poss")
        ratings["poss"] = ratings.aid.map(pcnt)
        mrg = ratings.merge(lg[["norm", "xpts_net"]], on="norm", how="inner")
        sel = mrg[mrg.poss >= 250]
        bench_r = float(sel.rapm_per100.corr(sel.xpts_net))
        gate_b = "PASS" if bench_r >= 0.70 else "FAIL"
        print(f"GATE LUMA benchmark: {gate_b} — r {bench_r:.3f} on {len(sel)} shared players (≥250 poss)")
        bench = {"r": bench_r, "n": int(len(sel)), "pass": gate_b == "PASS"}
        ratings.drop(columns=["norm"], inplace=True)

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
