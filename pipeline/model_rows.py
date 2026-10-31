"""model_rows.py — assemble the §1 RAPM design rows from pbpstats-native data.

    python pipeline/model_rows.py --season 2025

Inputs (all from the official NBA.com-log lineage, immune to ESPN's feed
misordering — see RESULTS-HOOPS §1 notes):
  - get-possessions per team-season (points = 2×FG2M + 3×FG3M + made FTs;
    made FTs are Events lines carrying a "(N PTS)" scoring marker — validated
    MAE 0.16 points vs ESPN box scores, 99.8% within ±2)
  - get-playing-time-distribution per player (on-court spans per game;
    minutes gate PASSED, median |Δ| 0.28 min)
Output: data/derived/rapm_rows_{season}.parquet — one row per offensive
possession: {gid, team, home, pts, on10 (first 5 = home pids, last 5 = away)}.
"""

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
PT = Path.home() / "Projects" / "vt_baseball" / "hoops_mart" / "data" / "pbpstats"
QLEN = {1: 720, 2: 720, 3: 720, 4: 720}


def game_elapsed(period: int, clock: str) -> float:
    """Period + 'MM:SS' remaining -> seconds from game start."""
    m, s = clock.split(":")
    remaining = int(m) * 60 + float(s)
    if period <= 4:
        return (period - 1) * 720 + (720 - remaining)
    return 4 * 720 + (period - 5) * 300 + (300 - remaining)


def spans_for(pid: int, season: str, gap: float = 50.0) -> dict:
    f = PT / f"pt_{season}_{pid}.json.gz"
    if not f.exists():
        return {}
    try:
        d = json.load(gzip.open(f))
    except Exception:
        return {}
    out = {}
    for row in d.get("results", []):
        ivs = sorted((float(p["StartTime"]), float(p["EndTime"]))
                     for p in row.get("Possessions", []) if p.get("EndTime") is not None)
        if not ivs:
            continue
        merged = [list(ivs[0])]
        for st, en in ivs[1:]:
            if st - merged[-1][1] <= gap:
                merged[-1][1] = max(merged[-1][1], en)
            else:
                merged.append([st, en])
        # the player's side: " at X" = away, "vs X" = home (their team is the
        # other side of the named opponent)
        home = not row.get("Opponent", "").strip().lower().startswith("at")
        out[row["GameId"]] = {"spans": [(a, b) for a, b in merged], "home": home}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    a = ap.parse_args()
    season_str = f"{a.season - 1}-{str(a.season)[2:]}"

    # game -> home tid (from the pbpstats spine joined to nothing else — the
    # possessions' Opponent field plus the two team pulls give the sides; the
    # spine carries HomeTeamId directly per GameId)
    pbs = pd.read_parquet(PT / "games.parquet")
    pbs = pbs[(pbs.season == season_str) & (pbs.season_type == "Regular Season")]
    home_of = {str(r.GameId): str(r.HomeTeamId) for r in pbs.itertuples()}

    ft_pts = re.compile(r"free throw", re.I)
    pts_mark = re.compile(r"\(\d+ PTS\)")
    poss_rows = []
    span_cache = {}
    for f in sorted(PT.glob(f"poss_{season_str}_*.json.gz")):
        tid = f.stem.split("_")[-1].replace(".json", "")
        for p in json.load(gzip.open(f)):
            gid = str(p["GameId"])
            ft = sum(1 for line in (p.get("Events") or "").splitlines()
                     if ft_pts.search(line) and pts_mark.search(line))
            pts = 2 * (p.get("FG2M") or 0) + 3 * (p.get("FG3M") or 0) + ft
            try:
                mid = (game_elapsed(int(p["Period"]), p["StartTime"])
                       + game_elapsed(int(p["Period"]), p["EndTime"])) / 2
            except (KeyError, ValueError):
                continue
            poss_rows.append({"gid": gid, "team": tid, "pts": pts, "mid": mid,
                              "home": home_of.get(gid) == tid})
    pr = pd.DataFrame(poss_rows)
    print(f"possession rows: {len(pr):,} ({pr.pts.sum():,.0f} points)")

    # intervals per pid, per game
    pids = sorted({pid for f in PT.glob(f"pt_{season_str}_*.json.gz")
                   for pid in [int(f.stem.split("_")[-1].replace(".json", ""))]})
    spans = {}
    home_flag = {}
    for pid in pids:
        for gid, info in spans_for(pid, season_str).items():
            spans.setdefault(gid, {})[str(pid)] = info["spans"]
            home_flag[(str(pid), gid)] = info["home"]
    print(f"interval data: {len(spans):,} games, {len(pids)} players")

    rows = []
    skipped = 0
    for r in pr.itertuples():
        game_spans = spans.get(r.gid, {})
        if not game_spans:
            skipped += 1
            continue
        h5, a5 = [], []
        for aid, sp in game_spans.items():
            if any(a <= r.mid <= b for a, b in sp):
                is_home = home_flag.get((aid, r.gid), home_of.get(r.gid) == r.team)
                (h5 if is_home else a5).append(aid)
        if len(h5) == 5 and len(a5) == 5:
            rows.append({"gid": r.gid, "team": r.team, "home": r.home, "pts": r.pts,
                         "on10": sorted(h5) + sorted(a5)})
        else:
            skipped += 1
    out = pd.DataFrame(rows)
    print(f"model rows: {len(out):,} ({skipped:,} possessions skipped — windows without exact 5v5)")
    DERIVED.mkdir(parents=True, exist_ok=True)
    out.to_parquet(DERIVED / f"rapm_rows_{a.season}.parquet", index=False)


if __name__ == "__main__":
    main()
