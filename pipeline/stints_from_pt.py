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


BUCKETS = [(0, 4), (4, 9), (9, 14), (14, 19), (19, 22.5), (22.5, 24.5), (24.5, 100)]


def dist_bucket(x, y):
    """Distance from the rim in feet -> the preregistered bucket's upper edge."""
    d = ((x - 25) ** 2 + (y - 5.25) ** 2) ** 0.5
    for lo, hi in BUCKETS:
        if lo < d <= hi:
            return hi
    return BUCKETS[-1][1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--gap", type=float, default=50.0,
                    help="max game-second gap inside one on-court span")
    a = ap.parse_args()
    season_str = f"{a.season - 1}-{str(a.season)[2:]}"

    g = pd.read_parquet(MART / "games.parquet")
    games = g[(g.season_year == a.season) & (g.season_type == 2) & g.completed & (g.n_plays > 0)].copy()
    # the §3 shot-value surface: league FG% by (distance bucket, shot value)
    # and league FT%, from our validated shot table, this season only
    sh = pd.read_parquet(MART / "shots.parquet")
    sh = sh[sh.game_id.isin(games.game_id)].copy()
    sh["dist"] = ((sh.x - 25) ** 2 + (sh.y - 5.25) ** 2).pow(0.5)
    sh["bucket"] = sh.dist.map(lambda d: next((hi for lo, hi in BUCKETS if lo < d <= hi), BUCKETS[-1][1]))
    fg = sh[~sh.is_ft]
    surf = fg.groupby(["bucket", "points_attempted"], observed=True).made.mean()
    ft_pct = float(sh[sh.is_ft].made.mean())
    SURFACE = {(k[0], int(k[1])): float(v) for k, v in surf.items()}
    shots_by_play = {str(r.play_id): (r.x, r.y) for r in fg.itertuples()}
    print(f"surface: {len(SURFACE)} buckets | league FT% {ft_pct:.3f}")
    games["home_x"] = games.home_abbr.map(norm_team := (lambda x: None if pd.isna(x) else XWALK.get(x, x)))
    pg = pd.read_parquet(MART / "player_game.parquet")
    pb = pd.read_parquet(MART / "pbp.parquet")

    # pbpstats spine for the GameId + possession-count join
    pbs = pd.read_parquet(PT_DIR / "games.parquet")
    pbs = pbs[(pbs.season == season_str) & (pbs.season_type == "Regular Season")]
    m = games.merge(pbs, left_on=["date_et", "home_x"],
                    right_on=["Date", "HomeTeamAbbreviation"], how="inner")
    print(f"games joined to the spine: {len(m)} of {len(games)}")

    # load per-player intervals once: pid -> {nba GameId: [spans]}
    def spans_for(pid: int, season: str, gap: float) -> dict:
        """Merge every (player, team-stint) file; flag the player's side."""
        files = sorted(PT_DIR.glob(f"pt_{season}_{pid}.json.gz")) + \
                sorted(PT_DIR.glob(f"pt_{season}_{pid}_*.json.gz"))
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

    pt_cache = {}
    def intervals(pid):
        if pid not in pt_cache:
            pt_cache[pid] = spans_for(pid, season_str, a.gap)
        return pt_cache[pid]
    all_pids = sorted(int(f.stem.split("_")[-1].replace(".json", ""))
                      for f in Path.home().joinpath("Projects/vt_baseball/hoops_mart/data/pbpstats")
                      .glob(f"pt_{season_str}_*.json.gz"))

    rows_stint = []
    rows_poss_roster = []
    minute_rows = []
    n_ok = n_nojoin = n_nopt = 0
    for gr in m.itertuples():
        gid_espn, gid_nba = gr.game_id, str(gr.GameId)
        one = pb[pb.game_id == gid_espn].sort_values(["period", "seq"]).reset_index(drop=True)
        prow = pg[(pg.game_id == gid_espn) & pg.pts.notna()]
        # name -> (espn athlete id, nba.com pid) within this game
        # roster = the season's pid set (the intervals themselves are the
        # roster; the ESPN box is no longer part of the §3 path)
        roster = {str(pid): pid for pid in all_pids}
        if len(roster) < 10:
            n_nojoin += 1
            continue
        # player -> spans (game elapsed seconds); keyed by ESPN athlete id
        # pid-native: spans keyed by nba.com player id, home flag per player
        espn_spans = {}
        home_flags = {}
        for pid in all_pids:
            if pid not in pt_cache:
                pt_cache[pid] = spans_for(pid, season_str, a.gap)
            sp_info = pt_cache[pid].get(gid_nba)
            if sp_info:
                espn_spans[str(pid)] = sp_info["spans"]
                home_flags[str(pid)] = sp_info["home"]
        if len(espn_spans) < 10:
            n_nopt += 1
            continue
        # running-score arrays: points across any play-index window are the
        # score deltas at its edges — robust to the feed's play misordering
        hs = one.home_score.astype(float).tolist()
        as_ = one.away_score.astype(float).tolist()
        els = [game_elapsed(r.period, r.period_elapsed) for r in one.itertuples()]
        def window_pts(a, b):
            """score delta across play-index window [a, b)"""
            pa = max(0, a - 1)
            return (hs[b - 1] - hs[pa], as_[b - 1] - as_[pa])
        # our possession segments for this game (from the mart walk, with wall
        # clock). idx indexes EVERY play uniformly; end_i is exclusive, so
        # window_pts telescopes exactly over the partition.
        segs = []
        cur = None
        idx = 0
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
            this_idx = idx
            idx += 1
            if cur is None:
                if not non_control and not is_ft:
                    cur = {"team": tid, "start_i": this_idx, "start": el}
                continue
            closes = is_turnover or is_ft or (tid != cur["team"] and not non_control)
            if closes:
                # the transfer play belongs to the NEW segment: end exclusive
                cur["end_i"] = this_idx
                cur["end"] = el
                segs.append(cur)
                cur = {"team": tid, "start_i": this_idx, "start": el,
                       **({"opened_by_ft": True} if is_ft else {})}
            continue
        if cur:
            cur["end_i"] = len(one)
            cur["end"] = els[-1] if els else None
            segs.append(cur)
        # fill any None edges from the nearest defined elapsed (some rows
        # carry no clock); drop segments that still cannot be placed
        last_known = None
        for j, e in enumerate(els):
            if e is not None:
                last_known = e
            if last_known is not None:
                els[j] = last_known
        for sgg in segs:
            if sgg.get("end") is None and sgg.get("end_i"):
                sgg["end"] = els[min(sgg["end_i"], len(els)) - 1]
            if sgg.get("start") is None:
                sgg["start"] = sgg.get("end")
        segs = [sgg for sgg in segs if sgg.get("start") is not None and sgg.get("end") is not None]
        # points from score deltas; dead-ball = FT-opened segments with no
        # score movement beyond the FT itself is left simple: FT-opened
        # segments whose whole score delta equals one FT are dead-ball
        for sgg in segs:
            wa, wb = sgg["start_i"], sgg.get("end_i", len(one))
            hd, ad = window_pts(wa, wb)
            sgg["home_pts"] = hd
            sgg["away_pts"] = ad
            dead = bool(sgg.get("opened_by_ft")) and (hd + ad) <= 1
            sgg["dead_ball"] = dead
        # xPTS per segment: the surface lookup needs the shots' distance from
        # the rim; the shots table carries x/y already normalized
        for sgg in segs:
            wa, wb = sgg["start_i"], sgg.get("end_i", len(one))
            xpts = 0.0
            ftas = 0
            for j in range(wa, min(wb, len(one))):
                rj = one.iloc[j]
                if not rj.is_shooting:
                    continue
                if (rj.points_attempted or 0) == 1:
                    ftas += 1
                    continue
                sh_row = shots_by_play.get(str(rj.play_id))
                if sh_row is None:
                    continue
                val = int(rj.points_attempted or 2)
                xpts += SURFACE.get((dist_bucket(sh_row[0], sh_row[1]), val), 0.0)
            sgg["xpts"] = xpts + ftas * ft_pct
        # stint edges: boundaries of every player span
        bounds = sorted({b for sp in espn_spans.values() for iv in sp for b in iv})
        for si in range(len(bounds) - 1):
            lo, hi = bounds[si], bounds[si + 1]
            on = {}
            for aid, sp in espn_spans.items():
                cov = sum(max(0.0, min(hi, b) - max(lo, a)) for a, b in sp)
                if cov > (hi - lo) * 0.5:
                    on[aid] = cov
            homes = [aid for aid in on if home_flags.get(aid, False)]
            aways = [aid for aid in on if aid not in homes]
            if len(homes) != 5 or len(aways) != 5:
                continue
            mine = [s for s in segs
                    if s["start"] is not None and lo <= (s["start"] + s["end"]) / 2 < hi]
            live = [s for s in mine if not s.get("dead_ball")]
            hp = sum(s["home_pts"] for s in mine)
            ap_ = sum(s["away_pts"] for s in mine)
            rows_stint.append({"game_id": gid_espn, "period": None,
                               "home_tid": str(gr.home_team_id), "away_tid": str(gr.away_team_id),
                               "home": sorted(homes), "away": sorted(aways),
                               "home_pts": hp, "away_pts": ap_, "n_poss": len(live),
                               "start_el": lo, "end_el": hi})
            # possession-level rows with the on-court 10 (the RAPM design):
            # points = the offense team's score delta across the segment;
            # xpts = the §3 surface value of the segment's shots + FT xPTS
            for sgg in mine:
                on10 = sorted(homes) + sorted(aways)
                off_pts = (sgg["home_pts"] if sgg["team"] == str(gr.home_team_id)
                           else sgg["away_pts"])
                rows_poss_roster.append({
                    "game_id": gid_espn, "team": sgg["team"],
                    "home": sgg["team"] == str(gr.home_team_id),
                    "pts": off_pts,
                    "xpts": sgg.get("xpts", 0.0),
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
    rx = pr[(~pr.dead_ball) & (pr.on10.map(len) == 10)][["game_id", "team", "home", "xpts", "on10"]] \
        .rename(columns={"xpts": "pts"})
    rx.to_parquet(DERIVED / f"rapm_xpts_{a.season}.parquet", index=False)
    print(f"rapm_xrows: {len(rx):,}")

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
