"""possessions.py — derive possession segments and on-court stints from ESPN PBP.

    python pipeline/possessions.py            # 2024-25 regular season (§1)
    python pipeline/possessions.py --season 2025

Implements §1's fixed rules (RESULTS-HOOPS.md), then runs the handling gates
BEFORE anything downstream consumes the tables.

Possession rule (the part that took iteration — see RESULTS-HOOPS §1 notes):
- possession = one team's control segment. Control transfers on defensive
  rebound, turnover by the offense, any other opponent-controlled play
  (which is how a made FG's possession ends — the opponent's inbound), and
  period start. Non-control events: fouls, blocks, timeouts, kicked balls,
  challenges/replays/delays, substitutions.
- Free throws by the team NOT in control are the feed's two awkward cases:
  dead-ball FTs (technical/flagrant) and misordered foul blocks (ESPN places
  the foul+FT block AFTER the next possession's made basket). Either way the
  FT never opens a segment: its points attach to the interrupted segment,
  the segment closes, and the ball's next owner is remembered — the
  interrupted offense after a technical, the FT shooter otherwise — so the
  next control event by that team REOPENS the same segment (one possession,
  not two). Implementation: the closed segment is held in `held` until the
  next control event decides: restore, or commit.

Gates: derived per-team-game possessions vs pbpstats' independent counts
(>=95% within ±2, MAE < 1.5); player stint-minutes vs box MIN (median |Δ|
<= 0.5). Gate results print and write data/derived/gate_*.json.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import MART, ROOT  # noqa: E402

DERIVED = ROOT / "data" / "derived"
XWALK = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}


def norm_team(abbr):
    return None if pd.isna(abbr) else XWALK.get(abbr, abbr)


def derive_possessions(periods, seqs, types, tids, is_scoring, pts_att, score_val):
    """Play arrays -> possession segments [{team, pts:dict, start_i, end_i}]."""
    n = len(types)
    poss, cur = [], None
    held, pending_return = None, None   # closed segment awaiting its ball owner

    def commit():
        nonlocal held
        if held is not None:
            poss.append(held)
            held = None

    def close(i, hold=False):
        nonlocal cur, held
        if cur is not None:
            cur["end_i"] = i
            if hold:
                held = cur
            else:
                poss.append(cur)
            cur = None

    for i in range(n):
        tl = types[i].lower()
        tid = tids[i]
        if types[i] in ("End Period", "End Game"):
            if held is not None:
                commit()
            close(i)
            continue
        if types[i] == "Substitution" or tid is None:
            continue
        is_turnover = "turnover" in tl
        is_foul = ("foul" in tl) and not is_turnover
        is_block = tl == "block"
        non_control = (is_foul or is_block or "timeout" in tl or "kicked" in tl
                       or "challenge" in tl or "replay" in tl or "delay" in tl)
        is_ft = bool(is_scoring[i]) and (pts_att[i] or 0) == 1

        def add_pts(bucket, team, val):
            if val:
                bucket[team] = bucket.get(team, 0) + int(val)

        is_turnover = is_turnover  # (named above)
        if cur is None:
            if held is not None and pending_return == tid and not non_control and not is_ft:
                cur = held
                held = None
                pending_return = None
            elif not non_control and not is_ft:
                commit()
                cur = {"team": tid, "pts": {}, "start_i": i}
            continue

        if tid == cur["team"]:
            add_pts(cur["pts"], tid, score_val[i] if is_scoring[i] else 0)
            if is_turnover:
                close(i)
            continue

        # tid != cur team
        if is_ft:
            # misordered foul block or dead-ball FT: open the FT shooter's
            # segment (the simple rule); their possession counts there
            add_pts(cur["pts"], tid, score_val[i] if is_scoring[i] else 0)
            close(i)
            cur = {"team": tid, "pts": {}, "start_i": i}
            continue
        if non_control:
            add_pts(cur["pts"], tid, score_val[i] if is_scoring[i] else 0)
            continue
        if held is not None:
            commit()
        close(i)
        cur = {"team": tid, "pts": {}, "start_i": i}
    close(n)
    commit()
    return poss


def derive_stints(periods, types, p1s, p2s, starters, home_tid, away_tid):
    """Play arrays + starters -> stints [{home, away, start_i, end_i, period}]."""
    n = len(types)
    stints = []
    oncourt = None
    diag = {"subs_applied": 0, "subs_skipped": 0, "bad_period_open": 0}

    def close(i):
        if stints and "end_i" not in stints[-1]:
            stints[-1]["end_i"] = i

    for i in range(n):
        tt = types[i]
        period = periods[i]
        first_of_period = i == 0 or period != periods[i - 1]
        if first_of_period:
            close(i)
            # Q1 opens with the box starters; every later period inherits the
            # previous period's final set — substitutions carry over between
            # quarters (resetting Q2-Q4 to Q1 starters was the cascade bug).
            src = starters if (oncourt is None or period == 1) else oncourt
            oncourt = {tid: set(v) for tid, v in src.items()}
            for tid, s in oncourt.items():
                if len(s) != 5:
                    diag["bad_period_open"] += 1
            stints.append({"home": sorted(oncourt.get(home_tid, [])),
                           "away": sorted(oncourt.get(away_tid, [])),
                           "start_i": i, "period": period})
            continue
        if tt == "Substitution":
            close(i)
            p1, p2 = p1s[i], p2s[i]
            # Exit always applies (the named exiting player leaves); the entry
            # applies only if the entering player is not already on. ESPN logs
            # bogus entries ("A enters for B" while A is on court) and the
            # reverse direction occasionally — a hard skip cascades, so never
            # skip the exit.
            applied = False
            p1 = p1 if (p1 is not None and pd.notna(p1)) else None
            p2 = p2 if (p2 is not None and pd.notna(p2)) else None
            if p2:
                for tid, s in oncourt.items():
                    if p2 in s:
                        s.discard(p2)
                        if p1 and p1 not in s:
                            s.add(p1)
                        applied = True
                        break
            if not applied and p1:
                # reversed direction: p1 is the exiting player
                for tid, s in oncourt.items():
                    if p1 in s:
                        s.discard(p1)
                        if p2 and p2 not in s:
                            s.add(p2)
                        applied = True
                        break
            if applied:
                diag["subs_applied"] += 1
                for tid, s in oncourt.items():
                    if len(s) != 5:
                        diag["bad_period_open"] += 1  # window with != 5 (dropped stints)
            else:
                diag["subs_skipped"] += 1
            stints.append({"home": sorted(oncourt.get(home_tid, [])),
                           "away": sorted(oncourt.get(away_tid, [])),
                           "start_i": i, "period": period})
    close(n)
    good = [s for s in stints
            if len(s["home"]) == 5 and len(s["away"]) == 5 and s["end_i"] > s["start_i"]]
    diag["stints"] = len(stints)
    diag["stints_kept"] = len(good)
    return good, diag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    a = ap.parse_args()
    g = pd.read_parquet(MART / "games.parquet")
    games = g[(g.season_year == a.season) & (g.season_type == 2) & g.completed & (g.n_plays > 0)]
    pg = pd.read_parquet(MART / "player_game.parquet")
    pb = pd.read_parquet(MART / "pbp.parquet")
    print(f"season {a.season}: {len(games)} regular games with PBP", flush=True)

    rows_poss, rows_stint = [], []
    diag_tot = {"subs_applied": 0, "subs_skipped": 0, "bad_period_open": 0,
                "stints": 0, "stints_kept": 0}
    games_ok = 0
    for gr in games.itertuples():
        gid = gr.game_id
        one = pb[pb.game_id == gid].sort_values(["period", "seq"]).reset_index(drop=True)
        prow = pg[(pg.game_id == gid) & pg.pts.notna()]
        starters, ok = {}, True
        for tid, rr in prow.groupby("team_id"):
            five = set(x for x in rr[rr.starter].athlete_id if pd.notna(x))
            if len(five) != 5:
                ok = False
                break
            starters[str(tid)] = five
        if not ok or len(starters) != 2:
            continue
        home_tid, away_tid = str(gr.home_team_id), str(gr.away_team_id)
        poss = derive_possessions(one.period.tolist(), one.seq.tolist(),
                                  one.type_text.tolist(), one.team_id.tolist(),
                                  one.is_scoring.tolist(), one.points_attempted.tolist(),
                                  one.score_value.tolist())
        stints, diag = derive_stints(one.period.tolist(), one.type_text.tolist(),
                                     one.p1.tolist(), one.p2.tolist(),
                                     starters, home_tid, away_tid)
        for k, v in diag.items():
            diag_tot[k] = diag_tot.get(k, 0) + v
        for p in poss:
            rows_poss.append({"game_id": gid, "team": p["team"],
                              "home": p["team"] == home_tid,
                              "pts": sum(p["pts"].values()), "end_i": p["end_i"]})
        for s in stints:
            mine = [p for p in poss if s["start_i"] < p["end_i"] <= s["end_i"]]
            rows_stint.append({"game_id": gid, "period": s["period"],
                               "home_tid": home_tid, "away_tid": away_tid,
                               "home": s["home"], "away": s["away"],
                               "home_pts": sum(p["pts"].get(home_tid, 0) for p in mine),
                               "away_pts": sum(p["pts"].get(away_tid, 0) for p in mine),
                               "n_poss": len(mine),
                               "start_i": s["start_i"], "end_i": s["end_i"]})
        games_ok += 1

    st = pd.DataFrame(rows_stint)
    ps = pd.DataFrame(rows_poss)
    print(f"derived over {games_ok} games: {len(ps):,} possessions, "
          f"{len(st):,} stints ({diag_tot['stints'] - diag_tot['stints_kept']} dropped) | "
          f"subs applied {diag_tot['subs_applied']:,}, skipped {diag_tot['subs_skipped']:,}, "
          f"bad-period-opens {diag_tot['bad_period_open']}")
    DERIVED.mkdir(parents=True, exist_ok=True)
    ps.to_parquet(DERIVED / f"possessions_{a.season}.parquet", index=False)
    st.to_parquet(DERIVED / f"stints_{a.season}.parquet", index=False)

    # ---- gate 1: possessions vs pbpstats -------------------------------
    pbs_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/pbpstats/games.parquet"
    if pbs_f.exists():
        season_str = f"{a.season - 1}-{str(a.season)[2:]}"
        pbs = pd.read_parquet(pbs_f)
        pbs = pbs[(pbs.season == season_str) & (pbs.season_type == "Regular Season")].copy()
        gg = games.copy()
        gg["home_x"] = gg.home_abbr.map(norm_team)
        m = gg.merge(pbs, left_on=["date_et", "home_x"],
                     right_on=["Date", "HomeTeamAbbreviation"], how="inner")
        der = ps.groupby(["game_id", "team"]).size().unstack(fill_value=0)
        diffs, n_joined = [], 0
        for r in m.itertuples():
            d = der.loc[der.index == r.game_id]
            if d.empty:
                continue
            d = d.iloc[0]
            n_joined += 1
            diffs += [abs(int(d.get(str(r.home_team_id), 0)) - int(r.HomePossessions)),
                      abs(int(d.get(str(r.away_team_id), 0)) - int(r.AwayPossessions))]
        if diffs:
            dd = pd.Series(diffs)
            within2 = float((dd <= 2).mean())
            mae = float(dd.mean())
            gate = "PASS" if (within2 >= 0.95 and mae < 1.5) else "FAIL"
            print(f"GATE possessions-vs-pbpstats: {gate} — within±2 {within2:.1%}, "
                  f"MAE {mae:.2f} ({n_joined} joined games)")
            (DERIVED / f"gate_possessions_{a.season}.json").write_text(json.dumps({
                "within2": within2, "mae": mae, "n_games": int(n_joined),
                "pass": gate == "PASS"}))

    # ---- gate 2: player minutes from stint spans vs box MIN ------------
    minute_rows = []
    for gr in games.itertuples():
        gid = gr.game_id
        one = pb[pb.game_id == gid].sort_values(["period", "seq"]).reset_index(drop=True)
        el = one.period_elapsed.tolist()
        per = one.period.tolist()
        for s in [x for x in rows_stint if x["game_id"] == gid]:
            si, ei = s["start_i"], s["end_i"]
            if ei > len(el) or ei <= si:
                continue
            secs = float(el[ei - 1] - el[si]) if per[ei - 1] == per[si] else 0.0
            if secs <= 0 or secs > 800:
                continue
            for pid in s["home"] + s["away"]:
                minute_rows.append({"athlete_id": pid, "game_id": gid, "secs": secs})
    mr = pd.DataFrame(minute_rows)
    if len(mr):
        agg = mr.groupby(["athlete_id", "game_id"]).secs.sum().div(60.0)
        box = pg[pg.pts.notna()].set_index(["athlete_id", "game_id"])["min"]
        cmp = pd.concat([agg.rename("stint_min"), box.rename("box_min")], axis=1).dropna()
        delta = (cmp.stint_min - cmp.box_min).abs()
        med = float(delta.median())
        gate2 = "PASS" if med <= 0.5 else "FAIL"
        print(f"GATE player-minutes: {gate2} — median |Δ| {med:.2f} min over {len(cmp):,} player-games")
        (DERIVED / f"gate_minutes_{a.season}.json").write_text(json.dumps({
            "median_abs_delta": med, "n": int(len(cmp)), "pass": gate2 == "PASS"}))


if __name__ == "__main__":
    main()
