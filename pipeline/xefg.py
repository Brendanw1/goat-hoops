"""§20 — per-shot make probability (zone, distance, outcome-neutral ESPN shot
families; no shooter identity) and player xeFG / shot-making. RESULTS-HOOPS
§20 fixes every rule; `--gate` runs the held-out test (fit 2025, score 2026).

    python pipeline/xefg.py --gate
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hoops_export import MART  # noqa: E402

GATE = Path(__file__).resolve().parents[1] / "data" / "derived" / "gate_xefg_20.json"
ZONES = ("rim", "paint", "mid", "c3", "ab3")
FINISH = (("dunk", "Dunk"), ("tip", "Tip"), ("layup", "Layup|Finger Roll"), ("hook", "Hook"))
ACTIONS = {"driving": "Driving", "running": "Running", "cutting": "Cutting", "pullup": "Pullup",
           "stepback": "Step Back", "turnaround": "Turnaround", "fadeaway": "Fade Away",
           "floating": "Floating", "alleyoop": "Alley Oop", "putback": "Putback"}
COLS = ["dist", "angle", "zone_i", "three", "finish_i", *ACTIONS]


def design(s: pd.DataFrame) -> pd.DataFrame:
    """Model features; 'Bank' / 'Reverse' / 'Finger Roll' descriptors never enter alone."""
    t = s.shot_type.fillna("")
    fin = np.select([t.str.contains(p) for _, p in FINISH], list(range(1, len(FINISH) + 1)), 0)
    x, y = s.x.to_numpy(float) - 25, s.y.to_numpy(float) - 1
    out = pd.DataFrame({"dist": np.hypot(x, y), "angle": np.abs(np.degrees(np.arctan2(x, np.maximum(y, 0.01)))),
                        "zone_i": s.zone.map({z: i for i, z in enumerate(ZONES)}).to_numpy(),
                        "three": (s.points_attempted == 3).to_numpy(int), "finish_i": fin}, index=s.index)
    for k, p in ACTIONS.items():
        out[k] = t.str.contains(p).to_numpy(int)
    return out


def fit(s: pd.DataFrame):
    from sklearn.ensemble import HistGradientBoostingClassifier
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=0,
                                       categorical_features=[COLS.index("zone_i"), COLS.index("finish_i")])
    return m.fit(design(s)[COLS], s.made.astype(int))


def _ll(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calib(p, y, bins=10) -> float:
    q = pd.qcut(p, bins, labels=False, duplicates="drop")
    d = pd.DataFrame({"p": p, "y": y, "q": q}).groupby("q").mean()
    return float((d.p - d.y).abs().max())


def gate(g: pd.DataFrame) -> dict:
    from creation import load_shots
    s = load_shots(g)
    tr, te = s[s.season_year == 2025], s[s.season_year == 2026]
    base = tr.groupby("zone").made.mean()
    pb = te.zone.map(base).to_numpy(float)
    pm = fit(tr).predict_proba(design(te)[COLS])[:, 1]
    y = te.made.to_numpy(int)
    lb, lm = _ll(y, pb), _ll(y, pm)
    d = pd.DataFrame({"g": te.game_id.to_numpy(), "d": lm - lb, "b": lb})
    per = d.groupby("g").agg(d=("d", "sum"), b=("b", "sum"), n=("d", "size"))
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(200):
        r = per.iloc[rng.integers(0, len(per), len(per))]
        boots.append(r.d.sum() / r.n.sum())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    rel = float((lm.mean() - lb.mean()) / lb.mean())
    cal = calib(pm, y)
    ok = bool(rel <= -0.01 and hi < 0 and cal <= 0.02)
    return {"n_train": int(len(tr)), "n_test": int(len(te)), "logloss_base": round(float(lb.mean()), 5),
            "logloss_model": round(float(lm.mean()), 5), "rel_change": round(rel, 4),
            "ci95_diff": [round(float(lo), 5), round(float(hi), 5)], "calib_max_gap": round(cal, 4),
            "calib_base": round(calib(pb, y), 4), "pass": ok}


def player_xefg(g: pd.DataFrame) -> pd.DataFrame:
    """Production: refit on every completed season (same spec), score every shot;
    per (season_year, athlete_id): xefg, smk (eFG − xEFG), sq_fga."""
    from creation import load_shots
    s = load_shots(g)
    m = fit(s[s.season_year < s.season_year.max()])  # completed seasons; the live one is scored only
    s = s.assign(p=m.predict_proba(design(s)[COLS])[:, 1])
    w = np.where(s.points_attempted == 3, 1.5, 1.0)
    s = s.assign(xv=s.p * w, av=s.made * w)
    a = s.groupby(["season_year", "shooter_id"]).agg(xefg=("xv", "mean"), efg_sh=("av", "mean"),
                                                     sq_fga=("xv", "size")).reset_index()
    return a.rename(columns={"shooter_id": "athlete_id"}).assign(smk=lambda d: d.efg_sh - d.xefg) \
        .drop(columns="efg_sh")


def _selfcheck() -> None:
    s = pd.DataFrame({"shot_type": ["Driving Finger Roll Layup", "Jump Shot Bank", "Running Pullup Jump Shot",
                                    "Alley Oop Dunk Shot"], "x": [25, 10, 40, 25], "y": [2, 10, 20, 1],
                      "zone": ["rim", "mid", "ab3", "rim"], "points_attempted": [2, 2, 3, 2]})
    d = design(s)
    assert list(d.finish_i) == [3, 0, 0, 1] and list(d.driving) == [1, 0, 0, 0], d
    assert list(d.pullup) == [0, 0, 1, 0] and list(d.running) == [0, 0, 1, 0] and d.alleyoop.iat[3] == 1
    assert abs(d.dist.iat[0] - 1) < 1e-9 and d.angle.iat[0] == 0
    assert abs(calib(np.array([.1] * 10 + [.9] * 10), np.array([0] * 9 + [1] + [1] * 9 + [0]), 2)) < 1e-9


if __name__ == "__main__":
    _selfcheck()
    if "--gate" in sys.argv:
        gm = pd.read_parquet(MART / "games.parquet")
        res = gate(gm[gm.completed])
        res["ran"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        GATE.write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
    else:
        print("selfcheck ok")
