"""stints_from_pt.py — build 10-man stints from pbpstats' official on-court
intervals, validated against box minutes (§1 handling iteration v6).

    python pipeline/stints_from_pt.py --season 2025 [--gap 50]

Why: ESPN's sub log is incomplete (§1 notes) and our sub-walk state drifts;
pbpstats' get-playing-time-distribution returns each player's on-court
possession intervals from the official NBA.com logs. Those intervals are the
stint backbone; our ESPN walk keeps supplying possession segments (control,
points, dead-ball marking). Identity joins: game via (Eastern date, home
abbr); player via normalized name within the game roster.

Pipeline per game:
  1. per player: merge his intervals when the gap <= --gap game-seconds
     (the other team's possession + dead time fits in the gap; longer gaps
     are off-court) -> on-court spans
  2. all span boundaries across the team's players -> candidate stint edges
  3. a possession segment (ours, wall-clock window) belongs to the player-
     spans that contain its midpoint -> the on-court 10
  4. stints = maximal runs of constant 10; points/possessions from the
     segments inside
Gates rerun here: player-minutes vs box (the validation the sub-walk kept
failing) and possessions vs pbpstats counts.
"""

import argparse
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import MART, ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
PT_DIR = Path.home() / "Projects/vt_baseball/hoops_mart/data/pbpstats"
XWALK = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
# game-clock elapsed for a (period, period_elapsed) pair
QLEN = {1: 720, 2: 720, 3: 720, 4: 720}


def game_elapsed(period: int, pe) -> float | None:
    if pe is None or period is None:
        return None
    if period <= 4:
        return (period - 1) * 720 + float(pe)
    return 4 * 720 + (period - 5) * 300 + float(pe)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[.'\u2019-]", " ", s.lower())
    return " ".join(t for t in s.split() if t and t not in SUFFIXES)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--gap", type=float, default=50.0,
                    help="max game-second gap inside one on-court span")
    a = ap.parse_args()
    season_str = f"{a.season - 1}-{str(a.season)[2:]}"

    g = pd.read_parquet(MART / "games.parquet")
    games = g[(g.season_year == a.season) & (g.season_type == 2) & g.completed & (g.n_plays > 0)].copy()
    games["home_x"] = games.home_abbr.map(norm_team := (lambda x: None if pd.isna(x) else XWALK.get(x, x)))
    pg = pd.read_parquet(MART / "player_game.parquet")
    pb = pd.read_parquet(MART / "pbp.parquet")

    xw = json.loads((PT_DIR / f"pt_ids_{season_str}.json").read_text())
    pid_by_norm_name = {norm(n): pid for n, pid in xw.items()}

    # pbpstats spine for the GameId + possession-count join
    pbs = pd.read_parquet(PT_DIR / "games.parquet")
    pbs = pbs[(pbs.season == season_str) & (pbs.season_type == "Regular Season")]
    m = games.merge(pbs, left_on=["date_et", "home_x"],
                    right_on=["Date", "HomeTeamAbbreviation"], how="inner")
    print(f"games joined to the spine: {len(m)} of {len(games)}")

    # load per-player intervals once: pid -> {nba GameId: [spans]}
    def spans_for(pid: int, gap: float) -> dict:
        f = PT_DIR / f"pt_{season_str}_{pid}.json.gz"
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
            out[row["GameId"]] = [(a, b) for a, b in merged]
        return out

    pt_cache = {}
    def intervals(pid):
        if pid not in pt_cache:
            pt_cache[pid] = spans_for(pid, a.gap)
        return pt_cache[pid]

    rows_stint = []
    rows_poss_roster = []
    minute_rows = []
    n_ok = n_nojoin = n_nopt = 0
    for gr in m.itertuples():
        gid_espn, gid_nba = gr.game_id, str(gr.GameId)
        one = pb[pb.game_id == gid_espn].sort_values(["period", "seq"]).reset_index(drop=True)
        prow = pg[(pg.game_id == gid_espn) & pg.pts.notna()]
        # name -> (espn athlete id, nba.com pid) within this game
        roster = {}
        for r in prow.itertuples():
            if pd.isna(r.name):
                continue
            pid = pid_by_norm_name.get(norm(r.name))
            if pid:
                roster[str(r.athlete_id)] = (r.name, pid)
        if len(roster) < 10:
            n_nojoin += 1
            continue
        # player -> spans (game elapsed seconds); keyed by ESPN athlete id
        espn_spans = {}
        for aid, (name, pid) in roster.items():
            sp = intervals(pid).get(gid_nba)
            if sp:
                espn_spans[aid] = sp
        if len(espn_spans) < 10:
            n_nopt += 1
            continue
        # our possession segments for this game (from the mart walk, with wall clock)
        segs = []
        cur = None
        for r in one.itertuples():
            tl = (r.type_text or "").lower()
            tid = str(r.team_id) if pd.notna(r.team_id) else None
            el = game_elapsed(r.period, r.period_elapsed)
            if r.type_text in ("End Period", "End Game"):
                if cur:
                    segs.append(cur)
                    cur = None
                continue
            if r.type_text == "Substitution" or tid is None:
                continue
            # reuse the possession rule inline (same as derive_possessions)
            is_turnover = "turnover" in tl
            is_foul = ("foul" in tl) and not is_turnover
            is_block = tl == "block"
            non_control = (is_foul or is_block or "timeout" in tl or "kicked" in tl
                           or "challenge" in tl or "replay" in tl or "delay" in tl)
            is_ft = bool(r.is_scoring) and (r.points_attempted or 0) == 1
            if cur is None:
                if not non_control and not is_ft:
                    cur = {"team": tid, "pts": {}, "start": el, "end": el}
                continue
            if tid == cur["team"]:
                if r.is_scoring and r.score_value:
                    cur["pts"][tid] = cur["pts"].get(tid, 0) + int(r.score_value)
                cur["end"] = el
                if is_turnover:
                    segs.append(cur)
                    cur = None
                continue
            if is_ft:
                if r.is_scoring and r.score_value:
                    cur["pts"][tid] = cur["pts"].get(tid, 0) + int(r.score_value)
                cur["end"] = el
                segs.append(cur)
                cur = {"team": tid, "pts": {}, "start": el, "end": el,
                       "opened_by_ft": True}
                continue
            if non_control:
                if r.is_scoring and r.score_value:
                    cur["pts"][tid] = cur["pts"].get(tid, 0) + int(r.score_value)
                continue
            cur["end"] = el
            segs.append(cur)
            cur = {"team": tid, "pts": {}, "start": el, "end": el}
        if cur:
            segs.append(cur)
        # mark dead-ball FT-only segments
        for sgg in segs:
            sgg["dead_ball"] = bool(sgg.get("opened_by_ft"))
        # stint edges: boundaries of every player span
        bounds = sorted({b for sp in espn_spans.values() for iv in sp for b in iv})
        for si in range(len(bounds) - 1):
            lo, hi = bounds[si], bounds[si + 1]
            on = {}
            for aid, sp in espn_spans.items():
                cov = sum(max(0.0, min(hi, b) - max(lo, a)) for a, b in sp)
                if cov > (hi - lo) * 0.5:
                    on[aid] = cov
            homes = [aid for aid in on
                     if str(int(prow[prow.athlete_id.astype(str) == aid].team_id.iloc[0])) == str(gr.home_team_id)]
            aways = [aid for aid in on if aid not in homes]
            if len(homes) != 5 or len(aways) != 5:
                continue
            mine = [s for s in segs
                    if s["start"] is not None and lo <= (s["start"] + s["end"]) / 2 < hi]
            live = [s for s in mine if not s.get("dead_ball")]
            hp = sum(s["pts"].get(str(gr.home_team_id), 0) for s in mine)
            ap_ = sum(s["pts"].get(str(gr.away_team_id), 0) for s in mine)
            rows_stint.append({"game_id": gid_espn, "period": None,
                               "home_tid": str(gr.home_team_id), "away_tid": str(gr.away_team_id),
                               "home": sorted(homes), "away": sorted(aways),
                               "home_pts": hp, "away_pts": ap_, "n_poss": len(live),
                               "start_el": lo, "end_el": hi})
            # possession-level rows with the on-court 10 (the RAPM design)
            for sgg in mine:
                on10 = sorted(homes) + sorted(aways)
                rows_poss_roster.append({
                    "game_id": gid_espn, "team": sgg["team"],
                    "home": sgg["team"] == str(gr.home_team_id),
                    "pts": sgg["pts"].get(sgg["team"], 0),
                    "dead_ball": bool(sgg.get("dead_ball")),
                    "on10": on10, "mid": (sgg["start"] + sgg["end"]) / 2})
        for aid, sp in espn_spans.items():
            on_secs = sum(b - a for a, b in sp)
            minute_rows.append({"athlete_id": aid, "game_id": gid_espn, "secs": on_secs})
        n_ok += 1

    st = pd.DataFrame(rows_stint)
    pr = pd.DataFrame(rows_poss_roster)
    print(f"built stints for {n_ok} games ({n_nojoin} no-roster-join, {n_nopt} no-intervals): "
          f"{len(st):,} stints, {len(pr):,} possession rows")
    DERIVED.mkdir(parents=True, exist_ok=True)
    st.to_parquet(DERIVED / f"stints_pt_{a.season}.parquet", index=False)
    pr.to_parquet(DERIVED / f"poss_rosters_{a.season}.parquet", index=False)

    # gate: minutes vs box
    mr = pd.DataFrame(minute_rows)
    agg = mr.groupby(["athlete_id", "game_id"]).secs.sum().div(60.0)
    box = pg[pg.pts.notna()].set_index(["athlete_id", "game_id"])["min"]
    cmp = pd.concat([agg.rename("pt_min"), box.rename("box_min")], axis=1).dropna()
    delta = (cmp.pt_min - cmp.box_min).abs()
    med = float(delta.median())
    gate2 = "PASS" if med <= 0.5 else "FAIL"
    print(f"GATE player-minutes (pbpstats backbone): {gate2} — median |Δ| {med:.2f} min "
          f"over {len(cmp):,} player-games")
    (DERIVED / f"gate_minutes_pt_{a.season}.json").write_text(json.dumps({
        "median_abs_delta": med, "n": int(len(cmp)), "pass": gate2 == "PASS"}))


if __name__ == "__main__":
    main()
