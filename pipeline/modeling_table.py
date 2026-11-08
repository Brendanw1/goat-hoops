"""modeling_table.py — P4 foundation artifact #1 (PROJECTIONS-SCOPE §1).

    python pipeline/modeling_table.py

One row per player-season, site 2006-2026, from the joined wide table
(`data/mart/bdl_season.parquet`, bdl labels 2005-2025). Rate space is
per-36 and per-possession; features stored raw AND as season z-scores;
lags 1/2/3 and 2/3-season rolling means by player; targets are NEXT
season's per-36 rates, mpg, and games (consecutive seasons only). Minute
floor 250 (sensitivity at 100/400 reported in the seal). Retired players
are first-class training rows; the site bridge rides along (nba_pid) for
rendering only.

Outputs:
  data/derived/modeling_table.parquet
  data/derived/modeling_table_SEALED.json  (schema + coverage + floor
  sensitivity; sealed = the reads query this exact artifact)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import MART, ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
MIN_FLOOR = 250
SITES = range(2006, 2027)  # bdl labels 2005-2025

CORE = ("pts", "reb", "ast", "stl", "blk", "tov")
RATE_COLS = ["ts_pct", "usg_pct", "ast_pct", "oreb_pct", "dreb_pct",
             "off_rating", "def_rating", "net_rating", "pie", "efg_pct"]


def per36(row: pd.Series) -> dict:
    min_pg = float(row.get("general_base.min") or 0)
    if min_pg <= 0:
        return {f"{c}36": np.nan for c in CORE}
    return {f"{c}36": float(row.get(f"general_base.{c}") or 0) / min_pg * 36
            for c in CORE}


def main() -> int:
    wide = pd.read_parquet(MART / "bdl_season.parquet")
    wide["site"] = wide["season"] + 1
    wide = wide[wide["site"].isin(SITES)].copy()

    # base frame: identity + context + per-36 ---------------------------------
    base = wide[["bdl_pid", "nba_pid", "name", "site",
                 "general_base.gp", "general_base.min", "general_base.w_pct",
                 "general_advanced.age"]].copy()
    base.columns = ["pid", "nba_pid", "name", "site", "gp", "min_pg",
                    "w_pct", "age"]
    p36 = wide.apply(per36, axis=1, result_type="expand")
    base = pd.concat([base, p36], axis=1)
    base["season_min"] = base["gp"] * base["min_pg"]

    # rate features (raw) ------------------------------------------------------
    for c in RATE_COLS:
        col = f"general_advanced.{c}"
        if col in wide.columns:
            base[c] = pd.to_numeric(wide[col], errors="coerce")

    # raw tracking sources (§12b per-36 lags; v2 of the seal) ------------------
    for c in ("tracking_drives.drives", "tracking_possessions.touches",
              "tracking_possessions.paint_touches",
              "tracking_possessions.front_ct_touches",
              "tracking_defense.def_rim_fga",
              "tracking_speeddistance.dist_miles"):
        if c in wide.columns:
            base[c] = pd.to_numeric(wide[c], errors="coerce")

    # season z-scores for the core rates --------------------------------------
    zsrc = ["pts36", "reb36", "ast36", "ts_pct", "usg_pct", "ast_pct",
            "oreb_pct", "dreb_pct"]
    for c in zsrc:
        grp = base.groupby("site")[c]
        mu, sd = grp.transform("mean"), grp.transform("std")
        base[f"z_{c}"] = (base[c] - mu) / sd.replace(0, np.nan)

    # era index (linear), role tier -------------------------------------------
    base["era"] = base["site"] - 2006
    base["min_tier"] = pd.cut(base["min_pg"], [0, 15, 25, 32, 48],
                              labels=False)

    # lags + rolling means (by player, consecutive seasons only) --------------
    base = base.sort_values(["pid", "site"])
    g = base.groupby("pid")
    feat = ["pts36", "reb36", "ast36", "stl36", "blk36", "tov36",
            "ts_pct", "usg_pct", "ast_pct", "gp", "min_pg"]
    c1 = g["site"].diff().eq(1)          # this row follows the previous season
    c2 = g["site"].diff(2).eq(2)         # two consecutive steps back
    next_c = g["site"].shift(-1).sub(base["site"]).eq(1)  # next row follows
    for c in feat:
        base[f"lag1_{c}"] = g[c].shift(1).where(c1)
        base[f"lag2_{c}"] = g[c].shift(2).where(c2)
        base[f"rm2_{c}"] = ((g[c].shift(1) + g[c].shift(2)) / 2).where(c2)

    # targets: NEXT season (consecutive) --------------------------------------
    for c in ["pts36", "reb36", "ast36", "min_pg", "gp"]:
        base[f"next_{c}"] = g[c].shift(-1).where(next_c)

    # minute floor + sensitivity ----------------------------------------------
    floors = {}
    for f in (100, 250, 400):
        ok = base["season_min"] >= f
        rows = int(ok.sum())
        players = base[ok]["pid"].nunique()
        with_target = int(base.loc[ok, "next_pts36"].notna().sum())
        floors[str(f)] = {"rows": rows, "players": players,
                          "rows_with_target": with_target}
    table = base[base["season_min"] >= MIN_FLOOR].copy()

    DERIVED.mkdir(parents=True, exist_ok=True)
    table.to_parquet(DERIVED / "modeling_table.parquet", index=False)

    seal = {
        "grain": "one row per player-season, site 2006-2026",
        "source": "data/mart/bdl_season.parquet (BDL season-average pulls)",
        "minute_floor": MIN_FLOOR,
        "floor_sensitivity": floors,
        "rows": int(len(table)),
        "players": int(table["pid"].nunique()),
        "seasons": int(table["site"].nunique()),
        "rows_with_target": int(table["next_pts36"].notna().sum()),
        "bridge_coverage": float(table["nba_pid"].notna().mean()),
        "target_cols": ["next_pts36", "next_reb36", "next_ast36",
                        "next_min_pg", "next_gp"],
        "feature_families": ["per36 core", "advanced rates", "season z-scores",
                             "age/era/role", "lags 1/2", "rm2"],
        "notes": "rate space per-36; targets consecutive-season only; retired "
                 "players first-class; nba_pid = rendering bridge (not training)",
        "v2_note": "2026-11-08: raw tracking source columns added for §12b "
                   "(drives/touches/paint/front-ct/def_rim_fga/dist_miles); "
                   "§10/§11 feature sets unchanged and their reads remain valid",
        "sealed": "2026-11-08",
    }
    (DERIVED / "modeling_table_SEALED.json").write_text(json.dumps(seal, indent=1))
    print(json.dumps(seal, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
