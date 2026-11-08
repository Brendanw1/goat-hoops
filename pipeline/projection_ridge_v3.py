"""projection_ridge_v3.py — P4 §13: the senior rebuild's read (§13
preregistration fixed the feature additions, the gate, and the conformal
interval design before this ran).

    python pipeline/projection_ridge_v3.py

Ridge v3 on the v3 table (rookie indicators, gp_frac, age_sq, momentum)
vs the §11 ridge, identical folds; gate = composite <= 0.98 on >= 4/5
folds. Intervals: cross-fold split-conformal at 90% (calibrate on the
other folds' residuals, evaluate on the held-out fold); gate = mean
empirical coverage in [0.85, 0.95].

Output: data/projections/projection_ridge_v3.json (+ forecasts with
intervals on PASS, keyed for the bake).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402
from projection_ridge import ridge_fit_predict  # the centered estimator

DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "data" / "projections"
FOLDS = [2021, 2022, 2023, 2024, 2025]
TARGETS = ["next_pts36", "next_reb36", "next_ast36", "next_min_pg"]
LAMBDA_GRID = [1, 3, 10, 30, 100, 300]
CORE = ["pts36", "reb36", "ast36", "stl36", "blk36", "tov36",
        "ts_pct", "usg_pct", "ast_pct", "gp", "min_pg"]
V2_FEATURES = ([f"lag1_{c}" for c in CORE] + [f"lag2_{c}" for c in CORE]
               + [f"rm2_{c}" for c in CORE]
               + ["age", "era", "min_tier"]
               + [f"z_{c}" for c in ("pts36", "reb36", "ast36", "ts_pct",
                                     "usg_pct", "ast_pct")])
V3_FEATURES = (V2_FEATURES + ["has_lag1", "has_lag2", "rookie", "age_sq",
                              "gp_frac", "lag1_gp_frac"]
               + [f"mom_{c}" for c in ("pts36", "reb36", "ast36")])
SHIP_RATIO = 0.98
COVERAGE_BAND = (0.85, 0.95)
NOMINAL = 0.90


def main() -> int:
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)
    ridge11 = json.loads((OUT / "projection_ridge.json").read_text())

    results = {"folds": {}, "composite": {}, "ship": {}, "intervals": {}}
    beats = 0
    residuals = {tgt: {} for tgt in TARGETS}  # fold -> resid array
    for S in FOLDS:
        train = t[(t.site <= S - 1) & t[TARGETS].notna().all(axis=1)]
        test = t[t.site == S].copy()
        nest_fit = t[(t.site <= S - 2) & t[TARGETS].notna().all(axis=1)]
        nest_val = t[t.site == S - 1]
        fold = {}
        for tgt in TARGETS:
            best_lam, best_mae = None, None
            for lam in LAMBDA_GRID:
                p = ridge_fit_predict(nest_fit[V3_FEATURES ], nest_fit[tgt].astype(float),
                                      nest_val[V3_FEATURES], lam)
                ok = nest_val[tgt].notna()
                mae = float((nest_val.loc[ok, tgt] - p[ok.to_numpy()]).abs().mean())
                if best_mae is None or mae < best_mae:
                    best_mae, best_lam = mae, lam
            pred = ridge_fit_predict(train[V3_FEATURES], train[tgt].astype(float),
                                     test[V3_FEATURES], best_lam)
            ok = test[tgt].notna()
            act = test.loc[ok, tgt].astype(float)
            ps = pd.Series(pred, index=test.index)[ok]
            resid = (act - ps).to_numpy()
            residuals[tgt][str(S)] = resid
            mae = float(np.abs(resid).mean())
            r = float(np.corrcoef(act, ps)[0, 1])
            r11 = ridge11["folds"][str(S)][tgt]["mae"]
            fold[tgt] = {"mae": round(mae, 3), "r": round(r, 3),
                         "lambda": best_lam,
                         "ratio_vs_ridge11": round(mae / r11, 4) if r11 else None}
        rs = [fold[t]["ratio_vs_ridge11"] for t in TARGETS if fold[t].get("ratio_vs_ridge11")]
        comp = round(float(np.mean(rs)), 4) if rs else None
        results["composite"][str(S)] = comp
        if comp is not None and comp <= SHIP_RATIO:
            beats += 1
        results["folds"][str(S)] = fold

    # conformal intervals: cross-fold calibration -----------------------------
    coverage = {}
    widths = {}
    for tgt in TARGETS:
        covs = []
        for S in FOLDS:
            test_resid = np.abs(residuals[tgt][str(S)])
            cal = np.concatenate([v for k, v in residuals[tgt].items() if k != str(S)])
            q = float(np.quantile(cal, NOMINAL))
            covs.append(float((test_resid <= q).mean()))
            widths.setdefault(tgt, q)
        coverage[tgt] = round(float(np.mean(covs)), 4)
    results["intervals"] = {"nominal": NOMINAL,
                            "empirical_coverage": coverage,
                            "half_widths": {k: round(v, 2) for k, v in widths.items()},
                            "gate_pass": all(COVERAGE_BAND[0] <= c <= COVERAGE_BAND[1]
                                             for c in coverage.values())}

    results["ship"] = {"folds_beaten": beats, "needed": 4,
                       "composite_pass": beats >= 4,
                       "verdict": ("PASS" if beats >= 4 else "FAIL")}
    print(json.dumps({"composite": results["composite"],
                      "intervals": results["intervals"],
                      "ship": results["ship"]}, indent=1))
    (OUT / "projection_ridge_v3.json").write_text(json.dumps(results, indent=1))
    if results["ship"]["verdict"] != "PASS":
        return 0

    # site-2027 forecasts with intervals --------------------------------------
    cur = t[t.site == 2026].copy()
    full = t[t[TARGETS].notna().all(axis=1)]
    out = {}
    pred_map = {}
    for tgt in TARGETS:
        nf = t[(t.site <= 2024) & t[TARGETS].notna().all(axis=1)]
        nv = t[(t.site == 2025) & t[tgt].notna()]
        best_mae, lam_star = None, None
        for lam in LAMBDA_GRID:
            p = ridge_fit_predict(nf[V3_FEATURES], nf[tgt].astype(float),
                                  nv[V3_FEATURES], lam)
            ok = nv[tgt].notna()
            mae = float((nv.loc[ok, tgt] - p[ok.to_numpy()]).abs().mean())
            if best_mae is None or mae < best_mae:
                best_mae, lam_star = mae, lam
        model_pred = ridge_fit_predict(full[V3_FEATURES], full[tgt].astype(float),
                                       cur[V3_FEATURES], lam_star)
        pred_map[tgt] = model_pred
    for i, (_, row) in enumerate(cur.iterrows()):
        key = str(row["nba_pid"]) if pd.notna(row["nba_pid"]) else f"bdl{int(row['pid'])}"
        src = ("pts36", "reb36", "ast36", "mpg")
        out[key] = {
            "name": row["name"], "nba_pid": row["nba_pid"], "bdl_pid": int(row["pid"]),
            "age": row["age"], "site": 2027,
            "pts36": round(float(pred_map["next_pts36"][i]), 2),
            "reb36": round(float(pred_map["next_reb36"][i]), 2),
            "ast36": round(float(pred_map["next_ast36"][i]), 2),
            "mpg": round(float(pred_map["next_min_pg"][i]), 1),
            "lo": {k: round(float(pred_map[f"next_{k}"][i] - widths[f"next_{k}"]), 2)
                   for k in src},
            "hi": {k: round(float(pred_map[f"next_{k}"][i] + widths[f"next_{k}"]), 2)
                   for k in src},
        }
    (OUT / "projections_2027_v3.json").write_text(json.dumps({
        "as_of": "2026-11-08", "model": "ridge v3 + conformal 90% (§13)",
        "targets": "per-36 rates + mpg — forecast of stats, not value",
        "coverage": coverage, "players": out}, indent=1))
    print(f"forecasts written: {len(out)} players (v3, with intervals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
