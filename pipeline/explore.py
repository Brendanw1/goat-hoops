"""explore.py — the exploration foundation (descriptive, not forecasts).

    python pipeline/explore.py        # writes similar/aging/clutch/surplus/rebound docs

Reads the already-validated site docs from data/export/web (advagg, careers,
seasavgs, players board, contracts) and writes four exploration artifacts.
Nothing here forecasts: every output is a transformation of baked values, and
findings land in docs/explorations-2026-11.md with any claim-shaped number
(e.g. "rebound conversion is a skill") carrying its own inline stability read.

Artifacts (keys under hoops/ on R2 like every other baked doc):
  similar.json.gz   season player vectors -> archetypes (k-means) + top-8
                    cosine neighbors; the z-vectors are the reusable foundation
  surplus.json.gz   production composite (mean z of 8 fields) vs cap-hit
                    percentile, one season offset (prod 2025-26, salary 2026-27)
  clutch.json.gz    clutch-vs-overall deltas from the seasavgs category docs
  rebound.json.gz   rebound conversion (reb36 / rebound chances per 36) + league
                    bands, per season
  aging.json        per-age career curves from the 2005-2025 history (selection
                    bias: old cohorts are survivors — descriptive only)
"""

import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "export" / "web"
BDL = Path.home() / "Projects/vt_baseball/hoops_mart/data/bdl"

# the similarity/composite vector: efficiency, load, playmaking, glass,
# impact, activity — every field exists on all recent seasons
VECTOR_FIELDS = (
    "ts_pct", "efg_pct", "usg_pct", "ast_pct", "ast_to", "orb_pct", "drb_pct",
    "reb_pct", "ortg", "drtg", "net", "pie", "pct_fga_3pt", "pct_pts_paint",
    "pct_ast_fgm", "pct_unast_fgm", "deflections", "contested", "charges",
    "boxouts", "screen_ast", "loose", "passes", "touches", "sec_ast", "ft_ast",
    "reb_ch", "speed", "distance", "blka", "switches",
)
LOWER_BETTER = {"drtg"}  # inverted before z-scoring so every axis is higher=more

# the production composite for surplus: eight transparent pillars
PROD_FIELDS = ("ts_pct", "usg_pct", "ast_pct", "drb_pct", "net", "pie",
               "deflections", "screen_ast")

SEASON = "2026"          # latest advagg season (2025-26; ~half covered, flagged)
SALARY_SEASON = 2027     # contracts.json salaries (2026-27 cap hits)
MIN_GP_VECTOR = 15
MIN_GP_PROD = 20
K_ARCHETYPES = 7


def load(name):
    op = gzip.open if name.endswith(".gz") else open
    return json.loads(op(OUT / name).read())


def wr_gz(name, obj):
    (OUT / name).write_bytes(gzip.compress(
        json.dumps(obj, allow_nan=False, sort_keys=True).encode(), mtime=0))
    print(f"wrote {name}")


def matrix(players, fields):
    """players: dict eid -> entry. Returns (eids, X with NaN imputed later)."""
    eids = sorted(players)
    M = np.full((len(eids), len(fields)), np.nan)
    for i, e in enumerate(eids):
        for j, f in enumerate(fields):
            v = players[e].get(f)
            if isinstance(v, (int, float)):
                M[i, j] = -v if f in LOWER_BETTER else v
    return eids, M


def zscore(M):
    """z per column; missing -> 0 (league average) so a gap never invents a
    similarity. Columns with >30% missing are dropped outright."""
    keep = np.isnan(M).mean(axis=0) <= 0.30
    M = M[:, keep]
    mu = np.nanmean(M, axis=0)
    sd = np.nanstd(M, axis=0)
    sd[sd == 0] = 1.0
    Z = (M - mu) / sd
    Z[np.isnan(Z)] = 0.0
    return Z, keep, mu, sd


def kmeans(X, k, seed=7, iters=100):
    rng = np.random.default_rng(seed)
    # k-means++ seeding
    centers = [X[rng.integers(len(X))]]
    for _ in range(k - 1):
        d2 = ((X[:, None, :] - np.array(centers)[None]) ** 2).sum(-1).min(axis=1)
        centers.append(X[rng.choice(len(X), p=d2 / d2.sum())])
    C = np.array(centers)
    for _ in range(iters):
        assign = ((X[:, None, :] - C[None]) ** 2).sum(-1).argmin(axis=1)
        new = []
        for j in range(k):
            rows = X[assign == j]
            new.append(rows.mean(axis=0) if len(rows) else X[rng.integers(len(X))])
        new = np.array(new)
        if np.allclose(new, C):
            break
        C = new
    assign = ((X[:, None, :] - C[None]) ** 2).sum(-1).argmin(axis=1)
    return C, assign


ARCHETYPE_RULES = (
    (("usg_pct", 0.9), "usage-heavy creators"),
    (("ast_pct", 0.9), "playmakers"),
    (("pct_unast_fgm", 0.5), "self-created scorers"),
    (("pct_ast_fgm", 0.5), "off-ball finishers"),
    (("pct_fga_3pt", 0.8), "perimeter shooters"),
    (("pct_pts_paint", 0.8), "paint finishers"),
    (("drb_pct", 0.7), "glass anchors"),
    (("deflections", 0.7), "activity defenders"),
    (("charges", 0.5), "3-and-D role players"),
    (("screen_ast", 0.7), "screeners"),
    (("ts_pct", 0.6), "efficient finishers"),
)


FALLBACK_PRETTY = {
    "pct_unast_fgm": "self-created", "pct_ast_fgm": "assisted-make",
    "blka": "shot-blocking", "charges": "charge-drawing",
    "deflections": "deflection-heavy", "screen_ast": "screening",
    "reb_ch": "glass activity", "distance": "high-motion",
}


def archetype_label(centroid_z, fields, taken=()):
    idx = {f: i for i, f in enumerate(fields)}
    tags = [label for (f, t), label in ARCHETYPE_RULES if idx.get(f) is not None
            and centroid_z[idx[f]] >= t]
    for label in tags:
        if label not in taken:
            return label
    if tags:
        return tags[0]
    top = int(np.argmax(centroid_z))
    return f"{FALLBACK_PRETTY.get(fields[top], fields[top])} profiles"


def pct_rank(vals):
    """0..1 percentile rank, ties averaged by construction (stable sort)."""
    order = np.argsort(vals, kind="stable")
    ranks = np.empty(len(vals))
    ranks[order] = np.arange(len(vals)) / (len(vals) - 1)
    return ranks


def similar(adv, board=None):
    players = adv["seasons"][SEASON]["players"]
    pool = {e: p for e, p in players.items()
            if p.get("gp", 0) >= MIN_GP_VECTOR and (p.get("min") or 0) >= 250}
    eids, M = matrix(pool, VECTOR_FIELDS)
    Z, keep, _, _ = zscore(M)
    fields = [f for f, k in zip(VECTOR_FIELDS, keep) if k]
    C, assign = kmeans(Z, K_ARCHETYPES)
    # cosine similarity on the unit sphere
    Zn = Z / np.clip(np.linalg.norm(Z, axis=1, keepdims=True), 1e-9, None)
    sim = Zn @ Zn.T
    archetypes = {}
    players_out = {}
    taken: set = set()
    name_of = {}
    if board:
        for rows_ in board.get("seasons", {}).values():
            for r in rows_:
                name_of[str(r["id"])] = r.get("name")
    for j in range(K_ARCHETYPES):
        rows = np.where(assign == j)[0]
        label = archetype_label(C[j], fields, taken)
        taken.add(label)
        top = sorted(zip(fields, C[j].round(2)), key=lambda t: -t[1])[:5]
        archetypes[j] = {"label": label, "size": int(len(rows)),
                         "centroid": [[f, float(z)] for f, z in top]}
        for i in rows:
            order = np.argsort(-sim[i])
            nbrs = [[eids[t], round(float(sim[i, t]), 3),
                     name_of.get(str(eids[t]))]
                    for t in order if t != i][:8]
            players_out[eids[i]] = {"a": j, "n": nbrs}
    wr_gz("similar.json.gz", {
        "season": int(SEASON), "k": K_ARCHETYPES, "fields": fields,
        "archetypes": archetypes, "players": players_out,
        "note": "descriptive exploration: z-scored balldontlie v2-advanced season "
                "vectors, k-means archetypes (seed 7) + cosine neighbors — internal "
                "research; not a forecast, no model gate"})
    return eids, Z, fields, assign


def surplus(adv, contracts):
    players = adv["seasons"][SEASON]["players"]
    pool = {e: p for e, p in players.items() if p.get("gp", 0) >= MIN_GP_PROD}
    eids, M = matrix(pool, PROD_FIELDS)
    Z, keep, _, _ = zscore(M)
    fields = [f for f, k in zip(PROD_FIELDS, keep) if k]
    prod_z = Z.mean(axis=1)
    prod_pct = pct_rank(prod_z)
    sal = {e: s["cap_hit"] for e, s in (contracts.get("salaries") or {}).items()
           if isinstance(s.get("cap_hit"), (int, float)) and s["cap_hit"] > 0}
    sals = np.array([sal.get(e, np.nan) for e in eids], dtype=float)
    have = ~np.isnan(sals)
    sal_pct = np.full(len(eids), np.nan)
    sal_pct[have] = pct_rank(sals[have])
    out = {}
    for i, e in enumerate(eids):
        out[e] = {"prod_z": round(float(prod_z[i]), 2),
                  "prod_pct": round(float(prod_pct[i]), 3),
                  "sal": int(sals[i]) if have[i] else None,
                  "sal_pct": round(float(sal_pct[i]), 3) if have[i] else None,
                  "surplus": (round(float(prod_pct[i] - sal_pct[i]), 3)
                              if have[i] else None)}
    wr_gz("surplus.json.gz", {
        "season_prod": int(SEASON), "season_salary": SALARY_SEASON,
        "fields": fields, "players": out,
        "note": "descriptive: production = mean z of ts/usg/ast/drb/net/pie/"
                "deflections/screen_ast within the season pool; surplus = "
                "production percentile minus cap-hit percentile (2025-26 "
                "production vs 2026-27 cap hit) — not a valuation model"})


def clutch():
    out = {}
    for yr in ("2024", "2025", "2026"):
        seas = load(f"seasavgs_{yr}.json.gz")
        season = {}
        for e, cats in seas["players"].items():
            a, c = cats.get("adv"), cats.get("clutch")
            if not a or not c:
                continue
            def d(k):
                av, cv = a.get(k), c.get(k)
                if isinstance(av, (int, float)) and isinstance(cv, (int, float)):
                    return round(cv - av, 3)
                return None
            gp = c.get("gp")
            # net: the plain net_rating when both sides carry it, else the
            # estimated one — never mix the two scales
            net_d = d("net_rating") if ("net_rating" in a and "net_rating" in c) \
                else d("e_net_rating")
            season[e] = {"gp": gp if isinstance(gp, (int, float)) else None,
                         "ts_d": d("ts_pct"), "usg_d": d("usg_pct"),
                         "net_d": net_d,
                         "pie_d": d("pie")}
        out[int(yr)] = season
    wr_gz("clutch.json.gz", {
        "seasons": out,
        "note": "descriptive: clutch-category minus overall season averages "
                "(balldontlie season_averages) — small samples by construction"})


def rebound(adv):
    board = load("players.json")
    out = {}
    for yr in ("2024", "2025", "2026"):
        advp = adv["seasons"].get(yr, {}).get("players", {})
        rows = {r["id"]: r for r in board["seasons"].get(yr, [])}
        season = {}
        for e, a in advp.items():
            ch = a.get("reb_ch")
            r36 = rows.get(e, {}).get("reb36")
            if isinstance(ch, (int, float)) and isinstance(r36, (int, float)) and ch > 0:
                season[e] = {"reb36": r36, "reb_ch": ch,
                             "conv": round(r36 / ch, 3)}
        vals = sorted(v["conv"] for v in season.values())
        if len(vals) >= 30:
            at = lambda p: vals[min(int(p * len(vals)), len(vals) - 1)]
            out[int(yr)] = {"players": season,
                            "dist": {"p10": at(.10), "p25": at(.25), "p50": at(.50),
                                     "p75": at(.75), "p90": at(.90)}}
    wr_gz("rebound.json.gz", {
        "seasons": out,
        "note": "descriptive: rebounds per 36 divided by balldontlie rebound "
                "chances per 36 — conversion of chances, not a skill claim "
                "(stability read in docs/explorations-2026-11.md)"})


def aging():
    careers = load("careers.json.gz")
    by_age = {}
    for rows in careers["players"].values():
        for season, age, gp, mpg, ppg, rpg, apg, ts, usg in rows:
            if age is None or (gp or 0) < 20:
                continue
            bucket = by_age.setdefault(age, [])
            bucket.append((mpg, ppg, rpg, apg, ts, usg))
    curves = {}
    for age, vals in sorted(by_age.items()):
        cols = list(zip(*vals))
        curves[age] = {"n": len(vals)}
        for name, col in zip(("mpg", "ppg", "rpg", "apg", "ts", "usg"), cols):
            col = [v for v in col if v is not None]
            if len(col) >= 5:
                col.sort()
                curves[age][name] = {
                    "mean": round(sum(col) / len(col), 2),
                    "p25": col[int(0.25 * (len(col) - 1))],
                    "p75": col[int(0.75 * (len(col) - 1))]}
    wr_gz("aging.json.gz", {
        "curves": curves,
        "note": "descriptive: per-age career-line averages from the 2005-2025 "
                "history pull, gp>=20 rows only. Selection bias by construction: "
                "28-year-olds include everyone; 38-year-olds are survivors — "
                "these are cohort curves, not trajectories"})


def yoy_stability(adv):
    """The inline stability read for any conversion-as-skill phrasing: same-
    player conversion, season t vs t+1, complete seasons only (2024->2025)."""
    board = load("players.json")
    def conv(yr):
        advp = adv["seasons"].get(yr, {}).get("players", {})
        rows = {r["id"]: r for r in board["seasons"].get(yr, [])}
        out = {}
        for e, a in advp.items():
            ch, r36 = a.get("reb_ch"), rows.get(e, {}).get("reb36")
            if isinstance(ch, (int, float)) and ch > 0 and isinstance(r36, (int, float)):
                out[e] = r36 / ch
        return out
    a, b = conv("2024"), conv("2025")
    shared = [e for e in a if e in b]
    if len(shared) >= 30:
        x = np.array([a[e] for e in shared])
        y = np.array([b[e] for e in shared])
        r = float(np.corrcoef(x, y)[0, 1])
        print(f"rebound conversion YoY (2024->2025, n={len(shared)}): r={r:.3f}")
        return r
    return None


def main():
    adv = load("advagg.json.gz")
    contracts = load("contracts.json")
    board = load("players.json")
    eids, Z, fields, assign = similar(adv, board)
    # exploration prints (the read happens once, recorded in docs/explorations)
    for j in sorted({int(a) for a in assign}):
        rows = [eids[i] for i in np.where(assign == j)[0]]
        print(f"archetype {j}: n={len(rows)}")
    surplus(adv, contracts)
    clutch()
    rebound(adv)
    r = yoy_stability(adv)
    aging()
    if r is not None:
        (ROOT / "docs" / ".rebound_yoy").write_text(f"{r:.4f}\n")


if __name__ == "__main__":
    main()
