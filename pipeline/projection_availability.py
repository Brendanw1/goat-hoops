"""projection_availability.py — P4 §12c: the availability model
(§12c preregistration fixed target, baselines, and the Brier gate first).

    python pipeline/projection_availability.py

Target: played >= 60 games next season (binary). Folds identical to §10-12b.
Model: LightGBM binary classifier, the §11 feature matrix, fixed config.
Baselines: base rate (training fold's P(>=60) for all) and the repeat rule
(1 if lag1_gp >= 60 else 0, scored as probabilities). Gate: Brier below
BOTH baselines on >= 4/5 folds.

Output: data/projections/projection_avail.json (+ availability
probabilities for current players on PASS).
"""

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
GAMES_T = 60
CORE = ["pts36", "reb36", "ast36", "stl36", "blk36", "tov36",
        "ts_pct", "usg_pct", "ast_pct", "gp", "min_pg"]
FEATURES = ([f"lag1_{c}" for c in CORE] + [f"lag2_{c}" for c in CORE]
            + [f"rm2_{c}" for c in CORE]
            + ["age", "era", "min_tier"]
            + [f"z_{c}" for c in ("pts36", "reb36", "ast36", "ts_pct",
                                  "usg_pct", "ast_pct")])
PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=31,
              min_child_samples=20, subsample=0.9, colsample_bytree=0.9,
              random_state=7, verbose=-1, n_jobs=3, objective="binary")


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((y - p) ** 2))


def logloss(y: np.ndarray, p: np.ndarray, eps: float = 1e-6) -> float:
    q = np.clip(p, eps, 1 - eps)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def main() -> int:
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)
    t = t[t["next_gp"].notna()].copy()
    y_all = (t["next_gp"] >= GAMES_T).astype(int)

    results = {"folds": {}, "ship": {}, "reliability": {}}
    beats = {"base": 0, "repeat": 0}
    for S in FOLDS:
        tr_mask = (t.site <= S - 1) & y_all.index.isin(
            t[t.site <= S - 1].index)
        train = t[tr_mask]
        test = t[t.site == S]
        ytr = (train["next_gp"] >= GAMES_T).astype(int).to_numpy()
        yte = (test["next_gp"] >= GAMES_T).astype(int).to_numpy()

        model = lgb.LGBMClassifier(**PARAMS)
        model.fit(train[FEATURES], ytr)
        p_model = model.predict_proba(test[FEATURES])[:, 1]
        p_base = np.full(len(yte), float(ytr.mean()))
        p_repeat = (test["lag1_gp"].to_numpy() >= GAMES_T).astype(float)

        b_model, b_base, b_rep = (brier(yte, p_model), brier(yte, p_base),
                                  brier(yte, p_repeat))
        fold = {"n": int(len(yte)),
                "base_rate": round(float(yte.mean()), 3),
                "brier": {"model": round(b_model, 4), "base": round(b_base, 4),
                          "repeat": round(b_rep, 4)},
                "logloss_model": round(logloss(yte, p_model), 4)}
        if b_model < b_base:
            beats["base"] += 1
        if b_model < b_rep:
            beats["repeat"] += 1
        # reliability: model-probability quintiles
        edges = np.quantile(p_model, [0, 0.2, 0.4, 0.6, 0.8, 1.0])
        bins = np.clip(np.digitize(p_model, edges[1:-1]), 0, 4)
        results["reliability"][str(S)] = [
            {"p_lo": round(float(edges[i]), 3), "p_hi": round(float(edges[i + 1]), 3),
             "n": int((bins == i).sum()),
             "actual": round(float(yte[bins == i].mean()), 3)}
            for i in range(5) if (bins == i).any()]
        results["folds"][str(S)] = fold
    results["ship"] = {"beats_base": beats["base"], "beats_repeat": beats["repeat"],
                       "needed": 4,
                       "verdict": "PASS" if (beats["base"] >= 4 and beats["repeat"] >= 4)
                       else "FAIL"}
    print(json.dumps({"folds": {k: {"brier": v["brier"]}
                                for k, v in results["folds"].items()},
                      "ship": results["ship"]}, indent=1))
    (OUT / "projection_avail.json").write_text(json.dumps(results, indent=1))

    if results["ship"]["verdict"] != "PASS":
        return 0
    cur = t[(t.site == 2026)].copy()
    model = lgb.LGBMClassifier(**PARAMS)
    yfull = (t["next_gp"] >= GAMES_T).astype(int)
    model.fit(t[FEATURES], yfull)
    p = model.predict_proba(cur[FEATURES])[:, 1]
    out = {}
    for i, (_, row) in enumerate(cur.iterrows()):
        key = str(row["nba_pid"]) if pd.notna(row["nba_pid"]) else f"bdl{int(row['pid'])}"
        out[key] = {"name": row["name"], "p60": round(float(p[i]), 3)}
    (OUT / "availability_2027.json").write_text(json.dumps({
        "as_of": "2026-11-08", "model": "LightGBM §12c",
        "definition": "P(>= 60 games in 2026-27) — availability, not durability",
        "players": out}, indent=1))
    print(f"availability forecasts: {len(out)} players")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
