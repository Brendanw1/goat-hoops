"""projection_env.py — P4 §14: env-normalized targets + drift-aware
conformal intervals (§14 preregistration fixed the normalization rule, the
two interval variants, and both gates before this ran).

    python pipeline/projection_env.py

Model: the §13 ridge (v3 features, same folds/λ/nested selection) trained
on env-normalized per-36 targets — ẑ = (next_t − μ̂_S)/σ̂_S with
μ̂_S = mean(μ_{S-1..S-3}) (σ̂ likewise), the env-forecast rule a real
forecast must pay. min_pg stays raw. Predictions back-transform to raw
space and score on the identical ladder vs the §11 ridge.

Intervals: drift-aware conformal, two preregistered variants — (a)
one-fold-back calibration, (b) rolling-2; per target the first variant
with mean coverage in [0.85, 0.95] wins. Intervals attach to the best
composite model on record.

Output: data/projections/projection_env.json (+ forecasts with intervals
per the ship rule).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402
from projection_ridge import ridge_fit_predict

DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "data" / "projections"
FOLDS = [2021, 2022, 2023, 2024, 2025]
RATE_TARGETS = ["next_pts36", "next_reb36", "next_ast36"]  # normalized
RAW_TARGETS = ["next_min_pg"]                              # kept raw
TARGETS = RATE_TARGETS + RAW_TARGETS
LAMBDA_GRID = [1, 3, 10, 30, 100, 300]
NOMINAL = 0.90
COVERAGE_BAND = (0.85, 0.95)
SHIP_RATIO = 0.98
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


def env_stats(t: pd.DataFrame, tgt: str) -> dict[int, tuple[float, float]]:
    """League mean/sd of the target's RAW next-season value per season."""
    g = t.groupby("site")[tgt]
    mu, sd = g.mean(), g.std()
    return {int(s): (float(mu[s]), float(sd[s])) for s in mu.index}


def env_forecast(env: dict[int, tuple[float, float]], S: int) -> tuple[float, float]:
    """Preregistered rule: the env of season S forecast from S-1..S-3 —
    entries whose env is not realizable (NaN) are skipped, so the rule is
    'the mean of the available prior seasons'."""
    mus, sds = [], []
    for k in (S - 1, S - 2, S - 3):
        m, sd = env.get(k, (np.nan, np.nan))
        if np.isfinite(m) and np.isfinite(sd) and sd > 0:
            mus.append(m)
            sds.append(sd)
    if not mus:
        return np.nan, np.nan
    return float(np.mean(mus)), float(np.mean(sds))


def main() -> int:
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)
    ridge11 = json.loads((OUT / "projection_ridge.json").read_text())

    envs = {tgt: env_stats(t, tgt) for tgt in TARGETS}
    results = {"folds": {}, "composite": {}, "ship": {}, "intervals": {}}
    beats = 0
    resid = {tgt: {} for tgt in TARGETS}
    for S in FOLDS:
        train = t[(t.site <= S - 1) & t[TARGETS].notna().all(axis=1)].copy()
        test = t[t.site == S].copy()
        nest_fit = t[(t.site <= S - 2) & t[TARGETS].notna().all(axis=1)].copy()
        nest_val = t[t.site == S - 1].copy()
        mu_f, sd_f = env_forecast(envs["next_pts36"], S)
        fold = {}
        for tgt in TARGETS:
            rate = tgt in RATE_TARGETS
            mu_t, sd_t = env_forecast(envs[tgt], S)
            if rate:
                # normalize targets by the env FORECAST (what a real forecast
                # knew at prediction time), not the realized env
                ytr_z = (train[tgt] - mu_t) / (sd_t if sd_t > 0 else 1.0)
            else:
                ytr_z = train[tgt].astype(float)
            best_mae_z, lam_star = None, None
            for lam in LAMBDA_GRID:
                p = ridge_fit_predict(nest_fit[V3_FEATURES],
                                      ((nest_fit[tgt] - mu_t) / (sd_t if sd_t > 0 and rate else 1.0)
                                       if rate else nest_fit[tgt]).astype(float),
                                      nest_val[V3_FEATURES], lam)
                ok = nest_val[tgt].notna()
                if rate:
                    p_raw = p * sd_t + mu_t
                else:
                    p_raw = p
                mae = float((nest_val.loc[ok, tgt] - p_raw[ok.to_numpy()]).abs().mean())
                if best_mae_z is None or mae < best_mae_z:
                    best_mae_z, lam_star = mae, lam
            pred_z = ridge_fit_predict(train[V3_FEATURES], ytr_z,
                                       test[V3_FEATURES], lam_star)
            p_raw = pred_z * sd_t + mu_t if rate else pred_z
            ok = test[tgt].notna()
            act = test.loc[ok, tgt].astype(float)
            ps = pd.Series(p_raw, index=test.index)[ok]
            r_ = (act - ps).to_numpy()
            resid[tgt][str(S)] = r_
            mae = float(np.abs(r_).mean())
            r = float(np.corrcoef(act, ps)[0, 1])
            r11 = ridge11["folds"][str(S)][tgt]["mae"]
            fold[tgt] = {"mae": round(mae, 3), "r": round(r, 3),
                         "lambda": lam_star,
                         "ratio_vs_ridge11": round(mae / r11, 4) if r11 else None}
        rs = [fold[t]["ratio_vs_ridge11"] for t in TARGETS if fold[t].get("ratio_vs_ridge11")]
        comp = round(float(np.mean(rs)), 4) if rs else None
        results["composite"][str(S)] = comp
        if comp is not None and comp <= SHIP_RATIO:
            beats += 1
        results["folds"][str(S)] = fold
    results["ship"] = {"folds_beaten": beats, "needed": 4,
                       "verdict": "PASS" if beats >= 4 else "FAIL",
                       "note": "composite vs the §11 ridge; FAIL leaves §11 as the shipped point model"}

    # drift-aware conformal: variant (a) one-fold-back, (b) rolling-2 --------
    intervals = {}
    for tgt in TARGETS:
        chosen = None
        best_try = None
        for variant in ("one_back", "roll2"):
            covs, qs = [], {}
            for S in FOLDS:
                cal_keys = ({str(S - 1)} if variant == "one_back"
                            else {str(S - 1), str(S - 2)})
                cals = [resid[tgt][k] for k in cal_keys if k in resid[tgt]]
                if not cals:
                    continue  # folds before the first calibration year
                cal = np.concatenate(cals)
                if len(cal) < 50:
                    continue
                q = float(np.quantile(np.abs(cal), NOMINAL))
                qs[str(S)] = q
                covs.append(float((np.abs(resid[tgt][str(S)]) <= q).mean()))
            if not covs or len(covs) < 3:
                continue
            mc = float(np.mean(covs))
            trial = {"variant": variant, "coverage": round(mc, 4),
                     "q90": round(float(np.mean(list(qs.values()))), 2),
                     "folds_evaluated": len(covs)}
            if best_try is None:
                best_try = trial
            if COVERAGE_BAND[0] <= mc <= COVERAGE_BAND[1]:
                chosen = trial
                break
        if chosen:
            chosen["pass"] = True
            intervals[tgt] = chosen
        else:
            intervals[tgt] = {**(best_try or {}), "pass": False}
    results["intervals"] = intervals
    results["intervals_pass"] = all(v.get("pass") for v in intervals.values())
    print(json.dumps({"composite": results["composite"],
                      "ship": results["ship"],
                      "intervals": {k: {"variant": v.get("variant"),
                                        "coverage": v.get("coverage"),
                                        "q90": v.get("q90"),
                                        "pass": v.get("pass", False)}
                                    for k, v in intervals.items()},
                      "intervals_pass": results["intervals_pass"]}, indent=1))
    (OUT / "projection_env.json").write_text(json.dumps(results, indent=1))

    # forecasts for 2027 (model per ship rule; intervals per variant) --------
    use_feats, use_src = (V3_FEATURES, "v3") if results["ship"]["verdict"] == "PASS" \
        else (None, "ridge11")
    cur = t[t.site == 2026].copy()
    full = t[t[TARGETS].notna().all(axis=1)]
    out_players = {}
    if use_src == "v3":
        pred_map = {}
        for tgt in TARGETS:
            rate = tgt in RATE_TARGETS
            mu_t, sd_t = env_forecast(envs[tgt], 2027)
            if rate:
                ytr_z = ((full[tgt] - mu_t) / (sd_t if sd_t > 0 else 1.0))
            else:
                ytr_z = full[tgt].astype(float)
            nf = t[(t.site <= 2024) & t[TARGETS].notna().all(axis=1)]
            nv = t[(t.site == 2025) & t[tgt].notna()]
            best_mae, lam_star = None, None
            for lam in LAMBDA_GRID:
                pz = ridge_fit_predict(nf[V3_FEATURES],
                                       ((nf[tgt] - mu_t) / (sd_t if sd_t > 0 and rate else 1.0)
                                        if rate else nf[tgt]).astype(float),
                                       nv[V3_FEATURES], lam)
                ok = nv[tgt].notna()
                p_raw = pz * sd_t + mu_t if rate else pz
                mae = float((nv.loc[ok, tgt] - p_raw[ok.to_numpy()]).abs().mean())
                if best_mae is None or mae < best_mae:
                    best_mae, lam_star = mae, lam
            pred_map[tgt] = ridge_fit_predict(full[V3_FEATURES], ytr_z,
                                              cur[V3_FEATURES], lam_star)
        for i, (_, row) in enumerate(cur.iterrows()):
            key = str(row["nba_pid"]) if pd.notna(row["nba_pid"]) else f"bdl{int(row['pid'])}"
            d = {"name": row["name"], "nba_pid": row["nba_pid"],
                 "bdl_pid": int(row["pid"]), "age": row["age"], "site": 2027,
                 "pts36": round(float(pred_map["next_pts36"][i]), 2),
                 "reb36": round(float(pred_map["next_reb36"][i]), 2),
                 "ast36": round(float(pred_map["next_ast36"][i]), 2),
                 "mpg": round(float(pred_map["next_min_pg"][i]), 1)}
            for k, tgt in (("pts36", "next_pts36"), ("reb36", "next_reb36"),
                           ("ast36", "next_ast36"), ("mpg", "next_min_pg")):
                iv = intervals.get(tgt, {})
                if iv.get("pass"):
                    d.setdefault("lo", {})[k] = round(d[k] - iv["q90"], 2)
                    d.setdefault("hi", {})[k] = round(d[k] + iv["q90"], 2)
            out_players[key] = d
        (OUT / "projections_2027_env.json").write_text(json.dumps({
            "as_of": "2026-11-08",
            "model": f"ridge env-normalized §14 (features {len(V3_FEATURES)})",
            "targets": "per-36 rates + mpg — forecast of stats, not value",
            "intervals": {k: v for k, v in intervals.items()},
            "players": out_players}, indent=1))
        print(f"forecasts written: {len(out_players)} players (§14)")
    return 0




def main_row() -> int:
    """§14b: per-row env normalization. Training targets are divided by
    their OWN next season's realized env (era removed from the training
    relation); predictions back-transform through the env-forecast rule,
    paying env-forecast error. Same folds/features/λ/gate as §14."""
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)
    ridge11 = json.loads((OUT / "projection_ridge.json").read_text())
    envs = {tgt: env_stats(t, tgt) for tgt in TARGETS}

    results = {"folds": {}, "composite": {}, "ship": {}}
    beats = 0
    resid = {tgt: {} for tgt in TARGETS}
    for S in FOLDS:
        train = t[(t.site <= S - 1) & t[TARGETS].notna().all(axis=1)].copy()
        test = t[t.site == S].copy()
        nest_fit = t[(t.site <= S - 2) & t[TARGETS].notna().all(axis=1)].copy()
        nest_val = t[t.site == S - 1].copy()
        fold = {}
        for tgt in TARGETS:
            rate = tgt in RATE_TARGETS
            # per-row env: the realized env of the row's OWN next season
            def row_env(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
                mus = df["site"].map(lambda s: envs[tgt].get(s + 1, (np.nan,))[0])
                sds = df["site"].map(lambda s: envs[tgt].get(s + 1, (0, np.nan))[1])
                return mus, sds
            def norm(df: pd.DataFrame) -> pd.Series:
                if not rate:
                    return df[tgt].astype(float)
                mus, sds = row_env(df)
                return ((df[tgt] - mus) / sds.replace(0, np.nan))
            tr_mu, tr_sd = env_forecast(envs[tgt], S)
            ytr = norm(train)
            best_mae, lam_star = None, None
            for lam in LAMBDA_GRID:
                pz = ridge_fit_predict(nest_fit[V3_FEATURES], norm(nest_fit),
                                       nest_val[V3_FEATURES], lam)
                if rate:
                    p_raw = pz * tr_sd + tr_mu
                else:
                    p_raw = pz
                ok = nest_val[tgt].notna()
                mae = float((nest_val.loc[ok, tgt] - p_raw[ok.to_numpy()]).abs().mean())
                if best_mae is None or mae < best_mae:
                    best_mae, lam_star = mae, lam
            pred_z = ridge_fit_predict(train[V3_FEATURES], ytr,
                                       test[V3_FEATURES], lam_star)
            p_raw = pred_z * tr_sd + tr_mu if rate else pred_z
            ok = test[tgt].notna()
            act = test.loc[ok, tgt].astype(float)
            ps = pd.Series(p_raw, index=test.index)[ok]
            r_ = (act - ps).to_numpy()
            resid[tgt][str(S)] = r_
            mae = float(np.abs(r_).mean())
            r = float(np.corrcoef(act, ps)[0, 1])
            r11 = ridge11["folds"][str(S)][tgt]["mae"]
            fold[tgt] = {"mae": round(mae, 3), "r": round(r, 3),
                         "lambda": lam_star,
                         "ratio_vs_ridge11": round(mae / r11, 4) if r11 else None}
        rs = [fold[t]["ratio_vs_ridge11"] for t in TARGETS if fold[t].get("ratio_vs_ridge11")]
        comp = round(float(np.mean(rs)), 4) if rs else None
        results["composite"][str(S)] = comp
        if comp is not None and comp <= SHIP_RATIO:
            beats += 1
        results["folds"][str(S)] = fold
    results["ship"] = {"folds_beaten": beats, "needed": 4,
                       "verdict": "PASS" if beats >= 4 else "FAIL",
                       "mode": "per-row env normalization (§14b)"}
    # one-back conformal on THESE residuals
    intervals = {}
    for tgt in TARGETS:
        covs, qs = [], {}
        for S in FOLDS:
            cal_keys = {str(S - 1)}
            cals = [resid[tgt][k] for k in cal_keys if k in resid[tgt]]
            if not cals:
                continue
            cal = np.concatenate(cals)
            if len(cal) < 50:
                continue
            q = float(np.quantile(np.abs(cal), NOMINAL))
            qs[str(S)] = q
            covs.append(float((np.abs(resid[tgt][str(S)]) <= q).mean()))
        mc = float(np.mean(covs)) if covs else None
        intervals[tgt] = {"variant": "one_back",
                          "coverage": round(mc, 4) if mc else None,
                          "q90": round(float(np.mean(list(qs.values()))), 2) if qs else None,
                          "pass": bool(mc and COVERAGE_BAND[0] <= mc <= COVERAGE_BAND[1])}
    results["intervals"] = intervals
    print(json.dumps({"composite": results["composite"], "ship": results["ship"],
                      "intervals": intervals}, indent=1))
    (OUT / "projection_env_row.json").write_text(json.dumps(results, indent=1))

    # 2027 forecasts on the §14b model + its intervals
    # per-row normalization needs the row's OWN next season's realized env —
    # site-2025 rows have none (2026 targets don't exist), so the §14b
    # training set ends at site 2024
    cur = t[t.site == 2026].copy()
    full = t[(t.site <= 2024) & t[TARGETS].notna().all(axis=1)].copy()
    pred_map = {}
    for tgt in TARGETS:
        rate = tgt in RATE_TARGETS
        mu_f, sd_f = env_forecast(envs[tgt], 2027)
        mus = full["site"].map(lambda s: envs[tgt].get(s + 1, (np.nan,))[0])
        sds = full["site"].map(lambda s: envs[tgt].get(s + 1, (0, np.nan))[1])
        ytr = ((full[tgt] - mus) / sds.replace(0, np.nan)) if rate else full[tgt].astype(float)
        nf = t[(t.site <= 2024) & t[TARGETS].notna().all(axis=1)].copy()
        nv = t[(t.site == 2025) & t[tgt].notna()].copy()
        best_mae, lam_star = None, None
        for lam in LAMBDA_GRID:
            pz = ridge_fit_predict(nf[V3_FEATURES], norm(nf), nv[V3_FEATURES], lam)
            p_raw = pz * sd_f + mu_f if rate else pz
            ok = nv[tgt].notna()
            mae = float((nv.loc[ok, tgt] - p_raw[ok.to_numpy()]).abs().mean())
            if best_mae is None or mae < best_mae:
                best_mae, lam_star = mae, lam
        pred_z = ridge_fit_predict(full[V3_FEATURES], ytr, cur[V3_FEATURES], lam_star)
        pred_map[tgt] = pred_z * sd_f + mu_f if rate else pred_z
    out_players = {}
    for i, (_, row) in enumerate(cur.iterrows()):
        key = str(row["nba_pid"]) if pd.notna(row["nba_pid"]) else f"bdl{int(row['pid'])}"
        d = {"name": row["name"], "nba_pid": row["nba_pid"],
             "bdl_pid": int(row["pid"]), "age": row["age"], "site": 2027,
             "pts36": round(float(pred_map["next_pts36"][i]), 2),
             "reb36": round(float(pred_map["next_reb36"][i]), 2),
             "ast36": round(float(pred_map["next_ast36"][i]), 2),
             "mpg": round(float(pred_map["next_min_pg"][i]), 1)}
        for k, tgt in (("pts36", "next_pts36"), ("reb36", "next_reb36"),
                       ("ast36", "next_ast36"), ("mpg", "next_min_pg")):
            iv = intervals.get(tgt, {})
            if iv.get("pass") and iv.get("q90"):
                d.setdefault("lo", {})[k] = round(d[k] - iv["q90"], 2)
                d.setdefault("hi", {})[k] = round(d[k] + iv["q90"], 2)
        out_players[key] = d
    (OUT / "projections_2027_row.json").write_text(json.dumps({
        "as_of": "2026-11-08",
        "model": "ridge per-row env-normalized §14b",
        "targets": "per-36 rates + mpg — forecast of stats, not value",
        "intervals": intervals, "players": out_players}, indent=1))
    print(f"forecasts written: {len(out_players)} players (§14b)")
    return 0




def attach_to_standing() -> int:
    """Ship rule: intervals attach to the STANDING model (the §11 ridge).
    Recompute its fold residuals (stored lambdas), run one-back conformal,
    and merge lo/hi into projections_2027.json (§11's point forecasts)."""
    t = pd.read_parquet(DERIVED / "modeling_table.parquet")
    t["min_tier"] = t["min_tier"].astype(float)
    r11 = json.loads((OUT / "projection_ridge.json").read_text())
    resid = {tgt: {} for tgt in TARGETS}
    for S in FOLDS:
        train = t[(t.site <= S - 1) & t[TARGETS].notna().all(axis=1)]
        test = t[t.site == S].copy()
        for tgt in TARGETS:
            lam = r11["folds"][str(S)]["lambdas"][tgt]
            pred = ridge_fit_predict(train[V2_FEATURES], train[tgt].astype(float),
                                     test[V2_FEATURES], lam)
            ok = test[tgt].notna()
            act = test.loc[ok, tgt].astype(float)
            ps = pd.Series(pred, index=test.index)[ok]
            resid[tgt][str(S)] = (act - ps).to_numpy()
    intervals = {}
    for tgt in TARGETS:
        covs, qs = [], {}
        for S in FOLDS:
            cals = [resid[tgt][k] for k in {str(S - 1)} if k in resid[tgt]]
            if not cals:
                continue
            cal = np.concatenate(cals)
            if len(cal) < 50:
                continue
            q = float(np.quantile(np.abs(cal), NOMINAL))
            qs[str(S)] = q
            covs.append(float((np.abs(resid[tgt][str(S)]) <= q).mean()))
        mc = float(np.mean(covs)) if covs else None
        intervals[tgt] = {"variant": "one_back", "coverage": round(mc, 4) if mc else None,
                          "q90": round(float(np.mean(list(qs.values()))), 2) if qs else None,
                          "pass": bool(mc and COVERAGE_BAND[0] <= mc <= COVERAGE_BAND[1])}
    print("standing-model intervals:", json.dumps(intervals))
    doc = json.loads((OUT / "projections_2027.json").read_text())
    for v in doc.get("players", {}).values():
        for k, tgt in (("pts36", "next_pts36"), ("reb36", "next_reb36"),
                       ("ast36", "next_ast36"), ("mpg", "next_min_pg")):
            iv = intervals.get(tgt, {})
            if iv.get("pass") and iv.get("q90") and isinstance(v.get(k), (int, float)):
                v.setdefault("lo", {})[k] = round(v[k] - iv["q90"], 2)
                v.setdefault("hi", {})[k] = round(v[k] + iv["q90"], 2)
    doc["intervals"] = intervals
    doc["model"] = "ridge+age+lags (§11) · 90% intervals: one-fold-back conformal (§14)"
    (OUT / "projections_2027.json").write_text(json.dumps(doc, indent=1))
    print("intervals attached to the standing model's forecasts")
    return 0


if __name__ == "__main__":
    raise SystemExit(attach_to_standing())
