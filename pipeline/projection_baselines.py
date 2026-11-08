"""projection_baselines.py — P4 §10: the three naive baselines on the sealed
modeling table (PROJECTIONS-SCOPE §2; §10 preregistration fixed the folds,
formulas, and metrics before this ran).

    python pipeline/projection_baselines.py

Folds (time only): train = rows with site <= S-1, predict site S where the
target exists; S in {2021..2025}. Targets: next_pts36/next_reb36/next_ast36/
next_min_pg/next_gp. Baselines: naive repeat (lag1), league-mean + minutes
shrink (w = m/(m+2000)), two-year weighted (2:1, lag2 fallback to lag1).
Metrics per target x fold x baseline: MAE, RMSE, Pearson r.

Output: data/projections/projection_baselines.json (sealed artifact; the
composite column feeds §11's ship rule).
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
TARGETS = ["next_pts36", "next_reb36", "next_ast36", "next_min_pg", "next_gp"]
SHRINK_K = 2000.0  # §10 preregistered minutes-shrink constant


def b1_repeat(t: pd.Series, lag1: pd.Series) -> pd.Series:
    return lag1


def b2_shrink(t: pd.Series, lag1: pd.Series, m: pd.Series,
              mu_train: float) -> pd.Series:
    w = m / (m + SHRINK_K)
    return w * lag1 + (1 - w) * mu_train


def b3_twoyear(lag1: pd.Series, lag2: pd.Series) -> pd.Series:
    out = lag1.copy()
    has = lag2.notna()
    out[has] = (2 / 3) * lag1[has] + (1 / 3) * lag2[has]
    return out


def metrics(actual: pd.Series, pred: pd.Series) -> dict:
    ok = actual.notna() & pred.notna()
    a, p = actual[ok], pred[ok]
    if len(a) < 30:
        return {"n": int(len(a))}
    mae = float((a - p).abs().mean())
    rmse = float(((a - p) ** 2).mean() ** 0.5)
    r = float(np.corrcoef(a, p)[0, 1]) if a.std() > 0 and p.std() > 0 else None
    return {"n": int(len(a)), "mae": round(mae, 3), "rmse": round(rmse, 3),
            "r": round(r, 3) if r is not None else None}


def main() -> int:
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    OUT.mkdir(parents=True, exist_ok=True)
    results = {"folds": {}, "composite": {}}
    for S in FOLDS:
        train = t[t.site <= S - 1]
        test = t[t.site == S].copy()
        fold = {}
        for tgt in TARGETS:
            src = tgt.replace("next_", "")
            lag1 = test[f"lag1_{src}"]
            lag2 = test[f"lag2_{src}"]
            m = (test["lag1_gp"].fillna(0) * test["lag1_min_pg"].fillna(0))
            mu_train = float(train[tgt].mean())
            preds = {
                "repeat": b1_repeat(tgt, lag1),
                "shrink": b2_shrink(tgt, lag1, m, mu_train),
                "twoyr": b3_twoyear(lag1, lag2),
            }
            fold[tgt] = {name: metrics(test[tgt], p) for name, p in preds.items()}
        results["folds"][str(S)] = fold

    # composite per fold: mean over targets of MAE ratio (shrink/repeat,
    # twoyr/repeat) — the number §11's ship rule multiplies against
    for S in FOLDS:
        fold = results["folds"][str(S)]
        ratios = {"shrink": [], "twoyr": []}
        for tgt in TARGETS:
            base_mae = fold[tgt]["repeat"].get("mae")
            if not base_mae:
                continue
            for name in ratios:
                m = fold[tgt][name].get("mae")
                if m:
                    ratios[name].append(m / base_mae)
        results["composite"][str(S)] = {
            k: round(float(np.mean(v)), 4) for k, v in ratios.items() if v}

    (OUT / "projection_baselines.json").write_text(json.dumps(results, indent=1))
    # readable summary
    print("fold | target        | repeat MAE | shrink | twoyr  | r(repeat)")
    for S in FOLDS:
        f = results["folds"][str(S)]
        for tgt in TARGETS:
            r = f[tgt]["repeat"]
            if "mae" not in r:
                continue
            print(f"{S} | {tgt:13} | {r['mae']:10.3f} | "
                  f"{f[tgt]['shrink'].get('mae', float('nan')):6.3f} | "
                  f"{f[tgt]['twoyr'].get('mae', float('nan')):6.3f} | {r['r']}")
    print("composite (MAE ratio vs repeat):",
          json.dumps(results["composite"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
