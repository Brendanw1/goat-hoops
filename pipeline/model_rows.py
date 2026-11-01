"""model_rows.py — assemble the §1/§3 RAPM design rows from pbpstats-native data.

    python pipeline/model_rows.py --season 2025

Inputs (official NBA.com-log lineage — immune to ESPN's feed misordering):
  - get-possessions per team-season: points = 2×FG2M + 3×FG3M + made FTs
    ((N PTS) marker; validated MAE 0.16 vs ESPN box, 99.8% within ±2)
  - get-playing-time-distribution per player: on-court spans (minutes gate
    PASSED, 0.28 min)
§3: each ESPN FG shot is assigned — within its SHOOTER's team's possessions
    only (the two sources' clocks differ by ~1-3s, so cross-team containment
    at possession boundaries corrupts naive matching) — to the possession
    whose window contains its game-elapsed position; xPTS = Σ surface value
    (league FG% by distance bucket × point value) + made FTs × 1.0.
Outputs: data/derived/rapm_rows_{season}.parquet (pts response) and
data/derived/rapm_xrows_{season}.parquet (xpts response): {gid, team, home,
pts, ft, on10 (first 5 = home pids, last 5 = away)}.
"""

import argparse
import bisect
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT, MART  # noqa: E402

DERIVED = ROOT / "data" / "derived"
PT = Path.home() / "Projects" / "vt_baseball" / "hoops_mart" / "data" / "pbpstats"
BUCKETS = [(0, 4), (4, 9), (9, 14), (14, 19), (19, 22.5), (22.5, 24.5), (24.5, 100)]


def game_elapsed(period: int, clock: str) -> float:
    m, s = clock.split(":")
    remaining = int(m) * 60 + float(s)
    if period <= 4:
        return (period - 1) * 720 + (720 - remaining)
    return 4 * 720 + (period - 5) * 300 + (300 - remaining)


def play_elapsed(period: int, period_elapsed) -> float:
    """ESPN play position (period, elapsed-in-period) -> game seconds."""
    if period_elapsed is None or pd.isna(period_elapsed):
        return None
    if period <= 4:
        return (period - 1) * 720 + float(period_elapsed)
    return 4 * 720 + (period - 5) * 300 + float(period_elapsed)


def bucket_of(d: float) -> float:
    return next((hi for lo, hi in BUCKETS if lo < d <= hi), BUCKETS[-1][1])


def spans_for(pid: int, season: str, gap: float = 50.0) -> dict:
    """Merge every (player, team-stint) file; flag the player's side."""
    files = sorted(PT.glob(f"pt_{season}_{pid}.json.gz")) + \
            sorted(PT.glob(f"pt_{season}_{pid}_*.json.gz"))
    if not files:
        return {}
    out = {}
    for f in files:
        try:
            d = json.load(gzip.open(f))
        except Exception:
            continue
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
            home = not row.get("Opponent", "").strip().lower().startswith("at")
            out[row["GameId"]] = {"spans": [(a, b) for a, b in merged], "home": home}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    a = ap.parse_args()
    season_str = f"{a.season - 1}-{str(a.season)[2:]}"

    g = pd.read_parquet(MART / "games.parquet")
    XW = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
    g["home_x"] = g.home_abbr.map(lambda a: XW.get(a, a))
    games = g[(g.season_year == a.season) & (g.season_type == 2) & g.completed].copy()

    pbs = pd.read_parquet(PT / "games.parquet")
    pbs = pbs[(pbs.season == season_str) & (pbs.season_type == "Regular Season")]
    m = games.merge(pbs, left_on=["date_et", "home_x"],
                    right_on=["Date", "HomeTeamAbbreviation"], how="inner")
    home_of = {str(r.GameId): str(r.HomeTeamId) for r in pbs.itertuples()}
    espn2nba = {str(r.game_id): str(r.GameId) for r in m.itertuples()}
    print(f"games joined to the spine: {len(m)} of {len(games)}")

    # ---- possession rows + per-team windows from the pulls ------------------
    # the poss files' tid is nba.com's; ESPN's play stream uses ESPN team ids
    # — the bridge runs per game via the box's team ids and abbreviations
    poss_rows, wins_by_team = [], {}
    ft_pts = re.compile(r"free throw", re.I)
    pts_mark = re.compile(r"\(\d+ PTS\)")
    espn_tid_to_nba = {}
    for gr in m.itertuples():
        espn_tid_to_nba[(str(gr.game_id), str(gr.home_team_id))] = str(gr.HomeTeamId)
        espn_tid_to_nba[(str(gr.game_id), str(gr.away_team_id))] = str(gr.AwayTeamId)
    for f in sorted(PT.glob(f"poss_{season_str}_*.json.gz")):
        nba_tid = f.stem.split("_")[-1].replace(".json", "")
        for p in json.load(gzip.open(f)):
            gid_nba = str(p["GameId"])
            ft = sum(1 for line in (p.get("Events") or "").splitlines()
                     if ft_pts.search(line) and pts_mark.search(line))
            try:
                se = game_elapsed(int(p["Period"]), p["StartTime"])
                en = game_elapsed(int(p["Period"]), p["EndTime"])
            except (KeyError, ValueError):
                continue
            wins_by_team.setdefault((gid_nba, nba_tid), []).append((se, en, nba_tid))
            poss_rows.append({"gid": gid_nba, "team": nba_tid,
                              "home": home_of.get(gid_nba) == nba_tid,
                              "fg2m": p.get("FG2M") or 0, "fg3m": p.get("FG3M") or 0,
                              "ft": ft, "start": se, "end": en})
    pr = pd.DataFrame(poss_rows)
    pr["pts"] = 2 * pr.fg2m + 3 * pr.fg3m + pr.ft
    for k in wins_by_team:
        wins_by_team[k].sort()
    print(f"possession rows: {len(pr):,} ({pr.pts.sum():,.0f} points)")

    # ---- §3/§4 xPTS per possession, from their own Events text --------------
    ft_re = re.compile(r"free throw", re.I)
    mark = re.compile(r"\(\d+ PTS\)")
    TYPE_RULES = [("dunk", "Dunk"), ("layup", "Layup"), ("fade", "Fadeaway"),
                  ("hook", "Hook"), ("tip", "Tip"), ("pullup", "Pullup"),
                  ("floating", "Floating"), ("jump shot", "JumpShot")]
    def class_of(line):
        ll = line.lower()
        for pat, cls in TYPE_RULES:
            if pat in ll:
                return cls
        return "Other"
    # every FGA line carries its distance ("27' 3PT ..."); the §4 surface
    # (pooled 3-season FG% by distance bucket × value × type class, parsed
    # from the Events text itself) converts each FGA to an expected value;
    # made FTs count 1.0. All within pbpstats' own possession grouping — no
    # cross-source matching, immune to the misordering.
    FGA_RE = re.compile(r"(\d+)' ")
    class_rules = TYPE_RULES
    def class_of2(line):
        ll = line.lower()
        for pat, cls in class_rules:
            if pat in ll:
                return cls
        return "Other"
    rich = []
    for ssn in ("2022-23", "2023-24", "2024-25"):
        for f in sorted(PT.glob(f"poss_{ssn}_*.json.gz")):
            for p in json.load(gzip.open(f)):
                for line in (p.get("Events") or "").splitlines():
                    if ft_re.search(line.lower()): continue
                    mm = re.search(r"(\d+)' ", line)
                    if not mm: continue
                    rich.append((int(mm.group(1)), 3 if "3PT" in line else 2,
                                 class_of2(line), not line.startswith("MISS")))
    rt = pd.DataFrame(rich, columns=["dist", "val", "cls", "made"])
    rt["bucket"] = rt.dist.map(bucket_of)
    surf3 = rt.groupby(["bucket", "val", "cls"], observed=True).made.mean()
    surf2 = rt.groupby(["bucket", "val"], observed=True).made.mean()
    surf1 = rt.val.mean() / 2.0  # league-average FG% proxy (per-shot value/2)
    def xps_of(dd, v, cls):
        key3 = (bucket_of(dd), v, cls)
        if key3 in surf3.index:
            return float(surf3.loc[key3]) * v
        key2 = (bucket_of(dd), v)
        if key2 in surf2.index:
            return float(surf2.loc[key2]) * v
        return float(surf1) * v
    print(f"§4 surface: {len(surf3)} rich cells from {len(rt):,} FGA (3 seasons pooled)")
    ft_re = re.compile(r"free throw", re.I)
    mark = re.compile(r"\(\d+ PTS\)")
    nfga = 0
    xpts_by_key = {}
    for f in sorted(PT.glob(f"poss_{season_str}_*.json.gz")):
        tid = f.stem.split("_")[-1].replace(".json", "")
        for p in json.load(gzip.open(f)):
            gid = str(p["GameId"])
            x = 0.0
            for line in (p.get("Events") or "").splitlines():
                if ft_re.search(line.lower()):
                    continue
                mm = FGA_RE.search(line)
                if mm:
                    dd = int(mm.group(1))
                    v = 3 if "3PT" in line else 2
                    x += xps_of(dd, v, class_of2(line))
                    nfga += 1
            ft = sum(1 for line in (p.get("Events") or "").splitlines()
                     if ft_re.search(line) and mark.search(line))
            xpts_by_key[(gid, tid, game_elapsed(int(p["Period"]), p["StartTime"]))] = x + ft
    print(f"Events FGA parsed: {nfga:,} | xpts keys: {len(xpts_by_key):,}")
    pr["xpts"] = [xpts_by_key.get((r.gid, r.team, r.start)) for r in pr.itertuples()]

    # ---- intervals -> on10 --------------------------------------------------
    pids = sorted(int(f.stem.split("_")[-1].replace(".json", ""))
                  for f in PT.glob(f"pt_{season_str}_*.json.gz"))
    spans, home_flag = {}, {}
    for pid in pids:
        for gid, info in spans_for(pid, season_str).items():
            spans.setdefault(gid, {})[str(pid)] = info["spans"]
            home_flag[(str(pid), gid)] = info["home"]
    print(f"interval data: {len(spans):,} games, {len(pids)} players")

    # ---- emit rows ----------------------------------------------------------
    rows_pts, rows_x = [], []
    diag = [0]
    skipped = 0
    for r in pr.itertuples():
        game_spans = spans.get(r.gid, {})
        if not game_spans:
            skipped += 1
            continue
        h5, a5 = [], []
        for aid, sp in game_spans.items():
            covered = any(a2 <= r.start <= b2 or a2 <= r.end <= b2 or
                          (a2 <= r.start and r.end <= b2) for a2, b2 in sp)
            if covered:
                (h5 if home_flag.get((aid, r.gid), False) else a5).append(aid)
        if len(h5) != 5 or len(a5) != 5:
            skipped += 1
            continue
        on10 = sorted(h5) + sorted(a5)
        base = {"gid": r.gid, "team": r.team, "home": r.home, "ft": r.ft, "on10": on10}
        rows_pts.append({**base, "pts": r.pts})
        if r.xpts is not None:
            rows_x.append({**base, "pts": r.xpts})
        elif diag[0] < 4:
            diag[0] += 1
            near = [(k2, v2) for k2, v2 in xpts_acc.items()
                    if k2[0] == r.gid and k2[1] == r.team and abs(k2[2] - r.start) < 30]
            print(f"DIAG miss: {key} | near: {[(k[2], round(v,2)) for k, v in near[:3]]}")
    out_pts = pd.DataFrame(rows_pts)
    out_x = pd.DataFrame(rows_x)
    print(f"rows: pts {len(out_pts):,} | xpts {len(out_x):,} (skipped {skipped:,})")
    DERIVED.mkdir(parents=True, exist_ok=True)
    out_pts.to_parquet(DERIVED / f"rapm_rows_{a.season}.parquet", index=False)
    out_x.to_parquet(DERIVED / f"rapm_xrows_{a.season}.parquet", index=False)


if __name__ == "__main__":
    main()
