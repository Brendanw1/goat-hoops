"""possessions.py — derive possession segments and on-court stints from ESPN PBP.

    python pipeline/possessions.py            # 2024-25 regular season (§1)
    python pipeline/possessions.py --season 2025

Implements §1's fixed rules (RESULTS-HOOPS.md), then runs the handling gates
BEFORE anything downstream consumes the tables.

Possession rules:
- possession = one team's control segment; transfers on defensive rebound,
  turnover by the offense, any other opponent-controlled play (how a made FG's
  possession ends), and period start. Non-control: fouls, blocks, timeouts,
  kicked balls, challenges/replays/delays. An FT by the non-control team opens
  the FT shooter's segment (misordered foul blocks / dead-ball FTs); if that
  segment holds only the FT, it is dead-ball — points count, possession doesn't.
- stint = interval between substitutions, with EVIDENCE-BASED DRIFT
  CORRECTION: ESPN's sub log is incomplete (re-entries without rows — §1
  notes), so every shot/FT shooter and rebounder (p1) and every assister
  (p2 of a made shot) is evidence he is on court for the row's team; a
  missing player is added, the stint splits at the correction (the
  pre-correction stint is marked poisoned and dropped), and a sixth man
  evicts the least-recently-evidenced. Q1 opens from box starters; later
  periods inherit the previous period's final set.

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


# §21 H4: rows that never change possession but can carry the "other" team's id
STRICT_NON_CONTROL = ("jumpball", "jump ball", "technical", "defensive goaltending", "lane", "review")


def derive_possessions(periods, types, tids, is_scoring, pts_att, score_val, strict=False):
    """Play arrays -> possession segments [{team, pts:dict, end_i, dead_ball}].
    strict=True adds STRICT_NON_CONTROL (§21 iteration 1)."""
    n = len(types)
    poss, cur = [], None

    def close(i):
        nonlocal cur
        if cur is not None:
            cur["end_i"] = i
            if cur.get("opened_by_ft") and sum(cur.get("team_plays", {}).values()) <= 1:
                cur["dead_ball"] = True
            poss.append(cur)
            cur = None

    for i in range(n):
        tl = types[i].lower()
        tid = tids[i]
        if types[i] in ("End Period", "End Game"):
            close(i)
            continue
        if types[i] == "Substitution" or tid is None:
            continue
        is_turnover = "turnover" in tl
        is_foul = ("foul" in tl) and not is_turnover
        is_block = tl == "block"
        non_control = (is_foul or is_block or "timeout" in tl or "kicked" in tl
                       or "challenge" in tl or "replay" in tl or "delay" in tl
                       or (strict and not is_turnover and any(k in tl for k in STRICT_NON_CONTROL)))
        is_ft = bool(is_scoring[i]) and (pts_att[i] or 0) == 1

        def add_pts(bucket, team, val):
            if val:
                bucket[team] = bucket.get(team, 0) + int(val)

        if cur is None:
            if not non_control and not is_ft:
                cur = {"team": tid, "pts": {}, "start_i": i,
                       "opened_by_ft": False, "team_plays": {}}
            continue
        if tid == cur["team"]:
            add_pts(cur["pts"], tid, score_val[i] if is_scoring[i] else 0)
            cur["team_plays"][tid] = cur["team_plays"].get(tid, 0) + 1
            if is_turnover:
                close(i)
            continue
        # tid != cur team
        if is_ft:
            # FT by the non-control team: misordered foul block or dead-ball
            # FT (technical/flagrant). Open the FT shooter's segment; it only
            # counts as dead-ball when the preceding foul was a technical or
            # flagrant — a shooting-foul FT block is a real possession.
            add_pts(cur["pts"], tid, score_val[i] if is_scoring[i] else 0)
            was_dead = any(("technical" in types[j].lower() or "flagrant" in types[j].lower())
                           for j in range(max(0, i - 3), i))
            close(i)
            cur = {"team": tid, "pts": {}, "start_i": i,
                   "opened_by_ft": was_dead, "team_plays": {}}
            continue
        if non_control:
            add_pts(cur["pts"], tid, score_val[i] if is_scoring[i] else 0)
            continue
        close(i)
        cur = {"team": tid, "pts": {}, "start_i": i,
               "opened_by_ft": False, "team_plays": {}}
    close(n)
    return poss


def derive_stints(periods, types, tids, p1s, p2s, is_scoring, starters,
                  home_tid, away_tid):
    """Play arrays + starters -> (kept stints, diag, every stint incl. poisoned)
    with evidence-based drift correction."""
    n = len(types)
    stints = []
    oncourt = None
    last_ev = {}
    diag = {"subs_applied": 0, "subs_skipped": 0, "evidence_adds": 0,
            "evictions": 0, "poisoned_stints": 0}

    def close(i, poisoned=False):
        if stints and "end_i" not in stints[-1]:
            stints[-1]["end_i"] = i
            stints[-1]["poisoned"] = poisoned

    def new_stint(i, period):
        stints.append({"home": sorted(oncourt.get(home_tid, [])),
                       "away": sorted(oncourt.get(away_tid, [])),
                       "start_i": i, "period": period, "poisoned": False})

    for i in range(n):
        tt = types[i]
        period = periods[i]
        first_of_period = i == 0 or period != periods[i - 1]
        if first_of_period:
            close(i)
            # Q1 opens with box starters; later periods inherit the previous
            # period's final set (substitutions carry across quarters).
            src = starters if (oncourt is None or period == 1) else oncourt
            oncourt = {tid: set(v) for tid, v in src.items()}
            new_stint(i, period)
            continue
        if tt == "Substitution":
            close(i)
            p1, p2 = p1s[i], p2s[i]
            p1 = str(p1) if (p1 is not None and pd.notna(p1)) else None
            p2 = str(p2) if (p2 is not None and pd.notna(p2)) else None
            applied = False
            if p2:
                for tid, s in oncourt.items():
                    if p2 in s:
                        s.discard(p2)
                        if p1 and p1 not in s:
                            s.add(p1)
                            last_ev[p1] = i
                        applied = True
                        break
            if applied:
                diag["subs_applied"] += 1
            else:
                diag["subs_skipped"] += 1
            new_stint(i, period)
            continue
        tid = tids[i] if tids[i] is not None else None
        if tid is None:
            continue
        evs = []
        if p1s[i] is not None and pd.notna(p1s[i]):
            evs.append((str(p1s[i]), str(tid)))
        if bool(is_scoring[i]) and p2s[i] is not None and pd.notna(p2s[i]):
            evs.append((str(p2s[i]), str(tid)))  # assister: same team
        changed = False
        for a, team in evs:
            last_ev[a] = i
            if team in oncourt and a not in oncourt[team]:
                oncourt[team].add(a)
                diag["evidence_adds"] += 1
                changed = True
                if len(oncourt[team]) > 5:
                    evict = min(oncourt[team], key=lambda x: last_ev.get(x, -1))
                    oncourt[team].discard(evict)
                    diag["evictions"] += 1
        if changed:
            close(i, poisoned=True)
            diag["poisoned_stints"] += 1
            new_stint(i, period)
    close(n)
    good = [s for s in stints
            if not s["poisoned"]
            and len(s["home"]) == 5 and len(s["away"]) == 5
            and s["end_i"] > s["start_i"]]
    diag["stints"] = len(stints)
    diag["stints_kept"] = len(good)
    return good, diag, stints


def stint_times(stints, elapsed, periods) -> None:
    """§21 H3: t0 = elapsed time at the stint's first row (0 at a period's
    first stint), t1 = the next stint's t0 in the same period, else the
    period's end (720 s regulation, 300 s OT). Mutates the stint dicts."""
    for k, s in enumerate(stints):
        first = k == 0 or stints[k - 1]["period"] != s["period"]
        s["t0"] = 0.0 if first else float(elapsed[s["start_i"]])
    for k, s in enumerate(stints):
        nxt = stints[k + 1] if k + 1 < len(stints) else None
        s["t1"] = nxt["t0"] if nxt is not None and nxt["period"] == s["period"] else (720.0 if s["period"] <= 4 else 300.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--order", choices=("seq", "clock"), default="clock",
                    help="clock = §21 (creation.clock_frame order + interval stint minutes); "
                         "seq = the §1 walk (kept for reproducing old reads)")
    ap.add_argument("--label", default="",
                    help="suffix every output (stints_{season}_{label}.parquet, gate_*) — "
                         "control/bisect runs must never overwrite the validated production files")
    a = ap.parse_args()
    sfx = f"_{a.label}" if a.label else ""
    g = pd.read_parquet(MART / "games.parquet")
    games = g[(g.season_year == a.season) & (g.season_type == 2) & g.completed & (g.n_plays > 0)]
    pg = pd.read_parquet(MART / "player_game.parquet")
    pb = pd.read_parquet(MART / "pbp.parquet")
    clock = a.order == "clock"
    if clock:
        from creation import clock_frame
        pb = clock_frame(pb[pb.game_id.isin(games.game_id)])
    print(f"order {a.order}", flush=True)
    print(f"season {a.season}: {len(games)} regular games with PBP", flush=True)

    rows_poss, rows_stint, interval_rows = [], [], []
    diag_tot = {"subs_applied": 0, "subs_skipped": 0, "evidence_adds": 0,
                "evictions": 0, "poisoned_stints": 0, "stints": 0, "stints_kept": 0}
    games_ok = 0
    for gr in games.itertuples():
        gid = gr.game_id
        one = (pb[pb.game_id == gid] if clock else
               pb[pb.game_id == gid].sort_values(["period", "seq"])).reset_index(drop=True)
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
        poss = derive_possessions(one.period.tolist(), one.type_text.tolist(),
                                  one.team_id.tolist(), one.is_scoring.tolist(),
                                  one.points_attempted.tolist(),
                                  one.score_value.tolist(), strict=clock)
        stints, diag, all_st = derive_stints(one.period.tolist(), one.type_text.tolist(),
                                     one.team_id.tolist(), one.p1.tolist(),
                                     one.p2.tolist(), one.is_scoring.tolist(),
                                     starters, home_tid, away_tid)
        for k, v in diag.items():
            diag_tot[k] = diag_tot.get(k, 0) + v
        if clock:
            stint_times(all_st, one.period_elapsed.tolist(), one.period.tolist())
            for s in all_st:
                for side in ("home", "away"):
                    if len(s[side]) == 5:
                        interval_rows += [{"athlete_id": pid, "game_id": gid, "secs": s["t1"] - s["t0"]}
                                          for pid in s[side]]
        for p in poss:
            rows_poss.append({"game_id": gid, "team": p["team"],
                              "home": p["team"] == home_tid,
                              "pts": sum(p["pts"].values()), "end_i": p["end_i"],
                              "dead_ball": bool(p.get("dead_ball"))})
        for s in stints:
            mine = [p for p in poss if s["start_i"] < p["end_i"] <= s["end_i"]]
            live = [p for p in mine if not p.get("dead_ball")]
            rows_stint.append({"game_id": gid, "period": s["period"],
                               "home_tid": home_tid, "away_tid": away_tid,
                               "home": s["home"], "away": s["away"],
                               "home_pts": sum(p["pts"].get(home_tid, 0) for p in mine),
                               "away_pts": sum(p["pts"].get(away_tid, 0) for p in mine),
                               "n_poss": len(live),
                               "start_i": s["start_i"], "end_i": s["end_i"],
                               **({"t0": s["t0"], "t1": s["t1"]} if clock else {})})
        games_ok += 1

    st = pd.DataFrame(rows_stint)
    ps = pd.DataFrame(rows_poss)
    print(f"derived over {games_ok} games: {len(ps):,} possessions "
          f"({int(ps.dead_ball.sum()):,} dead-ball), "
          f"{len(st):,} stints ({diag_tot['stints'] - diag_tot['stints_kept']} dropped, "
          f"{diag_tot['poisoned_stints']} poisoned splits) | "
          f"subs {diag_tot['subs_applied']:,}/{diag_tot['subs_skipped']:,} | "
          f"evidence adds {diag_tot['evidence_adds']:,}, evictions {diag_tot['evictions']:,}")
    DERIVED.mkdir(parents=True, exist_ok=True)
    ps.to_parquet(DERIVED / f"possessions_{a.season}{sfx}.parquet", index=False)
    st.to_parquet(DERIVED / f"stints_{a.season}{sfx}.parquet", index=False)

    # ---- gate 1: possessions vs pbpstats (dead-ball excluded) -----------
    pbs_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/pbpstats/games.parquet"
    if pbs_f.exists():
        season_str = f"{a.season - 1}-{str(a.season)[2:]}"
        pbs = pd.read_parquet(pbs_f)
        pbs = pbs[(pbs.season == season_str) & (pbs.season_type == "Regular Season")].copy()
        gg = games.copy()
        gg["home_x"] = gg.home_abbr.map(norm_team)
        m = gg.merge(pbs, left_on=["date_et", "home_x"],
                     right_on=["Date", "HomeTeamAbbreviation"], how="inner")
        der = ps[~ps.dead_ball].groupby(["game_id", "team"]).size().unstack(fill_value=0)
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
            (DERIVED / f"gate_possessions_{a.season}{sfx}.json").write_text(json.dumps({
                "within2": within2, "mae": mae, "n_games": int(n_joined),
                "pass": gate == "PASS"}))

    # ---- gate 2: player minutes from stint spans vs box MIN ------------
    minute_rows = interval_rows if clock else []
    for gr in ([] if clock else games.itertuples()):
        gid = gr.game_id
        one = pb[pb.game_id == gid].sort_values(["period", "seq"]).reset_index(drop=True)
        el = one.period_elapsed.tolist()
        per = one.period.tolist()
        for s in [x for x in rows_stint if x["game_id"] == gid]:
            si, ei = s["start_i"], s["end_i"]
            if ei > len(el) or ei <= si or per[ei - 1] != per[si]:
                continue
            secs = float(el[ei - 1] - el[si])
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
        (DERIVED / f"gate_minutes_{a.season}{sfx}.json").write_text(json.dumps({
            "median_abs_delta": med, "n": int(len(cmp)), "pass": gate2 == "PASS"}))


if __name__ == "__main__":
    main()
