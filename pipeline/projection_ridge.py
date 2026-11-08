"""projection_ridge.py — P4 §11: ridge with age + lags on the sealed
modeling table (§11 preregistration fixed features, λ grid, nested
rolling-origin λ selection, and the ship rule before this ran).

    python pipeline/projection_ridge.py

Folds and targets identical to §10. Ship rule: beat EACH of the three §10
baselines on >= 4 of 5 folds with composite MAE ratio <= 0.98. On PASS this
also writes site-2027 point forecasts for current players
(data/projections/projections_2027.json) for the bake.

Output: data/projections/projection_ridge.json (+ forecasts on PASS).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "data" / "projections"
FOLDS = [2021, 2022, 2023, 2024, 2025]
TARGETS = ["next_pts36", "next_reb36", "next_ast36", "next_min_pg"]
SHRINK_K = 2000.0
LAMBDA_GRID = [1, 3, 10, 30, 100, 300]
CORE = ["pts36", "reb36", "ast36", "stl36", "blk36", "tov36",
        "ts_pct", "usg_pct", "ast_pct", "gp", "min_pg"]
FEATURES = ([f"lag1_{c}" for c in CORE] + [f"lag2_{c}" for c in CORE]
            + [f"rm2_{c}" for c in CORE]
            + ["age", "era", "min_tier"]
            + [f"z_{c}" for c in ("pts36", "reb36", "ast36", "ts_pct",
                                  "usg_pct", "ast_pct")])
SHIP_RATIO = 0.98


def ridge_fit_predict(Xtr, ytr, Xte, lam):
    """Standardized ridge WITH centering (the target mean rides back in)."""
    mu, sd = Xtr.mean(0), Xtr.std(0).replace(0, 1)
    Z = (Xtr - mu) / sd
    Zt = (Xte - mu) / sd
    Z = Z.fillna(0).to_numpy()
    Zt = Zt.fillna(0).to_numpy()
    ym = float(np.nanmean(ytr))
    yc = np.asarray(ytr, dtype=float) - ym
    A = Z.T @ Z + lam * np.eye(Z.shape[1])
    b = np.linalg.solve(A, Z.T @ yc)
    return Zt @ b + ym


def main() -> int:
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)
    base = json.loads((OUT / "projection_baselines.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)

    results = {"folds": {}, "composite": {}, "ship": {}}
    for S in FOLDS:
        train = t[(t.site <= S - 1) & t[TARGETS].notna().all(axis=1)]
        test = t[t.site == S].copy()
        nest_fit = t[(t.site <= S - 2) & t[TARGETS].notna().all(axis=1)]
        fold = {"ratios": {}, "lambdas": {}}
        for tgt in TARGETS:
            src = tgt.replace("next_", "")
            lag1 = test[f"lag1_{src}"]
            m = (test["lag1_gp"].fillna(0) * test["lag1_min_pg"].fillna(0))
            mu_train = float(train[tgt].mean())
            ytr = train[tgt].astype(float)

            # nested λ pick: fit <= S-2, validate S-1
            nest_val = t[t.site == S - 1]
            best_lam, best_mae = None, None
            for lam in LAMBDA_GRID:
                p = ridge_fit_predict(nest_fit[FEATURES], nest_fit[tgt].astype(float),
                                      nest_val[FEATURES], lam)
                ok = nest_val[tgt].notna()
                mae = float((nest_val.loc[ok, tgt] - p[ok.to_numpy()]).abs().mean())
                if best_mae is None or mae < best_mae:
                    best_mae, best_lam = mae, lam
            fold["lambdas"][tgt] = best_lam

            pred = ridge_fit_predict(train[FEATURES], ytr, test[FEATURES], best_lam)
            ok = test[tgt].notna()
            a = test.loc[ok, tgt].astype(float)
            p = pd.Series(pred, index=test.index)[ok]
            mae = float((a - p).abs().mean())
            rmse = float(((a - p) ** 2).mean() ** 0.5)
            r = float(np.corrcoef(a, p)[0, 1])
            rep_mae = base["folds"][str(S)][tgt]["repeat"].get("mae")
            twoyr_mae = base["folds"][str(S)][tgt]["twoyr"].get("mae")
            shr_mae = base["folds"][str(S)][tgt]["shrink"].get("mae")
            fold[tgt] = {"mae": round(mae, 3), "rmse": round(rmse, 3),
                         "r": round(r, 3),
                         "ratio_vs_repeat": round(mae / rep_mae, 4) if rep_mae else None,
                         "ratio_vs_twoyr": round(mae / twoyr_mae, 4) if twoyr_mae else None,
                         "ratio_vs_shrink": round(mae / shr_mae, 4) if shr_mae else None}
        results["folds"][str(S)] = fold

    # composites + ship verdict vs EACH baseline
    beats = {b: 0 for b in ("repeat", "shrink", "twoyr")}
    for S in FOLDS:
        fold = results["folds"][str(S)]
        comp = {}
        for b in ("repeat", "shrink", "twoyr"):
            rs = [fold[t][f"ratio_vs_{b}"] for t in TARGETS
                  if fold[t].get(f"ratio_vs_{b}")]
            comp[b] = round(float(np.mean(rs)), 4) if rs else None
            if comp[b] is not None and comp[b] <= SHIP_RATIO:
                beats[b] += 1
        results["composite"][str(S)] = comp
    results["ship"] = {b: {"folds_beaten": beats[b], "needed": 4,
                           "pass": beats[b] >= 4} for b in beats}
    results["ship"]["verdict"] = ("PASS" if all(v["pass"] for v in results["ship"].values()
                                                if isinstance(v, dict))
                                  else "FAIL")
    print(json.dumps({"composite": results["composite"], "ship": results["ship"]}, indent=1))
    (OUT / "projection_ridge.json").write_text(json.dumps(results, indent=1))
    if results["ship"]["verdict"] != "PASS":
        return 0  # FAIL is a recorded outcome, not an error

    # ---- PASS: site-2027 point forecasts for current players ----------------
    cur = t[(t.site == 2026)].copy()
    preds = {}
    for tgt in TARGETS:
        # refit on ALL rows with that target, λ re-picked by the last nested origin
        full = t[t[tgt].notna()]
        lam = LAMBDA_GRID[-1]
        # nested pick on the final origin (2025)
        nf = t[t.site <= 2024]
        nv = t[t.site == 2025]
        best_mae = None
        for lam_try in LAMBDA_GRID:
            p = ridge_fit_predict(nf[FEATURES], nf[tgt].astype(float),
                                  nv[FEATURES], lam_try)
            ok = nv[tgt].notna()
            mae = float((nv.loc[ok, tgt] - p[ok.to_numpy()]).abs().mean())
            if best_mae is None or mae < best_mae:
                best_mae, lam = mae, lam_try
        preds[tgt] = ridge_fit_predict(full[FEATURES], full[tgt].astype(float),
                                       cur[FEATURES], lam)
    out = {}
    for i, (_, row) in enumerate(cur.iterrows()):
        out[str(row["nba_pid"]) if pd.notna(row["nba_pid"]) else f"bdl{int(row['pid'])}"] = {
            "name": row["name"], "nba_pid": row["nba_pid"], "bdl_pid": int(row["pid"]),
            "age": row["age"], "site": 2027,
            "pts36": round(float(preds["next_pts36"][i]), 2),
            "reb36": round(float(preds["next_reb36"][i]), 2),
            "ast36": round(float(preds["next_ast36"][i]), 2),
            "mpg": round(float(preds["next_min_pg"][i]), 1),
        }
    (OUT / "projections_2027.json").write_text(json.dumps({
        "as_of": "2026-11-08", "model": "ridge+age+lags (§11)",
        "targets": "per-36 rates + mpg — forecast of stats, not value",
        "players": out}, indent=1))
    print(f"forecasts written: {len(out)} players")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
