"""track_c.py — §15 gravity: teammate 3PA rate, a WOWY expression on the stint spine.

    python pipeline/track_c.py

Preregistered in pipeline/results/RESULTS-HOOPS.md §15 (2026-11-08) BEFORE
this implementation. Descriptive only — within-team importance, never league
quality (the ASA WOWY discipline held in the KB).

Inputs (all §0f-validated lineage, site season 2025 = 2024-25):
  data/derived/stints_2025.parquet       10-man windows, play-index spans
  data/derived/possessions_2025.parquet  team-attributed possession ends
  <mart>/data/mart/pbp.parquet           field-goal attempts (pa 2/3 — free
                                         throws carry is_shooting with pa 1
                                         and are excluded)
  data/export/web/seasavgs_2025.json.gz  names, positions, usage (BDL 2024 →
                                         site 2025: the SAME season as the stints)

Outputs:
  data/derived/track_c_2025.json   gates, top/bottom table, confounds
  data/derived/track_c_2025.csv    per-qualifier rows for inspection
"""

import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
MART = Path("/Users/brendanwaterval/Projects/vt_baseball/hoops_mart/data/mart")

# pre-registered (§15)
MIN_POSS = 600   # team possessions in EACH split
MIN_FGA = 300    # teammate FGA in EACH split
G1_BAR = 0.35    # split-half Spearman


def load():
    stints = pd.read_parquet(DERIVED / "stints_2025.parquet")
    poss = pd.read_parquet(DERIVED / "possessions_2025.parquet")
    pbp = pd.read_parquet(MART / "pbp.parquet",
                          columns=["game_id", "seq", "team_id", "is_shooting",
                                   "p1", "points_attempted"])
    ss = json.load(gzip.open(ROOT / "data/export/web/seasavgs_2025.json.gz"))["players"]
    return stints, poss, pbp, ss


def game_index(pbp: pd.DataFrame, poss: pd.DataFrame):
    """Per game: field-goal attempts at their POSITIONAL play index (order by
    seq — the alignment §0f validated) and team possession end indices."""
    fga = {}
    for gid, g in pbp.groupby("game_id", sort=False):
        g = g.sort_values("seq").reset_index(drop=True)
        m = g.is_shooting & g.points_attempted.isin([2, 3]) & g.p1.notna()
        fga[int(gid)] = list(zip(g.index[m], g.team_id[m].astype(int),
                                 g.p1[m].astype(int), g.points_attempted[m].astype(int)))
    # 578 of 138,179 segments carry no controlling team (0.4%) — they can't
    # count toward any team's possessions, so they drop
    poss = poss[poss.team.notna()]
    pend = {int(gid): list(zip(g.end_i.astype(int), g.team.astype(int)))
            for gid, g in poss.groupby("game_id", sort=False)}
    return fga, pend


def main() -> int:
    stints, poss, pbp, ss = load()
    fga, pend = game_index(pbp, poss)

    # each team's game roster = everyone who appears in any of its fives.
    # Every id source is STRING-typed (stints, possessions, pbp) — cast once
    # here and everywhere, or roster − five silently removes nobody
    rosters: dict = defaultdict(lambda: defaultdict(set))
    for r in stints.itertuples(index=False):
        rosters[int(r.game_id)][int(r.home_tid)].update(int(p) for p in r.home)
        rosters[int(r.game_id)][int(r.away_tid)].update(int(p) for p in r.away)

    # pairing WOWY (§15 amendment): for X and each teammate T, T's OWN
    # attempts with X on vs X off (T on court in both, same games).
    # pair[half][X][T] = [poss_w, fga_w, tpa_w, poss_wo, fga_wo, tpa_wo]
    # xp[half][X] = [team poss with X on, team poss with X off]
    pair: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0] * 6)))
    xp: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    cov = [0, 0]  # window-summed (possessions, FGA) — the conservation check
    for r in stints.itertuples(index=False):
        gid, s, e = int(r.game_id), int(r.start_i), int(r.end_i)
        half = gid % 2
        for tid, five in ((int(r.home_tid), r.home), (int(r.away_tid), r.away)):
            five = [int(p) for p in five]
            if len(five) != 5:
                continue
            n_poss = sum(1 for end, t in pend.get(gid, ()) if s < end <= e and t == tid)
            own = defaultdict(lambda: [0, 0])  # shooter → [fga, tpa] in window
            for i, t, p, pa in fga.get(gid, ()):
                if s < i <= e and t == tid:
                    own[p][0] += 1
                    own[p][1] += pa == 3
            cov[0] += n_poss
            cov[1] += sum(v[0] for v in own.values())
            off = rosters[gid][tid] - set(five)
            for x in five:
                xp[half][x][0] += n_poss
            for x in off:
                xp[half][x][1] += n_poss
            for t_ in five:  # T on court; X either alongside (with) or off (without)
                f, tp = own[t_]
                for x in five:
                    if x != t_:
                        a = pair[half][x][t_]
                        a[0] += n_poss; a[1] += f; a[2] += tp
                for x in off:
                    a = pair[half][x][t_]
                    a[3] += n_poss; a[4] += f; a[5] += tp

    PAIR_MIN = 100  # pair-entry floor: possessions in EACH split (amendment)

    # conservation: windows tile each game, so window sums should recover the
    # source totals for the stint games (a broken join shows up here, loudly)
    games = set(stints.game_id.astype(int))
    src_poss = sum(len(pend.get(g, ())) for g in games)
    src_fga = sum(len(fga.get(g, ())) for g in games)
    print(f"conservation: possessions {cov[0]:,}/{src_poss:,} ({cov[0]/src_poss:.3f}) | "
          f"FGA {cov[1]:,}/{src_fga:,} ({cov[1]/src_fga:.3f})")

    def gravity(x: int, halves: tuple) -> dict | None:
        """X's pairing WOWY over the given halves; None if X misses a floor."""
        agg: dict = defaultdict(lambda: [0] * 6)
        pon = poff = 0
        for h in halves:
            for t_, a in pair[h][x].items():
                b = agg[t_]
                for k in range(6):
                    b[k] += a[k]
            pon += xp[h][x][0]
            poff += xp[h][x][1]
        num = den = s_num = 0.0
        fw = fwo = 0
        for pw, fgw, tpw, pwo, fgwo, tpwo in agg.values():
            if pw < PAIR_MIN or pwo < PAIR_MIN:
                continue
            w = 2 * pw * pwo / (pw + pwo)  # harmonic weight: balanced samples
            num += w * (tpw / pw - tpwo / pwo) * 100
            den += w
            if fgw and fgwo:
                s_num += w * (tpw / fgw - tpwo / fgwo)
            fw += fgw
            fwo += fgwo
        if not (pon >= MIN_POSS and poff >= MIN_POSS and fw >= MIN_FGA
                and fwo >= MIN_FGA and den > 0):
            return None
        return {"gravity": num / den, "share_diff": s_num / den,
                "poss_on": pon, "poss_off": poff, "fga_with": fw, "fga_without": fwo}

    rows = []
    for pid in {x for h in xp for x in xp[h]}:
        g = gravity(pid, (0, 1))
        if g is None:
            continue
        info = ss.get(str(pid)) or {}
        h = {f"h{k}": (gravity(pid, (k,)) or {}).get("gravity") for k in (0, 1)}
        rows.append({"pid": pid, "name": info.get("name", str(pid)),
                     "pos": info.get("pos"), "usg": (info.get("adv") or {}).get("usg_pct"),
                     **g, **h})
    df = pd.DataFrame(rows)
    if df.empty:
        print("§15: no qualifiers — FAIL")
        return 1

    # G1: split-half Spearman among players qualifying in BOTH halves
    both = df.dropna(subset=["h0", "h1"])
    g1 = float(both.h0.rank().corr(both.h1.rank())) if len(both) >= 20 else float("nan")
    # G2: usage quartiles among qualifiers with a usage value
    u = df.dropna(subset=["usg"]).copy()
    u["q"] = pd.qcut(u.usg.rank(method="first"), 4, labels=[1, 2, 3, 4])
    top, bot = u[u.q == 4].gravity.median(), u[u.q == 1].gravity.median()
    gates = {"G1_split_half_spearman": round(g1, 4), "G1_pass": bool(g1 >= G1_BAR),
             "G2_top_usage_q_median": round(float(top), 3),
             "G2_bottom_usage_q_median": round(float(bot), 3),
             "G2_pass": bool(top > bot),
             "n_qualifiers": int(len(df)), "n_both_halves": int(len(both)),
             "n_with_usage": int(len(u))}
    verdict = "PASS" if gates["G1_pass"] and gates["G2_pass"] else "FAIL"

    out = df.sort_values("gravity", ascending=False)
    cols = ["name", "pos", "usg", "gravity", "share_diff", "poss_on", "poss_off",
            "fga_with", "fga_without", "h0", "h1"]
    doc = {"section": "§15", "season": "site 2025 (2024-25)", "verdict": verdict,
           "metric": "pairing WOWY: teammates' own 3PA per 100 team poss, with X minus without X",
           "gates": gates,
           "floors": {"poss": MIN_POSS, "fga": MIN_FGA, "pair_poss": PAIR_MIN},
           "top25": out.head(25)[cols].round(3).to_dict("records"),
           "bottom10": out.tail(10)[cols].round(3).to_dict("records")}
    (DERIVED / "track_c_2025.json").write_text(json.dumps(doc, indent=1, default=str))
    out.to_csv(DERIVED / "track_c_2025.csv", index=False)

    print(json.dumps(gates, indent=1))
    print(f"§15 verdict: {verdict}")
    for r in doc["top25"][:10]:
        print(f"  {r['name']:<26} {r['pos']!s:<3} usg {r['usg']}  gravity {r['gravity']:+.2f}"
              f"  share {r['share_diff']:+.3f}")
    print("  ...")
    for r in doc["bottom10"][-4:]:
        print(f"  {r['name']:<26} {r['pos']!s:<3} usg {r['usg']}  gravity {r['gravity']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
