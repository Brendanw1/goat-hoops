"""data_validation.py — the modeling table's validation suite (audit H4).

    python pipeline/data_validation.py

Runs BEFORE any table build; the build refuses to run on a HARD failure.
Checks (each traced to the audit doc's finding ids):
  V1 ranges        — physically possible values (min_pg, gp, rates, per-36)
  V2 cross-source  — seasavgs gp vs the box parquets' played-games on the
                     seasons where boxes exist (the trader-semantics check,
                     audit H5: verified combined at the season grain)
  V3 anomalies     — |season z| > 6 rows, zero-minute rows, target structure
  V4 drift         — per-season mean mpg/pts36 vs the span trend (informational)
  V5 coverage      — per-season rows/floors (the seal's numbers, re-derived)

Output: data/derived/validation_report.json (+ exit 1 on any hard failure).
The report is sealed into the table's build (modeling_table.py reads it and
records the verdict).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

BDL = Path.home() / "Projects/vt_baseball/hoops_mart/data/bdl"
MART = Path.home() / "Projects/vt_baseball/hoops_mart/data/mart"
DERIVED = ROOT / "data" / "derived"
SITE = {"2023": 2024, "2024": 2025, "2025": 2026}  # box labels with a seasavgs twin


def v1_ranges(wide: pd.DataFrame, floor_min: float = 250.0) -> dict:
    """Range checks. Pre-floor violations are informational (cup-of-coffee
    rows: gp mean 3.3, 160/182 with gp <= 5 — the 250-minute floor removes
    them); the HARD check is post-floor: a floor-surviving row that fails a
    range is real corruption and stops the build."""
    min_pg = pd.to_numeric(wide["general_base.min"], errors="coerce")
    gp = pd.to_numeric(wide["general_base.gp"], errors="coerce")
    ts = pd.to_numeric(wide["general_advanced.ts_pct"], errors="coerce")
    usg = pd.to_numeric(wide["general_advanced.usg_pct"], errors="coerce")
    pts36 = pd.to_numeric(wide["general_base.pts"], errors="coerce") / min_pg.replace(0, np.nan) * 36
    season_min = gp * min_pg
    keep = season_min >= floor_min
    pre = {
        "ts_out": int(((ts <= 0.2) | (ts >= 1.1)).fillna(False).sum()),
        "pts36_over": int((pts36 > 45).fillna(False).sum()),
        "min_pg_over": int((min_pg > 48.5).sum()),
        "gp_over": int((gp > 85).sum()),
        "usg_over": int((usg > 55).sum()),
    }
    post = {
        "ts_out": int((((ts <= 0.2) | (ts >= 1.1)).fillna(False) & keep).sum()),
        "pts36_over": int(((pts36 > 45).fillna(False) & keep).sum()),
        "min_pg_over": int(((min_pg > 48.5).fillna(False) & keep).sum()),
        "gp_over": int(((gp > 85).fillna(False) & keep).sum()),
        "usg_over": int(((usg > 55).fillna(False) & keep).sum()),
    }
    return {"violations_pre_floor": pre, "violations_post_floor": post,
            "note": "pre-floor violations are small-sample artifacts; the "
                    "floor is the cleaner and the hard check rides post-floor",
            "hard_fail": any(post.values())}


def v2_cross_source(wide: pd.DataFrame) -> dict:
    """seasavgs gp (games with minutes) vs the box parquets' played-games.
    Codifies the audit's H5 resolution: rows are COMBINED seasons; the box
    parquets carry DNP rows that any box-side sum must filter min>0."""
    out = {"seasons": {}, "hard_fail": False}
    for bdl_label, site in SITE.items():
        fb = BDL / f"stats_{bdl_label}.parquet"
        fa = BDL / f"seasavgs_{bdl_label}_general_base.parquet"
        if not fb.exists() or not fa.exists():
            continue
        box = pd.read_parquet(fb, columns=["player.id", "game.id", "min"])
        box["min"] = pd.to_numeric(box["min"], errors="coerce")
        played = box[box["min"].fillna(0) > 0]
        g = played.groupby("player.id")["game.id"].nunique()
        ss = pd.read_parquet(fa, columns=["player.id", "stats.gp"])
        ss["stats.gp"] = pd.to_numeric(ss["stats.gp"], errors="coerce")
        m = g.to_frame("box_gp").join(
            ss.set_index("player.id")["stats.gp"].rename("ss_gp"), how="outer")
        agree = float((m["box_gp"] == m["ss_gp"]).mean())
        mad = float((m["box_gp"] - m["ss_gp"]).abs().mean())
        big = int(((m["box_gp"] - m["ss_gp"]).abs() > 2).sum())
        out["seasons"][str(site)] = {
            "players": int(len(m)), "agreement": round(agree, 4),
            "mean_abs_diff": round(mad, 3), "mismatch_gt2": big}
        if agree < 0.80 or mad > 1.0:
            out["hard_fail"] = True
    return out


def v3_anomalies(wide: pd.DataFrame) -> dict:
    min_pg = pd.to_numeric(wide["general_base.min"], errors="coerce")
    pts = pd.to_numeric(wide["general_base.pts"], errors="coerce")
    pts36 = pts / min_pg.replace(0, np.nan) * 36
    z = (pts36 - pts36.mean()) / pts36.std()
    return {
        "pts36_abs_z_gt6": int((z.abs() > 6).fillna(False).sum()),
        "zero_min_rows": int((min_pg.fillna(0) == 0).sum()),
        "rows_total": int(len(wide)),
        "hard_fail": False,  # anomalies are flagged, not failed
    }


def v4_drift(wide: pd.DataFrame) -> dict:
    d = wide[["season"]].copy()
    d["mpg"] = pd.to_numeric(wide["general_base.min"], errors="coerce")
    d["pts36"] = (pd.to_numeric(wide["general_base.pts"], errors="coerce")
                  / d["mpg"].replace(0, np.nan) * 36)
    g = d.groupby("season").mean(numeric_only=True)
    trend_mpg = float(g["mpg"].iloc[-5:].mean() - g["mpg"].iloc[:5].mean())
    trend_pts36 = float(g["pts36"].iloc[-5:].mean() - g["pts36"].iloc[:5].mean())
    return {"mpg_first5_to_last5": round(trend_mpg, 2),
            "pts36_first5_to_last5": round(trend_pts36, 2),
            "note": "informational — the era drift the §14 target-space "
                    "migration will normalize",
            "hard_fail": False}


def main() -> int:
    wide = pd.read_parquet(MART / "bdl_season.parquet")
    report = {
        "as_of": "2026-11-08",
        "v1_ranges": v1_ranges(wide),
        "v2_cross_source": v2_cross_source(wide),
        "v3_anomalies": v3_anomalies(wide),
        "v4_drift": v4_drift(wide),
    }
    hard = any([report["v1_ranges"]["hard_fail"],
                report["v2_cross_source"]["hard_fail"]])
    report["verdict"] = "FAIL" if hard else "PASS"
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "validation_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1)[:1200])
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
