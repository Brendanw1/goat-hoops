"""rapm_spm.py — §7: the §5 xPTS ridge with a tracking SPM prior in place of the Game Score prior.

    nice -n 10 python pipeline/rapm_spm.py --dry     # features, SPM out-of-fold r, prior coverage; no ridge, no read
    nice -n 10 python pipeline/rapm_spm.py           # the one pre-registered read

Design per the §7 pre-registration (RESULTS-HOOPS.md, commit 0bfd61d):
  target    the two-season points RAPM on 2022-23 + 2023-24 at λ = 30,000
            (`rapm_multi.py --seasons 2024 2023 --tag _spmtarget`), players with >= 500 possessions
  features  every numeric bdl_season column (vt_baseball hoops_mart, BDL season = start year), possession-weighted over
            the two seasons; counting columns per 36 via general_base.min, columns whose full name contains
            pct/percentage/freq/ratio/avg/speed/dist/rating kept as they are, gp/w/l/age dropped and general_base.age
            re-added once; median fill (training medians) + a missing flag per category
  SPM       elastic net on standardized features, α and l1 ∈ {0.1, 0.5, 0.9} by 5-fold CV over players, weighted by
            possessions; an outer 5-fold reports its own out-of-fold r (reported, not gated)
  prior     the SPM applied to each player's 2024-25 row, centered over the response players, per 100 -> per possession;
            players with no 2024-25 BDL row fall back to their §5 Game Score prior
  ridge     §5 verbatim from the design matrix on (τ = 250, λ grid, game-margin CV, both gates)
Writes results/rapm_spm.json + results/rapm_spm_players.csv.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ROOT, MART  # noqa: E402,F401
from rapm_priors import fit_ridge, LAMBDA_GRID, TAU  # noqa: E402,F401

RESULTS = ROOT / "pipeline" / "results"
DERIVED = ROOT / "data" / "derived"
BDL_SEASON = Path.home() / "Projects/vt_baseball/hoops_mart/data/mart/bdl_season.parquet"
KEEP = ("pct", "percentage", "freq", "ratio", "avg", "speed", "dist", "rating")
FIT_SEASONS = {2022: 2023, 2023: 2024}                 # BDL start year -> our end-year possession files
RESPONSE_BDL = 2024                                    # 2024-25


def transform(s):
    """The fixed §7 feature rule on bdl_season rows (one row per player-season)."""
    num = s.select_dtypes("number").drop(columns=["season"], errors="ignore")
    age = num["general_base.age"]
    num = num.drop(columns=[c for c in num if c.split(".")[-1] in ("gp", "w", "l", "age")])
    mn = s["general_base.min"].where(s["general_base.min"] > 0)
    per36 = [c for c in num if not any(k in c for k in KEEP)]
    num[per36] = num[per36].div(mn, axis=0) * 36
    num["age"] = age
    num.index = s.nba_pid.astype(str).to_numpy()
    return num


def poss_by_player(end_year):
    f = DERIVED / f"rapm_rows_{end_year}.parquet"
    return pd.read_parquet(f, columns=["on10"]).explode("on10").groupby("on10").size()


def fill(X, med, cats):
    flags = pd.DataFrame({f"miss.{c}": X[[k for k in X if k.split(".")[0] == c]].isna().all(axis=1).astype(float)
                          for c in cats}, index=X.index)
    return pd.concat([X.fillna(med), flags], axis=1)


def spm(verbose=True):
    S = pd.read_parquet(BDL_SEASON)
    S = S[S.nba_pid.notna()]
    tgt = pd.read_csv(RESULTS / "rapm_multi_spmtarget_players.csv", dtype={"aid": str}).set_index("aid").rapm_30000
    xs = [transform(S[S.season == bs]) for bs in FIT_SEASONS]
    wts = [poss_by_player(ey).reindex(x.index).fillna(0) for x, ey in zip(xs, FIT_SEASONS.values())]
    num = pd.concat([x.mul(w, axis=0) for x, w in zip(xs, wts)]).groupby(level=0).sum(min_count=1)
    den = pd.concat([x.notna().mul(w, axis=0) for x, w in zip(xs, wts)]).groupby(level=0).sum()
    X = num / den.where(den > 0)
    poss = sum(poss_by_player(ey) for ey in FIT_SEASONS.values()).reindex(X.index).fillna(0)
    keep = X.index[(poss >= 500) & X.index.isin(tgt.index)]
    X, y, w = X.loc[keep], tgt.loc[keep].values, poss.loc[keep].values
    cats = sorted({c.split(".")[0] for c in X if "." in c})
    med = X.median()
    Xf = fill(X, med, cats)
    Xf = Xf.loc[:, Xf.std() > 0]
    cols = list(Xf.columns)

    def fit(Xa, ya, wa):
        sc = StandardScaler().fit(Xa)
        m = ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9], cv=KFold(5, shuffle=True, random_state=0), max_iter=20000,
                         n_jobs=2).fit(sc.transform(Xa), ya, sample_weight=wa)
        return sc, m

    oof = np.zeros(len(y))
    for tr, te in KFold(5, shuffle=True, random_state=1).split(Xf):
        sc, m = fit(Xf.values[tr], y[tr], w[tr])
        oof[te] = m.predict(sc.transform(Xf.values[te]))
    sc, m = fit(Xf.values, y, w)
    coef = pd.Series(m.coef_, index=cols)
    imp = coef.abs().groupby([c.split(".")[0] for c in cols]).sum().sort_values(ascending=False)
    rep = {"n_players": int(len(y)), "n_features": len(cols), "alpha": float(m.alpha_), "l1_ratio": float(m.l1_ratio_),
           "n_nonzero": int((coef != 0).sum()), "oof_r": round(float(np.corrcoef(oof, y)[0, 1]), 4),
           "oof_r_weighted": round(float(pd.DataFrame({"a": oof, "b": y}).corr().iloc[0, 1]), 4),
           "top_categories": {k: round(float(v), 3) for k, v in imp.head(10).items()}}
    # apply to 2024-25
    R = transform(S[S.season == RESPONSE_BDL])
    R = fill(R.reindex(columns=X.columns), med, cats).reindex(columns=cols)
    pred = pd.Series(m.predict(sc.transform(R.values)), index=R.index)
    if verbose:
        print(json.dumps(rep, indent=1))
    return pred, rep


def gamescore_prior(season):
    """The §5 Game Score prior (copied from rapm_priors.py), centered, per 100, keyed by nba pid."""
    # ---- box prior: Game Score per 100 (the season's own box) --------------
    pg = pd.read_parquet(MART / "player_game.parquet")
    gg = pd.read_parquet(MART / "games.parquet")
    season_games = set(gg[(gg.season_year == season) & (gg.season_type == 2)].game_id)
    pg = pg[(pg.game_id.isin(season_games)) & pg.pts.notna()].copy()
    gsc = (pg.pts + 0.4 * pg.fgm - 0.7 * pg.fga - 0.4 * (pg.fta - pg.ftm)
           + 0.7 * pg.oreb + 0.3 * pg.dreb + pg.stl + 0.7 * pg.ast
           + 0.7 * pg.blk - 0.7 * pg.pf - pg["to"])
    pg["gmsc"] = gsc
    agg = pg.groupby("athlete_id").agg(gmsc=("gmsc", "sum"), min=("min", "sum"))
    agg = agg[agg["min"] >= 100]
    agg["prior100"] = 100.0 * agg.gmsc / (agg["min"] * 2.0)
    league_mean = agg.prior100.mean()
    agg["prior_c"] = agg.prior100 - league_mean
    pg_name = pg.set_index("athlete_id").name.dropna().to_dict()
    pg["aid_str"] = pg.athlete_id.astype(str)
    pc = pg.groupby("aid_str").gmsc.sum()
    # bridge ESPN athlete ids -> nba.com pids via normalized names (the
    # register is the pt endpoint's id space; validated 0 unmapped in §1)
    import re as _re
    import unicodedata as _ud
    def _norm(s):
        s = _ud.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
        s = _re.sub(r"[.'\u2019-]", " ", s.lower())
        return " ".join(t for t in s.split() if t and t not in {"jr", "sr", "ii", "iii", "iv"})
    pg["name_norm"] = pg.name.map(_norm)
    reg = pd.read_parquet(Path.home() / "Projects/vt_baseball/hoops_mart/data/pbpstats/players.parquet")
    pid_by_norm = {r.name_norm: str(r.id) for r in
                   reg.assign(name_norm=reg.name.map(_norm)).itertuples()}
    prior_of = {}
    for aid, v, mn in zip(agg.index.astype(str), agg.prior_c, agg["min"]):
        nm = pg_name.get(aid)
        nba = pid_by_norm.get(_norm(nm)) if nm else None
        if nba:
            prior_of[nba] = (float(v), float(mn))
    print(f"box priors: {len(prior_of)} players bridged to nba ids | league mean prior100 {league_mean:.2f}")
    return prior_of



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--dry", action="store_true", help="everything before the read; no ridge fit")
    a = ap.parse_args()

    pr = pd.read_parquet(DERIVED / f"rapm_xrows_{a.season}.parquet").reset_index(drop=True)
    pr = pr[pr.on10.map(len) == 10].reset_index(drop=True)
    print(f"possession rows: {len(pr):,}")
    players = sorted({p for row in pr.on10 for p in row})
    pidx = {p: i for i, p in enumerate(players)}
    nP = len(players)

    pred, spm_rep = spm()
    spm_resp = pred[pred.index.isin(players)]
    spm_resp = spm_resp[~spm_resp.index.duplicated()]
    spm_c = spm_resp - spm_resp.mean()                 # centered over the response players
    gsp = gamescore_prior(a.season)
    prior_of = {p: (float(v), np.nan) for p, v in spm_c.items()}
    fallback = [p for p in players if p not in prior_of and p in gsp]
    for p in fallback:
        prior_of[p] = gsp[p]
    cover = {"response_players": nP, "spm_prior": int(len(spm_c)), "gamescore_fallback": len(fallback),
             "no_prior": nP - len(spm_c) - len(fallback),
             "spm_vs_gamescore_r": round(float(pd.DataFrame({"s": spm_c, "g": {p: v[0] for p, v in gsp.items()}})
                                               .dropna().corr().iloc[0, 1]), 4)}
    print(json.dumps(cover, indent=1))
    if a.dry:
        return
    # ---- design matrix -----------------------------------------------------
    X = np.zeros((len(pr) + len(players), nP + 1), dtype=np.float64)
    y = np.zeros(len(pr) + len(players), dtype=np.float64)
    w = np.ones(len(pr) + len(players), dtype=np.float64)
    gids = np.array([None] * (len(pr) + len(players)), dtype=object)
    for rix, row in enumerate(pr.itertuples()):
        on = list(row.on10)
        homes_set = set(on[:5])
        home_flag = bool(row.home)
        for aid in on:
            is_off = (aid in homes_set) == home_flag
            X[rix, pidx[aid]] = 1.0 if is_off else -1.0
        X[rix, nP] = 1.0 if home_flag else -1.0
        y[rix] = float(row.pts)
        gids[rix] = row.gid
    n_real = len(pr)
    y[:n_real] -= y[:n_real].mean()
    # prior rows
    n_prior_rows = 0
    for i, p in enumerate(players):
        if p not in prior_of:
            continue
        rix = n_real + n_prior_rows
        X[rix, pidx[p]] = 1.0
        y[rix] = prior_of[p][0] / 100.0
        w[rix] = TAU
        n_prior_rows += 1
    print(f"design: {n_real:,} possession rows + {n_prior_rows} prior rows")

    # ---- λ by 5-fold game-grouped CV (possession rows only) ----------------
    uniq = pd.unique(gids[:n_real])
    folds = {g: i % 5 for i, g in enumerate(sorted(uniq))}
    f = np.array([folds.get(g, 0) for g in gids])
    cv = {}
    for lam in LAMBDA_GRID:
        sse = 0.0
        for k in range(5):
            tr = (f != k) | (np.arange(len(y)) >= n_real)  # priors train always
            te = (f == k) & (np.arange(len(y)) < n_real)
            beta = fit_ridge(X[tr], y[tr], w[tr], lam)
            pred = X @ beta
            gg = pr.iloc[np.where(te)[0]].copy()
            gg["pred"] = pred[te]
            agg2 = gg.groupby(["gid", "team"]).agg(pred=("pred", "sum"),
                                                   actual=("pts", "sum"),
                                                   home=("home", "first")).reset_index()
            piv_p = agg2.pivot(index="gid", columns="home", values="pred")
            piv_a = agg2.pivot(index="gid", columns="home", values="actual")
            if True in piv_p.columns and False in piv_p.columns:
                sse += float(((piv_p[True] - piv_p[False]) - (piv_a[True] - piv_a[False])).pow(2).sum())
        cv[lam] = sse
        print(f"  λ={lam}: held-out game-margin SSE {cv[lam]:.0f}")

    # λ-sensitivity + gates (stability on real rows only)
    half = np.array([int(g) % 2 if g is not None else 0 for g in gids])
    ex = pd.DataFrame({"gid": gids[:n_real], "aid": pr.on10.tolist(), "half": half[:n_real]})
    ex = ex.explode("aid")
    ph = ex.groupby(["aid", "half"]).size().unstack(fill_value=0)
    sens_rows = []
    ratings = pd.DataFrame({"aid": players})
    for lam in LAMBDA_GRID:
        beta = fit_ridge(X, y, w, lam)
        ratings[f"rapm_{lam}"] = beta[:nP] * 100.0
        re_b = fit_ridge(X[half == 0], y[half == 0], w[half == 0], lam)
        ro_b = fit_ridge(X[half == 1], y[half == 1], w[half == 1], lam)
        dfe = pd.DataFrame({"aid": players, "r_e": re_b[:nP] * 100.0})
        dfo = pd.DataFrame({"aid": players, "r_o": ro_b[:nP] * 100.0})
        mg0 = dfe.merge(dfo, on="aid").merge(ph.rename(columns={0: "n_even", 1: "n_odd"}),
                                             on="aid", how="left")
        sel0 = mg0[(mg0.n_even >= 500) & (mg0.n_odd >= 500)]
        stab = float(sel0.r_e.corr(sel0.r_o)) if len(sel0) else float("nan")
        luma_f = Path.home() / "Projects/vt_baseball/hoops_mart/data/luma/xpts_rapm_2025.parquet"
        lg = pd.read_parquet(luma_f)
        pcnt = pr.explode("on10").groupby("on10").size().rename("poss")
        tmp = pd.DataFrame({"aid": players, "r": beta[:nP] * 100.0})
        tmp["poss"] = tmp.aid.map(pcnt)
        mrg = tmp.merge(lg[["pid", "xpts_net"]], left_on="aid", right_on=lg.pid.astype(str),
                        how="inner")
        selb = mrg[mrg.poss >= 250]
        bench = float(selb.r.corr(selb.xpts_net)) if len(selb) else float("nan")
        sens_rows.append({"lam": lam, "stability": round(stab, 3), "benchmark": round(bench, 3),
                          "n_stab": int(len(sel0)), "n_bench": int(len(selb))})
        print(f"  λ={lam}: stability {stab:.3f} | LUMA benchmark {bench:.3f}")

    lam_sel = min(cv, key=cv.get)                      # §7: verdict at the CV-selected λ, grid table beside it
    row_sel = next(r for r in sens_rows if r["lam"] == lam_sel)
    both = [r["lam"] for r in sens_rows if r["stability"] >= 0.60 and r["benchmark"] >= 0.70]
    gate_stab = "PASS" if row_sel["stability"] >= 0.60 else "FAIL"
    gate_b = "PASS" if row_sel["benchmark"] >= 0.70 else "FAIL"
    print(f"VERDICT at CV λ={lam_sel}: stability {gate_stab} ({row_sel['stability']}) | "
          f"benchmark {gate_b} ({row_sel['benchmark']} on {row_sel['n_bench']} players) | both gates at λ: {both}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    ratings.to_csv(RESULTS / "rapm_spm_players.csv", index=False)
    verdict = {"season": a.season, "tau": TAU, "lambda_cv": lam_sel, "cv": cv, "sensitivity": sens_rows,
               "gate_stability": gate_stab, "gate_benchmark": gate_b, "both_gates_at": both,
               "n_possessions": int(n_real), "n_players": nP, "n_prior_rows": int(n_prior_rows),
               "spm": spm_rep, "prior_coverage": cover}
    (RESULTS / "rapm_spm.json").write_text(json.dumps(verdict, indent=2, default=str))


if __name__ == "__main__":
    main()
