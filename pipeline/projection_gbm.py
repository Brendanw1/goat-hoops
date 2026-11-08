"""projection_gbm.py — P4 §12a/§12b: gradient boosting increments on the
sealed modeling table (§12a preregistration fixed config + gate before fit).

    python pipeline/projection_gbm.py --mode 12a   # §11 features, LightGBM
    python pipeline/projection_gbm.py --mode 12b   # + tracking lags (site 2016+)

Folds/targets identical to §10/§11. §12a gate: composite MAE ratio vs the
§11 ridge <= 0.98 on >= 4/5 folds. §12b gate: same bar vs the prior winner
(12a if it passed, else §11). Missing features stay NaN (LightGBM native).

Output: data/projections/projection_gbm.json (+ forecasts on a superseding
PASS, keyed for the bake).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "data" / "projections"
FOLDS = [2021, 2022, 2023, 2024, 2025]
TARGETS = ["next_pts36", "next_reb36", "next_ast36", "next_min_pg"]
CORE = ["pts36", "reb36", "ast36", "stl36", "blk36", "tov36",
        "ts_pct", "usg_pct", "ast_pct", "gp", "min_pg"]
BASE_FEATURES = ([f"lag1_{c}" for c in CORE] + [f"lag2_{c}" for c in CORE]
                 + [f"rm2_{c}" for c in CORE]
                 + ["age", "era", "min_tier"]
                 + [f"z_{c}" for c in ("pts36", "reb36", "ast36", "ts_pct",
                                       "usg_pct", "ast_pct")])
TRACK_PER36 = ["tracking_drives.drives_p36", "tracking_possessions.touches_p36",
               "tracking_possessions.paint_touches_p36",
               "tracking_possessions.front_ct_touches_p36",
               "tracking_defense.def_rim_fga_p36",
               "tracking_speeddistance.dist_miles_p36"]
SHIP_RATIO = 0.98
PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=31,
              min_child_samples=20, subsample=0.9, colsample_bytree=0.9,
              random_state=7, verbose=-1, n_jobs=3)


def add_tracking(t: pd.DataFrame) -> pd.DataFrame:
    """Tracking per-36 lags: the wide table's tracking_* columns are per-game
    counts — per-36 = count / min_pg * 36. Then season z-scores + lag1."""
    import re
    t = t.copy()
    for col in TRACK_PER36:
        fam, leaf = col.split(".")
        src = f"{fam}.{leaf.replace('_p36', '')}"
        if src not in t.columns:
            continue
        v = pd.to_numeric(t[src], errors="coerce")
        t[col] = v / t["min_pg"] * 36
        grp = t.groupby("site")[col]
        mu, sd = grp.transform("mean"), grp.transform("std")
        t[f"z_{col}"] = (t[col] - mu) / sd.replace(0, np.nan)
        t[f"lag1_{col}"] = t.groupby("pid")[col].shift(1)
        t[f"lag1_z_{col}"] = t.groupby("pid")[f"z_{col}"].shift(1)
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["12a", "12b"], required=True)
    a = ap.parse_args()
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)

    ridge = json.loads((OUT / "projection_ridge.json").read_text())
    prior_best = "ridge §11"
    if a.mode == "12b":
        gbm12a = OUT / "projection_gbm.json"
        if gbm12a.exists():
            r12a = json.loads(gbm12a.read_text())
            if r12a.get("ship", {}).get("verdict") == "PASS":
                prior_best = "gbm §12a"
                ridge = r12a
    features = BASE_FEATURES if a.mode == "12a" else None
    if a.mode == "12b":
        t = add_tracking(t)
        features = BASE_FEATURES + [f"lag1_{c}" for c in TRACK_PER36 if f"lag1_{c}" in t.columns] \
            + [f"lag1_z_{c}" for c in TRACK_PER36 if f"lag1_z_{c}" in t.columns]

    results = {"mode": a.mode, "prior_best": prior_best,
               "features": len(features), "folds": {}, "composite": {}, "ship": {}}
    beats = 0
    for S in FOLDS:
        train = t[(t.site <= S - 1) & t[TARGETS].notna().all(axis=1)]
        test = t[t.site == S].copy()
        fold = {}
        for tgt in TARGETS:
            ytr = train[tgt].astype(float)
            model = lgb.LGBMRegressor(**PARAMS)
            model.fit(train[features], ytr)
            p = model.predict(test[features])
            ok = test[tgt].notna()
            act = test.loc[ok, tgt].astype(float)
            ps = pd.Series(p, index=test.index)[ok]
            mae = float((act - ps).abs().mean())
            r = float(np.corrcoef(act, ps)[0, 1])
            ridge_mae = ridge["folds"][str(S)][tgt]["mae"]
            fold[tgt] = {"mae": round(mae, 3), "r": round(r, 3),
                         "ratio_vs_prior": round(mae / ridge_mae, 4) if ridge_mae else None}
        rs = [fold[t]["ratio_vs_prior"] for t in TARGETS if fold[t].get("ratio_vs_prior")]
        comp = round(float(np.mean(rs)), 4) if rs else None
        results["composite"][str(S)] = comp
        if comp is not None and comp <= SHIP_RATIO:
            beats += 1
        results["folds"][str(S)] = fold
    results["ship"] = {"prior_best": prior_best, "folds_beaten": beats,
                       "needed": 4, "pass": beats >= 4,
                       "verdict": "PASS" if beats >= 4 else "FAIL"}
    print(json.dumps({"composite": results["composite"], "ship": results["ship"]}, indent=1))
    (OUT / f"projection_gbm_{a.mode}.json").write_text(json.dumps(results, indent=1))

    if results["ship"]["verdict"] != "PASS":
        return 0
    # superseding PASS → site-2027 forecasts from this model
    cur = t[t.site == 2026].copy()
    full = t[t[TARGETS].notna().all(axis=1)]
    preds = {}
    for tgt in TARGETS:
        model = lgb.LGBMRegressor(**PARAMS)
        model.fit(full[features], full[tgt].astype(float))
        preds[tgt] = model.predict(cur[features])
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
    (OUT / f"projections_2027_{a.mode}.json").write_text(json.dumps({
        "as_of": "2026-11-08",
        "model": f"LightGBM §{a.mode} (features {len(features)})",
        "targets": "per-36 rates + mpg — forecast of stats, not value",
        "players": out}, indent=1))
    print(f"forecasts written: {len(out)} players ({a.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
