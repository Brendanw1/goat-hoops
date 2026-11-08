"""hoops_export.py — bake the basketball surfaces from the hoops mart.

    python pipeline/hoops_export.py             # full bake -> data/export/web/
    python pipeline/hoops_export.py --check     # verify a re-bake is a no-op, write nothing

This repo's keys sit at the TOP LEVEL of its export dir; the r2 sync prefixes
them with hoops/ on R2 (R2_PREFIX=hoops on the web side), so the baseball
sibling's goatpro/ keys are never touched.

Descriptive Phase 1 (docs/basketball-site-plan.md): box scores, game lists,
the x/y shot chart, the play feed — every number is a raw mart value or a
plain average/per-36. No model outputs; those arrive with pre-registered
phases. The mart is validated against LUMA (hoops_mart luma_check.py, gate
passed 2026-10-29) and meta.json carries that credit.

Files (keys under the hoops/ prefix on R2; goatpro/ is the sibling's):
  meta.json                    seasons, counts, validation + LUMA credit
  games_{season}.json          every game of a season (landing + finders)
  game/{gid}.json.gz           the game report: header, boxes, shots, plays
  teams.json                   team-season aggregates (the teams board)
  team/{abbr}.json.gz          one club: season aggregates + game list
  players.json                 player-season board rows (leaderboard)
  player/{id}.json.gz          one player: season lines + game log
  contracts.json               balldontlie deal/salary snapshot, name-bridged
                               to ESPN ids (docs/bdl-profile-schemas.md)
"""

import argparse
import gzip
import json
import os
import sys
import tempfile
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "export" / "web"
MART = Path(os.environ.get("HOOPS_MART",
                           Path.home() / "Projects" / "vt_baseball" / "hoops_mart" / "data" / "mart"))
BDL = MART.parent / "bdl"

TYPE_LABEL = {1: "preseason", 2: "regular", 3: "postseason"}
# ESPN abbreviations -> franchise names (static; the mart carries ids/abbrs
# only). ESPN spells them GS/NO/NY/SA/UTAH/WSH — not LUMA's GSW/NOP/….
NBA_TEAMS = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls",
    "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets", "DET": "Pistons",
    "GS": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers",
    "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat", "MIL": "Bucks",
    "MIN": "Timberwolves", "NO": "Pelicans", "NY": "Knicks", "OKC": "Thunder",
    "ORL": "Magic", "PHI": "76ers", "PHX": "Suns", "POR": "Trail Blazers",
    "SAC": "Kings", "SA": "Spurs", "TOR": "Raptors", "UTAH": "Jazz", "WSH": "Wizards",
}
# balldontlie's abbreviations are the standard ones; ESPN's six oddballs:
BDL_ABBR2ESPN = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def norm_name(s) -> str | None:
    """The name bridge used for the LUMA join: lowercase, punctuation off,
    generational suffixes off, diacritics folded (ESPN 'Dončić' vs BDL
    'Doncic'), collapsed spaces."""
    try:
        if s is None or pd.isna(s):
            return None
    except (TypeError, ValueError):
        pass
    t = unicodedata.normalize("NFD", str(s).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace(".", "").replace("'", "").replace("-", " ")
    toks = [t for t in t.split() if t and t not in _NAME_SUFFIXES]
    return " ".join(toks) or None


def clean(obj):
    """NaN floats (parquet Nones round-tripped) -> None; allow_nan=False stays honest."""
    if isinstance(obj, float):
        return None if obj != obj else obj
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def jwrite(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), allow_nan=False, sort_keys=True))


def jwrite_gz(path: Path, obj) -> None:
    """mtime=0 keeps the archive byte-identical across bakes (the --check no-op)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(clean(obj), allow_nan=False, sort_keys=True).encode()
    path.write_bytes(gzip.compress(data, mtime=0))


def iv(x):
    """NaN/pd.NA-safe int (parquet round-trips None as NaN in object columns)."""
    try:
        if x is None or pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return int(x)


def fv(x):
    try:
        if x is None or pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(x), 1)


def season_label(y: int) -> str:
    return f"{y - 1}-{str(y)[2:]}"


# ---------------------------------------------------------------------------
# balldontlie GOAT-trial layers (2026-11 harvest; data/bdl read-only).
# Box seasons 2023/2024 merge into the boards and logs (the ESPN mart only
# carries 2025 + live 2027); v2-advanced per-game rows roll up to season
# rates; seasavgs history becomes career arcs; standings land as their own
# doc. All descriptive. The republication note rides in every doc: public
# surfaces carry balldontlie numbers only while a subscription is active.

def site_season(bdl_year) -> int:
    """BDL season keys are the season's STARTING year (2025 = 2025-26); the
    site labels seasons by ENDING year (ESPN convention, 2025 = 2024-25).
    One hop, applied at bake so the site keeps a single convention."""
    return int(bdl_year) + 1

BDL_BOX_SOURCES = {2024: "2023", 2026: "2025"}  # site label -> BDL season pull
BDL_CHECK = ("2024", 2025)  # BDL 2024 (2024-25) vs ESPN season_year 2025

# season-key -> v2-advanced row column. Rates are minutes-weighted means
# (possessions where no minutes source exists — documented in the doc note).
ADV_RATE_COLS = {
    "ts_pct": "true_shooting_percentage", "efg_pct": "effective_field_goal_percentage",
    "usg_pct": "usage_percentage", "ast_pct": "assist_percentage",
    "orb_pct": "offensive_rebound_percentage", "drb_pct": "defensive_rebound_percentage",
    "reb_pct": "rebound_percentage", "ast_to": "assist_to_turnover",
    "to_ratio": "turnover_ratio", "ortg": "offensive_rating", "drtg": "defensive_rating",
    "net": "net_rating", "est_ortg": "estimated_offensive_rating",
    "est_drtg": "estimated_defensive_rating", "est_net": "estimated_net_rating",
    "est_pace": "estimated_pace", "pace": "pace", "pie": "pie",
    "ff_efg": "four_factors_efg_pct", "ftr": "free_throw_attempt_rate",
    "ff_oreb": "four_factors_oreb_pct", "opp_efg": "opp_efg_pct",
    "opp_ftr": "opp_free_throw_attempt_rate", "opp_oreb": "opp_oreb_pct",
    "opp_tov": "opp_turnover_pct", "pct_fga_3pt": "pct_fga_3pt",
    "pct_pts_paint": "pct_pts_paint", "pct_pts_3pt": "pct_pts_3pt",
    "pct_pts_ft": "pct_pts_free_throw", "pct_pts_fb": "pct_pts_fast_break",
    "pct_pts_to": "pct_pts_off_turnovers", "pct_ast_fgm": "pct_assisted_fgm",
    "pct_unast_fgm": "pct_unassisted_fgm", "pct_pts": "pct_points",
    "pct_fga": "pct_fga", "pct_reb": "pct_rebounds_total", "pct_stl": "pct_steals",
    "pct_blk": "pct_blocks", "pct_tov": "pct_turnovers",
    "speed": "speed", "distance": "distance",
}
# counting fields -> shipped per-36 (minutes summed from the box join)
ADV_COUNT_COLS = {
    "deflections": "deflections", "contested": "contested_shots",
    "charges": "charges_drawn", "boxouts": "box_outs", "screen_ast": "screen_assists",
    "screen_ast_pts": "screen_assist_points", "loose": "loose_balls_recovered_total",
    "passes": "passes", "touches": "touches", "sec_ast": "secondary_assists",
    "ft_ast": "free_throw_assists", "reb_ch": "rebound_chances_total",
    "reb_ch_d": "rebound_chances_def", "reb_ch_o": "rebound_chances_off",
    "matchup_min": "matchup_minutes", "matchup_fga": "matchup_fga",
    "matchup_fgm": "matchup_fgm", "matchup_3pa": "matchup_3pa",
    "matchup_3pm": "matchup_3pm", "matchup_pts": "matchup_player_points",
    "contested_fga": "contested_fga", "contested_fgm": "contested_fgm",
    "d_rim_fga": "defended_at_rim_fga", "d_rim_fgm": "defended_at_rim_fgm",
    "blka": "blocks_against", "fouls_drawn": "fouls_drawn",
    "poss": "possessions", "switches": "switches_on",
}
# ratios rebuilt from their sums (a mean of per-game ratios is not the season ratio)
ADV_DERIVED = {
    "matchup_fg_pct": ("matchup_fgm", "matchup_fga"),
    "matchup_3pt_pct": ("matchup_3pm", "matchup_3pa"),
    "contested_fg_pct": ("contested_fgm", "contested_fga"),
    "d_rim_fg_pct": ("d_rim_fgm", "d_rim_fga"),
}
# fields where LOW is the good end (defense/allowances) — the site's
# good/bad coloring flips on these
ADV_LOWER_BETTER = ("drtg", "est_drtg", "opp_efg", "opp_ftr", "opp_oreb", "opp_tov",
                    "matchup_fg_pct", "matchup_3pt_pct", "contested_fg_pct", "d_rim_fg_pct")

ADV_NOTES = ("season roll-ups of balldontlie v2-advanced game rows (GOAT-trial harvest "
             "2026-11): rates are minutes-weighted means, possessions-weighted where the box "
             "join (2023+) gives no minutes; counting fields are per-36; ratio fields are "
             "rebuilt from sums; 'league' holds mean + p10/p25/p50/p75/p90 of player-season "
             "values (gp>=5) for the site's good/bad coloring. internal research — public "
             "surfaces carry these only while a subscription is active")


def flatten_bdl_row(r: dict) -> dict:
    """balldontlie stats rows arrive nested (game/player/team dicts) in the
    page dumps and flat ('game.id') in the parquets — one shape for both."""
    out = {}
    for k, v in r.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out[f"{k}.{k2}"] = v2
        else:
            out[k] = v
    return out


def load_bdl_box(season: str) -> pd.DataFrame:
    """Box rows for one season: the parquet if the pull completed, else its
    pages.jsonl (2023 finished as pages only)."""
    f = BDL / f"stats_{season}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    f = BDL / f"stats_{season}.pages.jsonl"
    if not f.exists():
        return pd.DataFrame()
    rows = [flatten_bdl_row(r) for line in f.read_text().splitlines() if line.strip()
            for r in json.loads(line).get("rows", [])]
    return pd.DataFrame(rows)


BDL_NUM_COLS = ("min", "pts", "reb", "ast", "stl", "blk", "turnover", "pf", "plus_minus",
                "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb")


def bdl_box_ready(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric coercions + played-minutes filter + ESPN id/abbr attach."""
    df = df.copy()
    for c in BDL_NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["min"].fillna(0) > 0]
    df["eid"] = df["player.id"].map(
        lambda p: bdl2espn_of.get(int(p)) if pd.notna(p) else None).astype("object")
    df = df[df["eid"].notna()]
    df["abbr"] = df["team.id"].map(
        lambda t: bdl_team_abbr.get(int(t)) if pd.notna(t) else None)
    return df


def bdl_games_index(df: pd.DataFrame) -> pd.DataFrame:
    """One row per game (scores/flags repeat on every box row)."""
    cols = ["game.id", "game.date", "game.home_team_id", "game.home_team_score",
            "game.visitor_team_id", "game.visitor_team_score", "game.postseason",
            "game.period", "game.home_ot1", "game.home_ot2", "game.home_ot3"]
    return df[[c for c in cols if c in df.columns]].drop_duplicates("game.id").set_index("game.id")


def bdl_ot(gi_row) -> int | None:
    n = sum(1 for c in ("game.home_ot1", "game.home_ot2", "game.home_ot3")
            if c in gi_row.index and pd.notna(gi_row[c]) and gi_row[c] and gi_row[c] > 0)
    return n or None


# --- P1 team tier: pace / four factors / ratings (§0d-gated) ------------------

ANALYTICS_NUM = ("pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb",
                 "dreb", "reb", "ast", "stl", "blk", "turnover")
# site label -> BDL box pull label (BDL keys are starting years)
BDL_TEAM_ANALYTICS = {2024: "2023", 2025: "2024", 2026: "2025"}
ESPN_TEAM_ANALYTICS = 2027  # live season: ESPN mart only, always PARTIAL
ANALYTICS_FULL_AT = 1200    # team-games; below this a season block ships partial-flagged


def _team_grain_bdl(raw: pd.DataFrame) -> pd.DataFrame:
    """(game, team) box sums from RAW balldontlie rows. §0d fixed rule: the
    eid/name-bridge filter stays OFF — the bridge exists for player docs, and
    a team total must not silently lose an unmapped player. min>0 drops DNP
    rows; postseason rows are excluded (regular season only)."""
    df = raw.copy()
    for c in BDL_NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["min"].fillna(0) > 0]
    if "game.postseason" in df.columns:
        df = df[~df["game.postseason"].fillna(False).astype(bool)]
    df["abbr"] = df["team.id"].map(
        lambda t: bdl_team_abbr.get(int(t)) if pd.notna(t) else None)
    df = df[df["abbr"].isin(NBA_TEAMS)]
    df["date"] = df["game.date"].map(lambda d: str(d)[:10])
    df["ot"] = pd.to_numeric(df["game.period"], errors="coerce").map(
        lambda p: max(0, int(p) - 4) if pd.notna(p) else 0)
    df = df.rename(columns={"game.id": "game_id"})
    cols = [c for c in ANALYTICS_NUM if c in df.columns]
    return df.groupby(["game_id", "abbr", "date", "ot"])[cols].sum().reset_index()


def _team_grain_espn(tgx: pd.DataFrame, gg: pd.DataFrame, id2abbr) -> pd.DataFrame:
    """The same (game, team) grain from the ESPN mart (live seasons)."""
    t = tgx.copy()
    t["abbr"] = t["team_id"].map(lambda x: id2abbr.get(str(int(x))))
    t = t[t["abbr"].isin(NBA_TEAMS) & t["game_id"].isin(gg.index)]
    t = t.join(gg[["date_et", "n_periods", "season_type"]], on="game_id")
    t = t[t["season_type"] == 2]
    t["date"] = t["date_et"].map(lambda d: str(d)[:10])
    t["ot"] = t["n_periods"].map(lambda p: max(0, int(p or 4) - 4))
    ren = {"points": "pts",
           "fieldGoalsMade-fieldGoalsAttempted_made": "fgm",
           "fieldGoalsMade-fieldGoalsAttempted_att": "fga",
           "threePointFieldGoalsMade-threePointFieldGoalsAttempted_made": "fg3m",
           "threePointFieldGoalsMade-threePointFieldGoalsAttempted_att": "fg3a",
           "freeThrowsMade-freeThrowsAttempted_made": "ftm",
           "freeThrowsMade-freeThrowsAttempted_att": "fta",
           "totalRebounds": "reb", "offensiveRebounds": "oreb",
           "defensiveRebounds": "dreb", "assists": "ast", "steals": "stl",
           "blocks": "blk", "totalTurnovers": "turnover"}
    t = t.rename(columns=ren)
    cols = [c for c in ANALYTICS_NUM if c in t.columns]
    return t.groupby(["game_id", "abbr", "date", "ot"])[cols].sum().reset_index()


def _attach_opponent(g: pd.DataFrame) -> pd.DataFrame:
    """Each (game, team) row gains the same game's other side (`_o` suffix).
    Games that don't yield exactly two sides drop out."""
    m = g.merge(g, on="game_id", suffixes=("", "_o"))
    return m[m["abbr"] != m["abbr_o"]].reset_index(drop=True)


def team_analytics_block(g: pd.DataFrame) -> tuple[dict, dict]:
    """Per-team and league analytics off the (game, team) grain. §0d rules:
    aggregate-then-divide (Σ/Σ, never a mean of ratios), two-sided
    possessions, minutes = 240 + 25·OT. ORtg/DRtg divide opponent points by
    the same possessions (the two sides of one possession count)."""
    m = _attach_opponent(g)
    if m.empty:
        return {}, {}
    m["poss_own"] = m["fga"] - m["oreb"] + m["turnover"] + 0.44 * m["fta"]
    m["poss_opp"] = m["fga_o"] - m["oreb_o"] + m["turnover_o"] + 0.44 * m["fta_o"]
    m["poss"] = 0.5 * (m["poss_own"] + m["poss_opp"])
    m["min"] = 48 + 5 * m["ot"]  # team-minutes on the clock (5 players × game min)
    sums = ["pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb",
            "reb", "ast", "stl", "blk", "turnover",
            "pts_o", "fga_o", "fta_o", "fgm_o", "fg3m_o", "oreb_o", "dreb_o",
            "turnover_o", "poss_own", "poss_opp", "poss", "min"]

    def derived(r) -> dict:
        fga, fta = r["fga"], r["fta"]
        opp_fga, opp_fta = r["fga_o"], r["fta_o"]
        to = r["turnover"] + fga + 0.44 * fta
        opp_to = r["turnover_o"] + opp_fga + 0.44 * opp_fta
        d = {
            "ortg": r_(100 * r["pts"] / r["poss_own"]),
            "drtg": r_(100 * r["pts_o"] / r["poss_own"]),
            "net": None,  # filled right after, from the unrounded pair
            "efg": round((r["fgm"] + 0.5 * r["fg3m"]) / fga, 3),
            "tsp": round(r["pts"] / (2 * (fga + 0.44 * fta)), 3),
            "fg3ar": round(r["fg3a"] / fga, 3),
            "ftr": round(fta / fga, 3),
            "tov_pct": round(r["turnover"] / to, 3),
            "orb_pct": round(r["oreb"] / (r["oreb"] + r["dreb_o"]), 3),
            "drb_pct": round(r["dreb"] / (r["dreb"] + r["oreb_o"]), 3),
            "opp_efg": round((r["fgm_o"] + 0.5 * r["fg3m_o"]) / opp_fga, 3),
            "opp_tsp": round(r["pts_o"] / (2 * (opp_fga + 0.44 * opp_fta)), 3),
            "opp_tov_pct": round(r["turnover_o"] / opp_to, 3),
            "opp_orb_pct": round(r["oreb_o"] / (r["oreb_o"] + r["dreb"]), 3)}
        d["net"] = round(d["ortg"] - d["drtg"], 1) if d["ortg"] is not None and d["drtg"] is not None else None
        return d

    out = {}
    for abbr, r in m.groupby("abbr"):
        s = r[sums].sum()
        row = {"pace": round(48 * s["poss"] / s["min"], 1),
               "poss_g": round(s["poss"] / len(r), 1)}
        row.update(derived(s))
        out[abbr] = row
    s = m[sums].sum()
    env = {"pace": round(48 * s["poss"] / s["min"], 1),
           "poss_g": round(s["poss"] / len(m), 1)}
    env.update(derived(s))
    return out, {"league": env, "teams": out}


def r_(x) -> float | None:
    """Ratings round to 1 decimal; None-safe."""
    return None if x is None or pd.isna(x) else round(float(x), 1)


def merge_bdl_team_analytics(team_seasons, season_rows, counts,
                             tgx, gg, id2abbr) -> dict:
    """§0d-gated team analytics into team docs + teams.json. The site-2025
    BDL sums must first clear the preregistered agreement bars vs the ESPN
    official team boxes; a miss stops the bake before anything renders."""
    ge = _team_grain_espn(tgx, gg, id2abbr)
    gb25 = _team_grain_bdl(load_bdl_box(BDL_TEAM_ANALYTICS[2025]))
    ge25 = ge[ge["game_id"].map(
        lambda gid: int(gg.loc[gid].season_year) == 2025)] if not ge.empty else ge
    gate = {"label": "§0d BDL-summed team boxes vs ESPN team_game (site 2025)"}
    if gb25.empty or ge25.empty:
        gate["verdict"] = "SKIP (empty grain)"
    else:
        m = gb25.merge(ge25, on=["date", "abbr"], suffixes=("_b", "_e"))
        bars = {"pts": .99, "reb": .99, "fga": .99, "ftm": .99,
                "ast": .97, "oreb": .97, "stl": .97, "blk": .97}
        cols, failed = {}, []
        for c, bar in bars.items():
            if f"{c}_b" not in m or f"{c}_e" not in m:
                continue
            rate = float((m[f"{c}_b"] - m[f"{c}_e"]).abs().lt(1e-6).mean())
            cols[c] = round(rate, 4)
            if rate < bar:
                failed.append(f"{c} {rate:.3f}<{bar}")
        gate["matched_team_games"] = int(len(m))
        gate["rates"] = cols
        gate["tov_delta_per_game"] = round(
            float((m["turnover_e"] - m["turnover_b"]).mean()), 2) if "turnover_e" in m else None
        if failed:
            gate["verdict"] = "FAIL"
            print("§0d gate FAILED:", json.dumps(gate, indent=1))
            raise SystemExit("§0d team-analytics gate failed: " + "; ".join(failed))
        gate["verdict"] = "PASS"
        print("§0d gate PASS:", json.dumps(gate))
    counts["team_gate_0d"] = gate.get("verdict", "SKIP")

    league = {}
    for season, bdl_label in BDL_TEAM_ANALYTICS.items():
        g = _team_grain_bdl(load_bdl_box(bdl_label))
        if g.empty:
            continue
        teams, pkg = team_analytics_block(g)
        partial = len(g) < ANALYTICS_FULL_AT
        league[season] = {**pkg["league"], "partial": partial, "src": "bdl"}
        for abbr, row in teams.items():
            block = {**row, "partial": partial, "src": "bdl"}
            if abbr in team_seasons and season in team_seasons[abbr]:
                team_seasons[abbr][season]["analytics"] = block
        for r in season_rows.get(season, []):
            if r["abbr"] in teams:
                r["analytics"] = {**teams[r["abbr"]], "partial": partial, "src": "bdl"}
        counts[f"team_analytics_{season}"] = len(teams)
    ge27 = ge[ge["game_id"].map(
        lambda gid: int(gg.loc[gid].season_year) == ESPN_TEAM_ANALYTICS)] if not ge.empty else ge
    if not ge27.empty:
        teams, pkg = team_analytics_block(ge27)
        league[ESPN_TEAM_ANALYTICS] = {**pkg["league"], "partial": True, "src": "espn"}
        for abbr, row in teams.items():
            block = {**row, "partial": True, "src": "espn"}
            if abbr in team_seasons and ESPN_TEAM_ANALYTICS in team_seasons[abbr]:
                team_seasons[abbr][ESPN_TEAM_ANALYTICS]["analytics"] = block
        for r in season_rows.get(ESPN_TEAM_ANALYTICS, []):
            if r["abbr"] in teams:
                r["analytics"] = {**teams[r["abbr"]], "partial": True, "src": "espn"}
        counts[f"team_analytics_{ESPN_TEAM_ANALYTICS}"] = len(teams)
    return {"gate": gate, "league": league}


# espn-id/abbr bridges shared with the box phases (set inside bake(); module
# globals keep the helpers' signatures small)
bdl2espn_of: dict[int, int] = {}
bdl_team_abbr: dict[int, str] = {}


def day_diff(a: str, b: str) -> int:
    """Calendar days between two YYYY-MM-DD strings (rest-day grain)."""
    from datetime import date
    ya, ma, da = map(int, a.split("-"))
    yb, mb, db = map(int, b.split("-"))
    return (date(ya, ma, da) - date(yb, mb, db)).days


def schedule_splits(doc: dict, opp_records: dict) -> None:
    """Cut each season's game log into the METRICS.md splits — rest (B2B/1/2+),
    venue, opponent tier (final-season record) — from the game-log grain.
    Neutral rendering: these are context cuts, not grades; buckets under 10
    games are flagged by the site. MUTATES doc in place."""
    num = ("min", "pts", "reb", "ast", "stl", "blk", "tov")
    for season, sdoc in doc["seasons"].items():
        games = sdoc.get("games") or []
        if len(games) < 5:
            continue
        buckets: dict[str, dict] = {}

        def add(key: str, g: dict):
            b = buckets.setdefault(key, {"g": 0, **{k: 0.0 for k in num}})
            b["g"] += 1
            for k in num:
                v = g.get(k)
                if isinstance(v, (int, float)):
                    b[k] += v

        rec = opp_records.get(int(season), {})
        prev_date = None
        for g in sorted(games, key=lambda x: x["date"]):
            opp = g.get("opp")
            ow, ol = rec.get(opp, (None, None))
            tier = None
            if ow is not None and (ow + ol) > 0:
                tier = "vs_top" if ow / (ow + ol) >= 0.5 else "vs_bottom"
            add("venue_" + ("home" if g.get("home") else "away"), g)
            if tier:
                add(tier, g)
            if prev_date is not None:
                d = day_diff(g["date"], prev_date)
                add("rest_" + ("b2b" if d <= 0 else "one" if d == 1 else "two_plus"), g)
            prev_date = g["date"]
        out = {}
        for key, b in buckets.items():
            dim, _, val = key.partition("_")
            out.setdefault(dim, {})[val] = {
                "g": b["g"],
                **{k: round(b[k] / b["g"], 1) for k in num}}
        sdoc["splits"] = out


def merge_bdl_box(board, pdocs, team_seasons, season_rows, out, counts) -> dict:
    """Seasons the ESPN mart lacks (2022-23, 2023-24) from balldontlie box rows:
    games list, board rows, player season lines + game logs, team aggregates.
    BDL game ids live in their own namespace — log rows carry ext:1 and the
    site renders them without a game-page link."""
    added = {}
    for season, bdl_year in BDL_BOX_SOURCES.items():
        raw = load_bdl_box(bdl_year)
        if raw.empty:
            print(f"bdl box {season}: no rows — skipped")
            continue
        gi = bdl_games_index(raw)
        df = bdl_box_ready(raw)
        # one name lookup per player (the register names, not the deal feed's)
        name_by_eid: dict[int, str] = {}
        fn_col = "player.first_name" if "player.first_name" in df.columns else None
        ln_col = "player.last_name" if "player.last_name" in df.columns else None
        if fn_col and ln_col:
            first = df.groupby("eid")[fn_col].first()
            last = df.groupby("eid")[ln_col].first()
            for eid in first.index:
                nm = f"{first[eid]} {last[eid]}".strip()
                if nm:
                    name_by_eid[int(eid)] = nm
        # games_{season}.json -------------------------------------------------
        glist = []
        for gid, gr in gi.iterrows():
            home = bdl_team_abbr.get(int(gr["game.home_team_id"]))
            away = bdl_team_abbr.get(int(gr["game.visitor_team_id"]))
            if home not in NBA_TEAMS or away not in NBA_TEAMS:
                continue
            glist.append({"id": str(gid), "date": str(gr["game.date"])[:10], "season": int(season),
                          "type": "postseason" if gr["game.postseason"] else "regular",
                          "away": away, "home": home,
                          "away_score": int(gr["game.visitor_team_score"]),
                          "home_score": int(gr["game.home_team_score"]),
                          "ot": bdl_ot(gr)})
        if not glist:
            continue
        glist.sort(key=lambda r: r["date"], reverse=True)
        jwrite(out / f"games_{season}.json", {"season": int(season),
                                              "label": season_label(int(season)),
                                              "games": glist})
        added[season] = {"games": len(glist), "first": min(r["date"] for r in glist),
                         "last": max(r["date"] for r in glist), "source": "bdl"}
        counts[f"bdl_games_{season}"] = len(glist)
        # board rows ----------------------------------------------------------
        seas_board = []
        for eid, rows in df.groupby("eid"):
            eid = int(eid)
            mins, gp = float(rows["min"].sum()), len(rows)
            team = rows["abbr"].dropna().mode()
            pos_col = "player.position" if "player.position" in rows.columns else None
            pos = rows[pos_col].dropna().mode() if pos_col else pd.Series(dtype="object")
            seas_board.append({"id": str(eid), "name": name_by_eid.get(eid) or pdocs_name(pdocs, eid),
                               "pos": pos.iloc[0] if len(pos) else None,
                               "team": team.iloc[0] if len(team) else None,
                               "gp": gp, "gs": None, "src": "bdl",
                               "min": fv(mins / gp),
                               "pts": fv(rows["pts"].mean()), "reb": fv(rows["reb"].mean()),
                               "ast": fv(rows["ast"].mean()), "stl": fv(rows["stl"].mean()),
                               "blk": fv(rows["blk"].mean()), "tov": fv(rows["turnover"].mean()),
                               "oreb": fv(rows["oreb"].mean()), "dreb": fv(rows["dreb"].mean()),
                               "pts36": per36(rows["pts"].sum(), mins),
                               "reb36": per36(rows["reb"].sum(), mins),
                               "ast36": per36(rows["ast"].sum(), mins),
                               "fgp": sv_ratio(rows["fgm"].sum(), rows["fga"].sum()),
                               "tpp": sv_ratio(rows["fg3m"].sum(), rows["fg3a"].sum()),
                               "ftp": sv_ratio(rows["ftm"].sum(), rows["fta"].sum())})
        seas_board.sort(key=lambda r: -(r["pts"] or 0))
        board[int(season)] = seas_board
        counts[f"bdl_board_{season}"] = len(seas_board)
        # team aggregates + team-game lists -----------------------------------
        num = [c for c in ("pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
                           "reb", "oreb", "dreb", "ast", "stl", "blk", "turnover") if c in df.columns]
        tg = df.groupby(["game.id", "abbr"])[num].sum()
        games_by_team: dict[str, list] = {}
        for r in glist:
            for side in ("home", "away"):
                pts, opp_pts = (r["home_score"], r["away_score"]) if side == "home" \
                    else (r["away_score"], r["home_score"])
                games_by_team.setdefault(r[side], []).append(
                    {"id": r["id"], "date": r["date"], "type": r["type"],
                     "opp": r["away"] if side == "home" else r["home"],
                     "home": side == "home", "ext": 1,
                     "pts": pts, "opp_pts": opp_pts,
                     "res": "W" if pts > opp_pts else ("L" if pts < opp_pts else "T")})
        for abbr in sorted({a for a in games_by_team if a in NBA_TEAMS}):
            trows = tg.xs(abbr, level=1) if abbr in tg.index.get_level_values(1) else None
            if trows is None or trows.empty:
                continue
            gl = sorted(games_by_team.get(abbr, []), key=lambda r: r["date"], reverse=True)
            w = sum(1 for r in gl if r["res"] == "W")
            l = sum(1 for r in gl if r["res"] == "L")
            agg = {"abbr": abbr, "name": NBA_TEAMS[abbr], "g": len(gl), "w": w, "l": l,
                   "pts": fv(trows["pts"].mean()),
                   "opp_pts": fv(sum(r["opp_pts"] for r in gl) / len(gl)) if gl else None,
                   "fgm": fv(trows["fgm"].mean()), "fga": fv(trows["fga"].mean()),
                   "tpm": fv(trows["fg3m"].mean()), "tpa": fv(trows["fg3a"].mean()),
                   "ftm": fv(trows["ftm"].mean()), "fta": fv(trows["fta"].mean()),
                   "reb": fv(trows["reb"].mean()), "ast": fv(trows["ast"].mean()),
                   "tov": fv(trows["turnover"].mean()), "stl": fv(trows["stl"].mean()),
                   "blk": fv(trows["blk"].mean()), "paint": None, "fastbreak": None,
                   "src": "bdl"}
            season_rows.setdefault(int(season), []).append(agg)
            team_seasons.setdefault(abbr, {})[int(season)] = {**agg, "games": gl}
        # player docs ----------------------------------------------------------
        for eid, rows in df.groupby("eid"):
            doc = pdocs.get(str(int(eid)))
            if doc is None:
                continue
            mins, gp = float(rows["min"].sum()), len(rows)
            team = rows["abbr"].dropna().mode()
            games = []
            for _, r in rows.sort_values("game.date").iterrows():
                htid = int(r["game.home_team_id"])
                tid = int(r["team.id"])
                home = htid == tid
                hs, as_ = int(r["game.home_team_score"]), int(r["game.visitor_team_score"])
                pts, ops = (hs, as_) if home else (as_, hs)
                games.append({"id": str(int(r["game.id"])), "date": str(r["game.date"])[:10],
                              "opp": bdl_team_abbr.get(int(r["game.visitor_team_id"] if home
                                                       else r["game.home_team_id"])),
                              "home": home, "res": "W" if pts > ops else ("L" if pts < ops else "T"),
                              "ext": 1, "min": iv(r["min"]), "pts": iv(r["pts"]), "reb": iv(r["reb"]),
                              "ast": iv(r["ast"]), "stl": iv(r["stl"]), "blk": iv(r["blk"]),
                              "tov": iv(r["turnover"]), "pf": iv(r["pf"]), "pm": iv(r["plus_minus"]),
                              "fg": fg_str(r["fgm"], r["fga"]), "tp": fg_str(r["fg3m"], r["fg3a"]),
                              "ft": fg_str(r["ftm"], r["fta"])})
            doc["seasons"][int(season)] = {
                "team": team.iloc[0] if len(team) else None, "gp": gp, "gs": None,
                "totals": {"min": round(mins, 1), "pts": int(rows["pts"].sum()),
                           "reb": int(rows["reb"].sum()), "ast": int(rows["ast"].sum()),
                           "stl": int(rows["stl"].sum()), "blk": int(rows["blk"].sum()),
                           "tov": int(rows["turnover"].sum())},
                "per_game": {"min": fv(mins / gp), "pts": fv(rows["pts"].mean()),
                             "reb": fv(rows["reb"].mean()), "ast": fv(rows["ast"].mean()),
                             "stl": fv(rows["stl"].mean()), "blk": fv(rows["blk"].mean()),
                             "tov": fv(rows["turnover"].mean())},
                "per36": {"pts": per36(rows["pts"].sum(), mins), "reb": per36(rows["reb"].sum(), mins),
                          "ast": per36(rows["ast"].sum(), mins)},
                "shoot": {"fg": [int(rows["fgm"].sum()), int(rows["fga"].sum())],
                          "tp": [int(rows["fg3m"].sum()), int(rows["fg3a"].sum())],
                          "ft": [int(rows["ftm"].sum()), int(rows["fta"].sum())],
                          "oreb": fv(rows["oreb"].mean()), "dreb": fv(rows["dreb"].mean())},
                "games": games}
        counts[f"bdl_players_{season}"] = len(df["eid"].unique())
    return added


def pdocs_name(pdocs, eid: int) -> str | None:
    d = pdocs.get(str(eid))
    return d["name"] if d else None


# site label -> the BDL starters pull (parquets carry per-game starting fives,
# NOT unit minutes/ratings — so this builds team continuity, honestly; BDL
# season keys are starting years, hence lineups_2025 -> site 2026)
BDL_STARTERS = {2026: "lineups_2025.parquet", 2027: "lineups_2026.parquet"}
STARTERS_FULL_SEASON_GAME_TEAMS = 1000  # below this, GS must not merge (partial pull)


def merge_bdl_starters(board, pdocs, team_seasons, counts) -> dict:
    """Team starting-five continuity from the BDL starters pulls, plus GS —
    but GS merges only from a near-complete pull (internal-consistency gate
    §0c: a (game, team) group rarely holds exactly 5 rows (~10% injury/
    re-registration noise); continuity units count ONLY exact-5 groups, and
    GS counts from a partial pull would silently undercount starts, so they
    wait for coverage)."""
    added = {}
    for site_season, fname in BDL_STARTERS.items():
        f = BDL / fname
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        df = df[df["starter"] == True]  # noqa: E712 — flag column
        groups = df.groupby(["game_id", "team.id"]).size()
        exact5 = groups[groups == 5]
        coverage = len(exact5) / len(groups) if len(groups) else 0
        added[site_season] = {"coverage": round(coverage, 4),
                              "game_teams": int(len(groups)),
                              "exact5": int(len(exact5)),
                              "gs_merged": False}
        counts[f"starters_{site_season}_coverage"] = round(coverage, 4)
        # GS only from a near-complete pull — a partial pull undercounts starts
        if len(groups) >= STARTERS_FULL_SEASON_GAME_TEAMS and coverage >= 0.95:
            gs = {}
            for pid, rows in df.groupby("player.id"):
                eid = bdl2espn_of.get(int(pid))
                if eid:
                    gs[str(eid)] = int(len(rows))
            for r in board.get(site_season, []):
                if r["gs"] is None and r["id"] in gs:
                    r["gs"] = gs[r["id"]]
            for eid, g in gs.items():
                doc = pdocs.get(eid)
                if doc and site_season in doc["seasons"]:
                    doc["seasons"][site_season]["gs"] = g
            added[site_season]["gs_merged"] = True
            counts[f"starters_{site_season}_gs"] = len(gs)
        # team continuity: most-used starting fives, exact-5 groups only
        for (gid, tid), rows in df.groupby(["game_id", "team.id"]):
            if len(rows) != 5:
                continue
            abbr = bdl_team_abbr.get(int(tid))
            if abbr not in NBA_TEAMS:
                continue
            ids = sorted(str(int(p)) for p in rows["player.id"])
            key = "|".join(ids)
            names = [f"{fn} {ln}".strip() for fn, ln in
                     zip(rows["player.first_name"], rows["player.last_name"])]
            entry = team_seasons.setdefault(abbr, {}).setdefault(
                site_season, {}).setdefault("starters5", {})
            e = entry.setdefault(key, {"names": sorted(names), "g": 0})
            e["g"] += 1
        # keep only the top 3 units per team-season, as a list
        for abbr, seasons in team_seasons.items():
            doc5 = seasons.get(site_season, {}).get("starters5")
            if doc5:
                top = sorted(doc5.items(), key=lambda kv: -kv[1]["g"])[:3]
                seasons[site_season]["starters5"] = [
                    {"names": v["names"], "g": v["g"]} for _, v in top]
    return added


def sv_ratio(m, a):
    try:
        return round(float(m) / float(a), 3) if a and float(a) > 0 else None
    except (TypeError, ValueError):
        return None


def fg_str(m, a) -> str | None:
    m, a = iv(m), iv(a)
    return None if a is None else f"{m or 0}-{a}"


def bdl_espn_check(gg, pgx, id2abbr) -> dict:
    """Cross-source agreement on the overlapping season (BDL 2024 = the
    2024-25 season = ESPN season_year 2025): game scores by (date, home, away)
    and box lines by bridged (player, date, team). This is the bar the new
    source clears before its seasons render — the ESPN-source analogue of the
    LUMA gate."""
    bdl_year, espn_label = BDL_CHECK
    raw = load_bdl_box(bdl_year)
    if raw.empty:
        return {"note": f"no BDL {bdl_year} box rows"}
    gi = bdl_games_index(raw)
    b_score = {}
    for _, gr in gi.iterrows():
        home, away = (bdl_team_abbr.get(int(gr["game.home_team_id"])),
                      bdl_team_abbr.get(int(gr["game.visitor_team_id"])))
        if home in NBA_TEAMS and away in NBA_TEAMS:
            b_score[(str(gr["game.date"])[:10], home, away)] = (int(gr["game.home_team_score"]),
                                                                int(gr["game.visitor_team_score"]))
    matched = exact = 0
    for gid, gr in gg[gg.season_year == espn_label].iterrows():
        key = (str(gr.date_et)[:10], gr.home_abbr, gr.away_abbr)
        if key in b_score:
            hs, as_ = int(gr.home_score), int(gr.away_score)
            matched += 1
            exact += b_score[key] == (hs, as_)
    # boxes
    df = bdl_box_ready(raw)
    df["date"] = df["game.date"].map(lambda d: str(d)[:10])
    b = df[["eid", "date", "abbr", "pts", "reb", "ast", "min"]].copy()
    e = pgx[pgx.season_year == espn_label].copy()
    e = e[e.pts.notna()]
    e["date"] = e["game_id"].map(lambda gid: str(gg.loc[gid].date_et)[:10] if gid in gg.index else None)
    e["abbr"] = e["team_id"].map(lambda t: id2abbr.get(str(int(t))))
    e = e.rename(columns={"athlete_id": "eid", "to": "tov"})[["eid", "date", "abbr", "pts", "reb", "ast", "min"]]
    e["eid"] = e["eid"].astype("int64")
    b["eid"] = b["eid"].astype("int64")
    m = b.merge(e, on=["eid", "date", "abbr"], suffixes=("_b", "_e"))
    out = {"games": {"matched": matched, "score_exact": exact,
                     "score_exact_rate": round(exact / matched, 4) if matched else None,
                     "note": f"BDL {bdl_year} vs ESPN {espn_label} — the same 2024-25 season, two sources"},
           "boxes": {"matched": int(len(m))}}
    if len(m):
        for c in ("pts", "reb", "ast", "min"):
            diff = (m[f"{c}_b"] - m[f"{c}_e"]).abs()
            out["boxes"][f"{c}_exact"] = round(float((diff < 1e-9).mean()), 4)
            out["boxes"][f"{c}_mad"] = round(float(diff.mean()), 3)
    return out


def _num(v):
    """Numbers arrive as floats, ints, None/NaN — and some fields (matchup
    minutes) as 'MM:SS' time strings. One coercion for all of them."""
    if v is None:
        return None
    if isinstance(v, str):
        if ":" in v:
            try:
                m, s = v.split(":")
                return int(m) + int(s) / 60.0
            except ValueError:
                return None
        try:
            return float(v)
        except ValueError:
            return None
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _adv_scan_parquet(path: Path, wanted: list[str], seen: set, emit) -> int:
    df = pd.read_parquet(path)
    use = [c for c in wanted if c in df.columns]
    n = 0
    for r in df[use].itertuples(index=False):
        d = dict(zip(use, r))
        gid, pid = d.get("game.id"), d.get("player.id")
        if pd.isna(gid) or pd.isna(pid):
            continue
        key = (int(gid), int(pid))
        if key in seen:
            continue
        seen.add(key)
        emit(key, d)
        n += 1
    return n


def _adv_scan_jsonl(path: Path, seen: set, emit) -> int:
    """Stream the page dumps (several GB, each line one 100-row page); only
    unseen (game, player) keys are emitted, so overlapping walks dedup."""
    n = 0
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows = json.loads(line).get("rows", [])
            except json.JSONDecodeError:
                continue  # torn tail on a still-appending walk file
            for r in rows:
                d = flatten_bdl_row(r)
                gid, pid = d.get("game.id"), d.get("player.id")
                if gid is None or pid is None:
                    continue
                key = (int(gid), int(pid))
                if key in seen:
                    continue
                seen.add(key)
                emit(key, d)
                n += 1
    return n


def advagg_phase(out, counts) -> None:
    """advagg.json.gz — season roll-ups of the v2-advanced per-game rows across
    every recovered source (parquet snapshots + the page dumps, which hold the
    most). League block carries the distribution the site colors against."""
    rate_l = list(ADV_RATE_COLS.items())
    cnt_l = list(ADV_COUNT_COLS.items())
    wanted = ["game.id", "player.id", "game.season", "possessions"] + [c for _, c in rate_l] \
        + [c for _, c in cnt_l]
    seasons: dict[int, dict] = {}
    seen: set = set()
    games_seen: dict[int, set] = {}  # per site season: distinct games with advanced rows

    def bucket(season: int, eid) -> dict:
        ss = seasons.setdefault(season, {})
        key = "league" if eid is None else eid
        return ss.setdefault(key, {"gp": 0, "w": 0.0, "min": 0.0,
                                   "rate": [0.0] * len(rate_l),
                                   "cnt": [0.0] * len(cnt_l),
                                   "der": {k: [0.0, 0.0] for k in ADV_DERIVED}})

    def emit(key, d):
        try:
            season = site_season(d.get("game.season"))
        except (TypeError, ValueError):
            return
        rows_n[season] = rows_n.get(season, 0) + 1
        games_seen.setdefault(season, set()).add(int(d["game.id"]))
        eid = bdl2espn_of.get(int(d["player.id"]))
        lg = bucket(season, None)
        pl = bucket(season, eid) if eid else None
        poss = _num(d.get("possessions"))
        w = None
        for tgt in (lg, pl):
            if tgt is None:
                continue
            tgt["gp"] += 1
            if w is None:
                # weight: box minutes when the season has them, else possessions
                w = box_min.get((key[0], key[1])) or poss or 1.0
            tgt["w"] += w
            if w and w > 0 and box_min.get((key[0], key[1])):
                tgt["min"] += w
            for i, (_, col) in enumerate(rate_l):
                v = _num(d.get(col))
                if v is not None:
                    tgt["rate"][i] += v * w
            for i, (_, col) in enumerate(cnt_l):
                v = _num(d.get(col))
                if v is not None:
                    tgt["cnt"][i] += v
            for k, (nk, dk) in ADV_DERIVED.items():
                nv, dv = _num(d.get(ADV_COUNT_COLS[nk])), _num(d.get(ADV_COUNT_COLS[dk]))
                if nv is not None:
                    tgt["der"][k][0] += nv
                if dv is not None:
                    tgt["der"][k][1] += dv

    # minutes from the box seasons (2023+); the 2021/2022 advanced rows have no
    # minutes source, so their per-36 fields stay null and rates weight by poss
    box_min: dict[tuple, float] = {}
    for season in ("2023", "2024", "2025"):
        b = load_bdl_box(season)
        if b.empty:
            continue
        b = b[["game.id", "player.id", "min"]]
        b["min"] = pd.to_numeric(b["min"], errors="coerce")
        for gid, pid, mn in b.itertuples(index=False):
            if pd.notna(mn) and mn > 0:
                box_min[(int(gid), int(pid))] = float(mn)

    n_rows = 0
    rows_n: dict[int, int] = {}
    # jsonls first: the parquets are snapshots derived from them, so the live
    # dumps win on duplicate (game, player) keys
    for name in ("advanced_2024.pages.jsonl", "advanced_2025.pages.jsonl",
                 "advanced_2026.pages.jsonl"):
        p = BDL / name
        if p.exists():
            n_rows += _adv_scan_jsonl(p, seen, emit)
    for name in ("advanced_2023.parquet", "advanced_2024_salvaged.parquet",
                 "advanced_v2_checkpoints_recovered.parquet", "advanced_2026.parquet"):
        p = BDL / name
        if p.exists():
            n_rows += _adv_scan_parquet(p, wanted, seen, emit)
    counts["advagg_rows"] = n_rows
    counts["advagg_seen"] = len(seen)

    # coverage: distinct advanced games per site season vs the games spine —
    # a partial harvest must say so wherever its rates render
    spine: dict[int, int] = {}
    for season in seasons:
        gp_f = BDL / f"games_{season - 1}.parquet"  # site s = BDL starting-year s-1
        if gp_f.exists():
            try:
                spine[season] = int(pd.read_parquet(gp_f, columns=["id"])["id"].nunique())
            except Exception:
                pass
    coverage = {}
    for season in sorted(seasons):
        g = len(games_seen.get(season, ()))
        cov = {"games": g}
        if season in spine:
            cov["spine"] = spine[season]
            cov["full"] = g >= 0.95 * spine[season]
        coverage[int(season)] = cov

    seasons_out = {}
    league_out = {}
    for season in sorted(seasons):
        ss = seasons[season]
        lg = ss.pop("league")
        players_out = {}
        # collect player values for the league distribution
        dist: dict[str, list] = {}
        gp_min = 5
        for eid, b in ss.items():
            if b["gp"] < gp_min:
                continue
            mins = b["min"] if b["min"] > 0 else None
            entry = {"gp": b["gp"], "min": round(mins) if mins else None}
            for i, (short, _) in enumerate(rate_l):
                v = b["rate"][i] / b["w"] if b["w"] else None
                entry[short] = round(v, 3) if v is not None and v == v else None
                if entry[short] is not None:
                    dist.setdefault(short, []).append(entry[short])
            for i, (short, _) in enumerate(cnt_l):
                entry[short] = round(b["cnt"][i] * 36.0 / mins, 2) if mins else None
                if entry[short] is not None:
                    dist.setdefault(short, []).append(entry[short])
            for k in ADV_DERIVED:
                num, den = b["der"][k]
                v = num / den if den else None
                entry[k] = round(v, 3) if v is not None and v == v else None
                if entry[k] is not None:
                    dist.setdefault(k, []).append(entry[k])
            players_out[str(eid)] = entry
        lg_out = {"n": len(players_out), "rows": rows_n.get(season, 0)}
        for i, (short, _) in enumerate(rate_l):
            lg_out[short] = round(lg["rate"][i] / lg["w"], 3) if lg["w"] else None
        for i, (short, _) in enumerate(cnt_l):
            lg_out[short] = round(lg["cnt"][i] * 36.0 / lg["min"], 2) if lg["min"] else None
        for k in ADV_DERIVED:
            num, den = lg["der"][k]
            lg_out[k] = round(num / den, 3) if den else None
        for short, vals in dist.items():
            vals.sort()
            n = len(vals)
            ps = (0.10, 0.25, 0.50, 0.75, 0.90)
            lg_out[f"{short}|dist"] = {f"p{int(p * 100)}": vals[min(int(p * n), n - 1)] for p in ps}
        seasons_out[int(season)] = {"players": players_out}
        league_out[int(season)] = lg_out
    jwrite_gz(out / "advagg.json.gz", {
        "seasons": seasons_out, "league": league_out, "lower_better": list(ADV_LOWER_BETTER),
        "coverage": coverage, "note": ADV_NOTES})


def careers_phase(out, counts) -> None:
    """careers.json.gz — per-season per-game lines 2005-2025 from the seasavgs
    history pull (general base + advanced categories), keyed by ESPN id. The
    register bridge is the active-player register, so arcs cover players with
    an ESPN page; retired stars have no site page to hang one on."""
    players: dict[str, list] = {}
    for f in sorted(BDL.glob("seasavgs_*_general_base.parquet")):
        yr = int(f.stem.split("_")[1])
        b = pd.read_parquet(f)
        adv_f = BDL / f"seasavgs_{yr}_general_advanced.parquet"
        adv_ix = {}
        if adv_f.exists():
            a = pd.read_parquet(adv_f)
            for _, r in a.iterrows():
                adv_ix[int(r["player.id"])] = (r.get("stats.ts_pct"), r.get("stats.usg_pct"))
        for _, r in b.iterrows():
            eid = bdl2espn_of.get(int(r["player.id"]))
            if not eid:
                continue
            ts, usg = adv_ix.get(int(r["player.id"]), (None, None))
            r3 = lambda v: round(float(v), 3) if pd.notna(v) else None
            players.setdefault(str(eid), []).append([
                site_season(yr), iv(r.get("stats.age")), iv(r.get("stats.gp")), fv(r.get("stats.min")),
                fv(r.get("stats.pts")), fv(r.get("stats.reb")), fv(r.get("stats.ast")),
                r3(ts), r3(usg)])
    for rows in players.values():
        rows.sort(key=lambda r: r[0])
    counts["careers_players"] = len(players)
    counts["careers_rows"] = sum(len(v) for v in players.values())
    jwrite_gz(out / "careers.json.gz", {
        "players": players,
        "note": "row = [season, age, gp, mpg, ppg, rpg, apg, ts_pct, usg_pct] from the "
                "balldontlie season-averages pull (general base + advanced, regular seasons "
                "2005-06 through 2025-26, keyed by ending year); bridged to ESPN ids via the "
                "active-player register — internal research, republication needs a subscription"})


def reads_phase(out, counts) -> None:
    """reads.json.gz — the /research index, parsed from RESULTS-HOOPS.md so the
    site's read list can never drift from the recorded verdicts. Each section's
    verdict is its last explicit '**Verdict:' line (final read wins over the
    iteration logs); the campaign ladder value is parsed from that line.
    Non-campaign gates (§0b/§0c/§9) are recorded across docs, so they are
    curated here with pointers."""
    import re
    txt = (ROOT / "pipeline" / "results" / "RESULTS-HOOPS.md").read_text()
    # The campaign is CLOSED — where the log's prose resists clean parsing
    # (§2's last bold verdict carries a stability number; §7/§8 record their
    # verdicts outside the marker), these curated facts from the ledger and
    # the recorded reads override the parse:
    CURATED = {
        "1": {"benchmark": 0.464,
              "line": "FAIL — single-season raw-points RAPM peaks at 0.464 vs the 0.70 bar."},
        "2": {"verdict": "FAIL", "benchmark": 0.618,
              "line": "FAIL — multi-season RAPM peaks at 0.618; the YoY-stability gate confirms the estimator."},
        "3": {"benchmark": 0.621,
              "line": "FAIL — but the xPTS lever is confirmed: 0.621 on identical gates."},
        "7": {"verdict": "FAIL", "benchmark": None,
              "line": "FAIL — the tracking-SPM prior target loses to §5's Game Score prior."},
        "8": {"verdict": "FAIL", "benchmark": 0.658,
              "line": "FAIL — τ-grid at (τ*=2000, λ*=3000): stability 0.494 (bar 0.60), benchmark 0.658 "
                      "(bar 0.70) — the campaign closes at the response-side ceiling."},
    }
    sections = []
    for chunk in re.split(r"(?m)^## ", txt)[1:]:
        head = chunk.split("\n", 1)[0]
        m = re.match(r"§(\d+)\s+—\s+(.+?)\s+\(pre-registered\s+([0-9-]{10})", head)
        if not m:
            continue
        n, title, date = m.groups()
        # [^*] + DOTALL: the bold marker often wraps to the next line
        vlines = re.findall(r"\*\*Verdict:\s*([^*]+?)\*\*", chunk, re.S)
        vline = re.sub(r"\s+", " ", vlines[-1]).strip() if vlines else None
        verdict = None
        if vline:
            token = re.split(r"[—–-]", vline)[0].strip().upper()
            verdict = next((t for t in ("PASS", "FAIL", "TIE") if token.startswith(t[:2])), None)
        bm = re.search(r"(\d\.\d{3})", vline or "")
        if not bm:
            bm = (re.search(r"peaks at (\d\.\d{3})", chunk)
                  or re.search(r"benchmark[^\n.]{0,40}?(\d\.\d{3})", chunk))
        wm = re.search(r"\*\*Why\.\*\*\s*(.{0,240})", chunk, re.S)
        cur = CURATED.get(n, {})
        sections.append({
            "n": f"§{n}", "title": title.strip(), "date": date,
            "verdict": cur.get("verdict") or verdict,
            "line": cur.get("line") or vline,
            "benchmark": cur.get("benchmark",
                                 float(bm.group(1)) if bm else None),
            "why": re.sub(r"\s+", " ", wm.group(1)).strip()[:240] if wm else None,
        })
    ladder = [[s["n"], s["benchmark"]] for s in sections if s["benchmark"] is not None]
    gates = [
        {"n": "§0b", "title": "BDL ↔ ESPN two-source gate", "verdict": "PASS",
         "line": counts.get("bdl_check",
                            "688/688 games, 11,326 boxes pts/reb/ast 100% exact"),
         "why": "The balldontlie harvest is trusted only where it matches the ESPN spine exactly."},
        {"n": "§0c", "title": "Lineups internal-consistency gate", "verdict": "PARTIAL",
         "line": "starters coverage 0.90/0.89 — per-game starting fives, not unit minutes",
         "why": "Unit ratings need stint stitching; the lineups surface stays continuity-only."},
        {"n": "§9", "title": "Zone shot-making gate + read", "verdict": "PASS",
         "line": "gate caught a per-game-units bug before the read; league rates rebuilt "
                 "gp-weighted; RA .673 > paint .448",
         "why": "Durant +10.2 on 1,365 FGA anchors the read; corners > above-break confirms geometry."},
    ]
    jwrite_gz(out / "reads.json.gz", {
        "sections": sections, "gates": gates, "ladder": ladder,
        "note": "parsed from pipeline/results/RESULTS-HOOPS.md at bake — the internal "
                "research log, verdicts included",
    })
    counts["reads_sections"] = len(sections)


def methods_phase(out, counts) -> None:
    """methods.json.gz — docs/METRICS.md split into sections for /methods; the
    site renders this, so the canon page can never drift from the doc."""
    import re
    txt = (ROOT / "docs" / "METRICS.md").read_text()
    parts = re.split(r"(?m)^## ", txt)
    sections = []
    for chunk in parts[1:]:
        head, _, body = chunk.partition("\n")
        sections.append({"title": head.strip(), "body": body.strip()})
    jwrite_gz(out / "methods.json.gz", {
        "intro": parts[0].strip(), "sections": sections,
        "note": "rendered from docs/METRICS.md at bake — the metrics canon",
    })
    counts["methods_sections"] = len(sections)


def standings_phase(out, counts) -> None:
    seasons = {}
    for f in sorted(BDL.glob("standings_*.json")):
        yr = f.stem.split("_")[1]
        try:
            data = json.loads(f.read_text()).get("data", [])
        except json.JSONDecodeError:
            continue
        rows = []
        for r in data:
            abbr = BDL_ABBR2ESPN.get(r["team"]["abbreviation"], r["team"]["abbreviation"])
            if abbr not in NBA_TEAMS:
                continue
            def rec(s):
                try:
                    a, b = str(s).split("-")
                    return int(a), int(b)
                except ValueError:
                    return None, None
            hw, hl = rec(r.get("home_record"))
            rw, rl = rec(r.get("road_record"))
            w, l = int(r.get("wins", 0)), int(r.get("losses", 0))
            rows.append({"abbr": abbr, "conference": r["team"].get("conference"),
                         "w": w, "l": l, "pct": round(w / (w + l), 3) if w + l else None,
                         "conf_rank": r.get("conference_rank"), "home": [hw, hl] if hw is not None else None,
                         "road": [rw, rl] if rw is not None else None})
        rows.sort(key=lambda r: -(r["pct"] or 0))
        seasons[site_season(yr)] = rows
    counts["standings_seasons"] = len(seasons)
    jwrite(out / "standings.json", {
        "seasons": seasons,
        "note": "balldontlie standings snapshot 2026-11 — internal research"})


def per36(total, minutes) -> float | None:
    return round(36.0 * total / minutes, 1) if minutes and minutes > 0 else None


def sv(x):
    """NaN-safe str for labels like abbreviations (some preseason foes lack one)."""
    try:
        if x is None or pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return str(x)


def game_row(r, gid=None) -> dict:
    n_per = iv(r.n_periods)
    return {"id": str(gid if gid is not None else r.game_id), "date": r.date_et, "season": int(r.season_year),
            "type": TYPE_LABEL.get(int(r.season_type), str(r.season_type)),
            "away": sv(r.away_abbr), "home": sv(r.home_abbr),
            "away_score": iv(r.away_score), "home_score": iv(r.home_score),
            "ot": (n_per - 4) if n_per and n_per > 4 else None}


def load():
    g = pd.read_parquet(MART / "games.parquet")
    tg = pd.read_parquet(MART / "team_game.parquet")
    pg = pd.read_parquet(MART / "player_game.parquet")
    pb = pd.read_parquet(MART / "pbp.parquet")
    sh = pd.read_parquet(MART / "shots.parquet")
    g = g[g.completed].copy()
    id2abbr = {}
    for c_id, c_ab in (("home_team_id", "home_abbr"), ("away_team_id", "away_abbr")):
        for a, b in zip(g[c_id], g[c_ab]):
            if pd.notna(a) and pd.notna(b):
                id2abbr[str(int(a))] = b
    gg = g.set_index("game_id")
    tgx = tg.join(gg[["season_year"]], on="game_id")
    pgx = pg.join(gg[["season_year"]], on="game_id")
    return g, gg, tg, tgx, pg, pgx, pb, sh, id2abbr


def bake(out_dir: Path | None = None) -> dict:
    out = out_dir or OUT
    g, gg, tg, tgx, pg, pgx, pb, sh, id2abbr = load()
    counts = {}

    # meta --------------------------------------------------------------------
    luma = {}
    luma_f = MART.parent / "luma_check.json"
    if luma_f.exists():
        lc = json.loads(luma_f.read_text())
        a, b, c = lc.get("A_backfill_2024_25", {}), lc.get("B_current_2026_27", {}), lc.get("C_stat_agreement", {})
        luma = {"gate": "passed 2026-10-29",
                "games_2024_25": f"{a.get('score_exact')}/{a.get('scored_both')} exact",
                "games_2026_27": f"{b.get('score_exact')}/{b.get('scored_both')} exact",
                "boxes": lc.get("C_boxes_compared"),
                "credit": "LUMA Basketball Research (ARC v3.1, LOKI v3.3)"}
        ast = c.get("ast", {})
        luma["boxes_ast_note"] = f"assists exact_rate {ast.get('exact_rate')} (scorer judgment)"
    seasons_meta = {int(s): {"games": int(len(ss)), "first": str(ss.date_et.min()),
                             "last": str(ss.date_et.max()), "source": "espn"}
                    for s, ss in g.groupby("season_year")}

    # games_{season}.json -------------------------------------------------------
    for season, ss in g.groupby("season_year"):
        rows = [game_row(r) for r in ss.sort_values("date_et", ascending=False).itertuples()]
        jwrite(out / f"games_{season}.json", {"season": int(season),
                                                        "label": season_label(int(season)),
                                                        "games": rows})
        counts[f"games_{season}"] = len(rows)

    # teams.json + team/{abbr}.json.gz ------------------------------------------
    season_rows = {}
    team_seasons = {}
    for (season, team_id), rows in tgx.groupby(["season_year", "team_id"]):
        abbr = id2abbr.get(str(int(team_id)))
        if not abbr or abbr not in NBA_TEAMS:  # 30 franchises only (exhibitions out)
            continue
        tid = str(int(team_id))
        reg_gids = [gid for gid in rows.game_id if gg.loc[gid].season_type == 2]
        w = l = 0
        pts_all, opp_all = [], []
        games_list = []
        for gid in sorted(reg_gids, key=lambda k: gg.loc[k].date_et, reverse=True):
            gr = gg.loc[gid]
            home = str(int(gr.home_team_id)) == tid
            pts = int(gr.home_score) if home else int(gr.away_score)
            ops = int(gr.away_score) if home else int(gr.home_score)
            w += pts > ops
            l += pts < ops
            pts_all.append(pts)
            opp_all.append(ops)
            games_list.append({"id": str(gid), "date": gr.date_et, "type": "regular",
                               "opp": sv(gr.away_abbr if home else gr.home_abbr), "home": home,
                               "pts": pts, "opp_pts": ops,
                               "res": "W" if pts > ops else ("L" if pts < ops else "T")})
        reg = rows[rows.game_id.isin(reg_gids)]
        agg = {"abbr": abbr, "name": NBA_TEAMS.get(abbr, abbr), "g": len(reg_gids), "w": w, "l": l,
               "pts": round(sum(pts_all) / max(len(pts_all), 1), 1),
               "opp_pts": round(sum(opp_all) / max(len(opp_all), 1), 1),
               "fgm": fv(reg["fieldGoalsMade-fieldGoalsAttempted_made"].mean()),
               "fga": fv(reg["fieldGoalsMade-fieldGoalsAttempted_att"].mean()),
               "tpm": fv(reg["threePointFieldGoalsMade-threePointFieldGoalsAttempted_made"].mean()),
               "tpa": fv(reg["threePointFieldGoalsMade-threePointFieldGoalsAttempted_att"].mean()),
               "ftm": fv(reg["freeThrowsMade-freeThrowsAttempted_made"].mean()),
               "fta": fv(reg["freeThrowsMade-freeThrowsAttempted_att"].mean()),
               "reb": fv(reg["totalRebounds"].mean()), "ast": fv(reg["assists"].mean()),
               "tov": fv(reg["totalTurnovers"].mean()), "stl": fv(reg["steals"].mean()),
               "blk": fv(reg["blocks"].mean()),
               "paint": fv(reg["pointsInPaint"].mean()) if "pointsInPaint" in reg else None,
               "fastbreak": fv(reg["fastBreakPoints"].mean()) if "fastBreakPoints" in reg else None}
        season_rows.setdefault(int(season), []).append(agg)
        team_seasons.setdefault(abbr, {})[int(season)] = {**agg, "games": games_list}
    for s in season_rows:
        season_rows[s].sort(key=lambda r: -(r["w"] + r["l"]))
    # teams.json / team files are written at the end, after the BDL seasons merge

    # players.json board ----------------------------------------------------------
    board = {}
    pgx_played = pgx[pgx.pts.notna()]
    for (season, ath), rows in pgx_played.groupby(["season_year", "athlete_id"]):
        team = rows.team_id.mode()
        abbr = id2abbr.get(str(int(team.iloc[0]))) if len(team) else None
        gp = len(rows)
        mins = float(rows["min"].sum())
        pos = rows.position.mode()
        row = {"id": str(ath), "name": rows.name.iloc[0],
               "pos": pos.iloc[0] if len(pos) else None,
               "team": abbr, "gp": gp, "gs": int(rows.starter.sum()), "min": fv(mins / gp),
               "pts": fv(rows.pts.mean()), "reb": fv(rows.reb.mean()), "ast": fv(rows.ast.mean()),
               "stl": fv(rows.stl.mean()), "blk": fv(rows.blk.mean()), "tov": fv(rows["to"].mean()),
               "oreb": fv(rows.oreb.mean()), "dreb": fv(rows.dreb.mean()),
               "pts36": per36(rows.pts.sum(), mins), "reb36": per36(rows.reb.sum(), mins),
               "ast36": per36(rows.ast.sum(), mins),
               "fgp": sv_ratio(rows.fgm.sum(), rows.fga.sum()),
               "tpp": sv_ratio(rows.tpm.sum(), rows.tpa.sum()),
               "ftp": sv_ratio(rows.ftm.sum(), rows.fta.sum()), "src": "espn"}
        board.setdefault(int(season), []).append(row)
    for s in board:
        board[s].sort(key=lambda r: -r["pts"])
    # players.json is written at the end, after the BDL seasons merge

    # player/{id}.json.gz — built into pdocs; written at the end after the BDL merge
    pdocs: dict[str, dict] = {}
    for ath, rows in pgx_played.groupby("athlete_id"):
        seasons = {}
        for season, srows in rows.groupby("season_year"):
            games = []
            for r in srows.itertuples():
                gr = gg.loc[r.game_id]
                home = str(int(gr.home_team_id)) == str(int(r.team_id))
                pts = int(gr.home_score) if home else int(gr.away_score)
                ops = int(gr.away_score) if home else int(gr.home_score)
                games.append({"id": str(r.game_id), "date": gr.date_et,
                              "opp": sv(gr.away_abbr if home else gr.home_abbr), "home": home,
                              "res": "W" if pts > ops else "L", "min": fv(r.min), "pts": iv(r.pts),
                              "reb": iv(r.reb), "ast": iv(r.ast), "stl": iv(r.stl), "blk": iv(r.blk),
                              "tov": iv(r.to), "pf": iv(r.pf), "pm": iv(r.plus_minus),
                              "fg": f"{iv(r.fgm)}-{iv(r.fga)}", "tp": f"{iv(r.tpm)}-{iv(r.tpa)}",
                              "ft": f"{iv(r.ftm)}-{iv(r.fta)}"})
            mins = float(srows["min"].sum())
            team = srows.team_id.mode()
            seasons[int(season)] = {
                "team": id2abbr.get(str(int(team.iloc[0]))) if len(team) else None,
                "gp": len(srows), "gs": int(srows.starter.sum()),
                "totals": {"min": round(mins, 1), "pts": int(srows.pts.sum()),
                           "reb": int(srows.reb.sum()), "ast": int(srows.ast.sum()),
                           "stl": int(srows.stl.sum()), "blk": int(srows.blk.sum()),
                           "tov": int(srows["to"].sum())},
                "per_game": {"min": fv(mins / len(srows)), "pts": fv(srows.pts.mean()),
                             "reb": fv(srows.reb.mean()), "ast": fv(srows.ast.mean()),
                             "stl": fv(srows.stl.mean()), "blk": fv(srows.blk.mean()),
                             "tov": fv(srows["to"].mean())},
                "per36": {"pts": per36(srows.pts.sum(), mins), "reb": per36(srows.reb.sum(), mins),
                          "ast": per36(srows.ast.sum(), mins)},
                "shoot": {"fg": [int(srows.fgm.sum()), int(srows.fga.sum())],
                          "tp": [int(srows.tpm.sum()), int(srows.tpa.sum())],
                          "ft": [int(srows.ftm.sum()), int(srows.fta.sum())],
                          "oreb": fv(srows.oreb.mean()), "dreb": fv(srows.dreb.mean())},
                "games": games}
        name = rows.name.dropna().iloc[-1]
        pdocs[str(ath)] = {"id": str(ath), "name": name, "seasons": seasons}

    # bridge: norm-name -> ESPN id, and BDL player_id -> ESPN id (shared by
    # the contracts + season-average-category docs below). Ambiguous norms
    # (two ESPN ids share a name) are dropped, not guessed.
    espn_of: dict[str, set] = {}
    for ath, nm in pg[["athlete_id", "name"]].dropna().drop_duplicates().itertuples(index=False):
        n = norm_name(nm)
        if n:
            espn_of.setdefault(n, set()).add(int(ath))
    espn_of = {n: next(iter(ids)) for n, ids in espn_of.items() if len(ids) == 1}
    bdl_team = {}
    nt_f = BDL / "nba_teams.parquet"
    if nt_f.exists():
        ntd = pd.read_parquet(nt_f)
        for _, r in ntd.iterrows():
            bdl_team[int(r["id"])] = BDL_ABBR2ESPN.get(r["abbreviation"], r["abbreviation"])
    if (BDL / "contracts_teams_2026.parquet").exists():
        tdf = pd.read_parquet(BDL / "contracts_teams_2026.parquet")
        bdl_team = {int(r["team.id"]): BDL_ABBR2ESPN.get(r["team.abbreviation"], r["team.abbreviation"])
                    for _, r in tdf.drop_duplicates("team.id").iterrows()}
    bdl2espn: dict[int, int] = {}
    reg_f = BDL / "nba_players_active.parquet"
    if reg_f.exists():
        rdf = pd.read_parquet(reg_f)
        for _, r in rdf.iterrows():
            e = espn_of.get(norm_name(f"{r['first_name']} {r['last_name']}"))
            if e:
                bdl2espn[int(r["id"])] = e

    # contracts.json — balldontlie snapshot, name-bridged to ESPN ids -----------
    teams_f = BDL / "contracts_teams_2026.parquet"
    agg_f = BDL / "contracts_agg_current.batches.jsonl"   # in-flight source
    agg_parquet = BDL / "contracts_agg_current.parquet"   # completed source
    if teams_f.exists() and (agg_f.exists() or agg_parquet.exists()):
        # identity by BDL player_id (register names above); embedded names in
        # the contracts feeds have been observed to drift (Grant/MEM row)
        deals: dict[str, list] = {}
        unmapped = 0
        if agg_f.exists():
            # the jsonl holds batch lines {key, rows:[deal, ...]} — flatten
            agg_rows = [r for l in agg_f.read_text().splitlines() if l.strip()
                        for r in json.loads(l).get("rows", [])]
        else:
            # the completed pull deletes its jsonl; the parquet is flat —
            # rebuild just the fields the deal builder reads (numpy-safe)
            pdf = pd.read_parquet(agg_parquet)
            need = ("player_id", "start_year", "end_year", "contract_type", "contract_status",
                    "contract_years", "total_value", "average_salary", "total_guaranteed",
                    "guaranteed_at_signing", "signed_using", "free_agent_year",
                    "free_agent_status", "contract_notes", "team_id")
            agg_rows = []
            for _, r in pdf.iterrows():
                d: dict = {}
                for k in need:
                    v = r.get(k)
                    if hasattr(v, "__len__") and not isinstance(v, str):
                        d[k] = None  # degenerate array cell — builder needs none of it
                    elif pd.isna(v):
                        d[k] = None
                    else:
                        try:
                            d[k] = round(float(v), 3)
                        except (TypeError, ValueError):
                            d[k] = str(v)
                agg_rows.append(d)
        for d in agg_rows:
            eid = bdl2espn.get(int(d.get("player_id") or (d.get("player") or {}).get("id") or -1))
            if not eid:
                p = d.get("player") or {}
                eid = espn_of.get(norm_name(f"{p.get('first_name', '')} {p.get('last_name', '')}"))
            if not eid:
                unmapped += 1
                continue
            deals.setdefault(str(eid), []).append({
                "type": d.get("contract_type"), "status": d.get("contract_status"),
                "start": d.get("start_year"), "end": d.get("end_year"),
                "years": d.get("contract_years"), "total_value": d.get("total_value"),
                "avg_salary": d.get("average_salary"),
                "guaranteed": d.get("total_guaranteed"),
                "guaranteed_signing": d.get("guaranteed_at_signing"),
                "signed_using": d.get("signed_using"), "fa_year": d.get("free_agent_year"),
                "fa_status": d.get("free_agent_status"), "notes": d.get("contract_notes"),
                "team": bdl_team.get(d.get("team_id"))})
        for v in deals.values():
            v.sort(key=lambda d: -(d["start"] or 0))
        salaries = {}
        salary_team_mismatch = 0
        for _, r in tdf.iterrows():
            eid = bdl2espn.get(int(r["player_id"]))
            if eid:
                team = bdl_team.get(int(r["team.id"]))
                cur = deals.get(str(eid), [])
                cur_team = next((d["team"] for d in cur if d["status"] == "CURRENT"), None)
                if cur_team and team and cur_team != team:
                    salary_team_mismatch += 1  # feeds disagree — keep the row, count it
                salaries[str(eid)] = {"season": site_season(iv(r["season"])),
                                      "cap_hit": iv(r["cap_hit"]),
                                      "base_salary": iv(r["base_salary"]),
                                      "team": team}
        jwrite(out / "contracts.json", {
            "deals": deals, "salaries": salaries, "unmapped": unmapped,
            "salary_team_mismatch": salary_team_mismatch,
            "note": "balldontlie GOAT-trial snapshot 2026-11-02; internal research — "
                    "public surfaces carry these numbers only while a subscription is active"})
        counts["contracts_deals"] = sum(len(v) for v in deals.values())
        counts["contracts_salaries"] = len(salaries)
        counts["contracts_salary_team_mismatch"] = salary_team_mismatch
    else:
        print("contracts: BDL snapshot files missing — contracts.json skipped")

    # seasavgs_{season}.json.gz — curated category season averages -----------
    # docs/bdl-profile-schemas.md; docs keyed by ESPN id, one entry per player
    def ss_pick(row, keys, prefix="stats."):
        out = {}
        for k in keys:
            col = f"{prefix}{k}"
            if col not in row.index:
                continue
            v = row[col]
            if hasattr(v, "__len__") and not isinstance(v, str):
                continue  # degenerate array cell — nothing to show
            if pd.isna(v):
                continue
            try:
                out[k] = round(float(v), 3)
            except (TypeError, ValueError):
                out[k] = str(v)
        return out

    PT_KEYS = ("play_type", "gp", "poss", "ppp", "pts", "fga", "fg_pct", "efg_pct",
               "poss_pct", "percentile", "tov_poss_pct", "ft_poss_pct")
    ZONES = ("restricted_area", "in_the_paint_(non-ra)", "mid-range",
             "left_corner_3", "right_corner_3", "above_the_break_3", "backcourt")
    BANDS = ("less_than_5_ft", "5-9_ft", "10-14_ft", "15-19_ft", "20-24_ft",
             "25-29_ft", "30-34_ft", "35-39_ft", "40+_ft")
    for bdl_yr in ("2025", "2024", "2023"):
        site_yr = site_season(bdl_yr)
        ss_files = sorted(BDL.glob(f"seasavgs_{bdl_yr}_*.parquet"))
        if len(ss_files) < 40:
            continue
        players: dict[str, dict] = {}
        zone_lg: dict[str, list] = {}   # per §9: league zone fga/fgm sums
        for f in ss_files:
            tag = f.stem.replace(f"seasavgs_{bdl_yr}_", "")
            df = pd.read_parquet(f)
            if tag.startswith("playtype_"):
                for _, r in df.iterrows():
                    eid = bdl2espn.get(int(r["player.id"]))
                    if not eid:
                        continue
                    players.setdefault(str(eid), {}).setdefault(
                        "playtype", []).append(ss_pick(r, PT_KEYS))
            elif tag.startswith("tracking_") or tag in ("hustle", "defense_overall",
                                                        "clutch_advanced", "general_advanced"):
                key = {"tracking_speeddistance": "speed", "tracking_drives": "drives",
                       "tracking_passing": "passing", "tracking_painttouch": "paint",
                       "tracking_catchshoot": "catch_shoot", "tracking_pullupshot": "pullup",
                       "tracking_posttouch": "post", "tracking_elbowtouch": "elbow",
                       "tracking_rebounding": "reb_tracking", "tracking_efficiency": "eff",
                       "tracking_possessions": "poss_t", "tracking_defense": "def_t",
                       "hustle": "hustle", "defense_overall": "defense",
                       "clutch_advanced": "clutch", "general_advanced": "adv"}.get(tag, tag)
                for _, r in df.iterrows():
                    eid = bdl2espn.get(int(r["player.id"]))
                    if not eid:
                        continue
                    players.setdefault(str(eid), {})[key] = ss_pick(r, tuple(
                        c.replace("stats.", "") for c in df.columns if c.startswith("stats.")))
                    pp = r.get("player.position")
                    if pd.notna(pp):
                        players[str(eid)]["pos"] = str(pp)[:1]
            elif tag == "shooting_by_zone":
                for _, r in df.iterrows():
                    eid = bdl2espn.get(int(r["player.id"]))
                    if not eid:
                        continue
                    players.setdefault(str(eid), {})["zones"] = {
                        z: ss_pick(r, ("fga", "fgm", "fg_pct"), prefix=f"stats.{z}_") for z in ZONES}
                    # §9 league sums: the category rows are PER-GAME averages, so
                    # season totals need the gp from general_advanced (runs
                    # earlier in this same loop) — league rates are gp-weighted
                    gp = (players[str(eid)].get("adv") or {}).get("gp")
                    gp = float(gp) if isinstance(gp, (int, float)) and gp else 0.0
                    if gp <= 0:
                        continue
                    for z in ZONES:
                        fa = r.get(f"stats.{z}_fga")
                        fm = r.get(f"stats.{z}_fgm")
                        if pd.notna(fa) and pd.notna(fm):
                            acc = zone_lg.setdefault(z, [0.0, 0.0])
                            acc[0] += float(fa) * gp
                            acc[1] += float(fm) * gp
            elif tag == "shooting_5ft_range":
                for _, r in df.iterrows():
                    eid = bdl2espn.get(int(r["player.id"]))
                    if not eid:
                        continue
                    players.setdefault(str(eid), {})["bands"] = {
                        b: ss_pick(r, ("fga", "fgm", "fg_pct"), prefix=f"stats.{b}._") for b in BANDS}
        for v in players.values():
            if "playtype" in v:
                v["playtype"].sort(key=lambda d: -(d.get("poss") or 0))
        # §9 zone shot-making benchmark — league zones + per-player xefg.
        # Preregistered in RESULTS-HOOPS §9 before this code ran; amended there
        # for units (category rows are per-game averages; league rates are
        # gp-weighted season rates; floors restated in season attempts 25/100).
        # Descriptive vs the same-season pool; eFG valued (3s ×1.5).
        lgz = {}
        for z, (fa, fm) in zone_lg.items():
            if fa >= 20:
                fgp = fm / fa
                lgz[z] = {"fga": int(round(fa)), "fgp": round(fgp, 3),
                          "efgp": round(fgp * 1.5, 3) if "3" in z else round(fgp, 3)}
        gate = None
        need = {"restricted_area", "in_the_paint_(non-ra)", "above_the_break_3"}
        if need <= set(lgz):
            g = lgz
            corners = [g[z]["fgp"] for z in ("left_corner_3", "right_corner_3") if z in g]
            gate = (g["restricted_area"]["fgp"] > g["in_the_paint_(non-ra)"]["fgp"]
                    and (not corners or max(corners) > g["above_the_break_3"]["fgp"]))
        if gate:
            for eid, cats in players.items():
                zones = cats.get("zones") or {}
                gp = (cats.get("adv") or {}).get("gp")
                gp = float(gp) if isinstance(gp, (int, float)) and gp else 0.0
                if gp <= 0:
                    continue
                num = den = 0.0
                for z, zz in zones.items():
                    fa, lz = zz.get("fga"), lgz.get(z)
                    fa_s = fa * gp if isinstance(fa, (int, float)) else 0
                    if lz and fa_s >= 25:   # 25+ season attempts enter the diet
                        num += fa_s * lz["efgp"]
                        den += fa_s
                efg = (cats.get("adv") or {}).get("efg_pct")
                if den >= 100 and isinstance(efg, (int, float)):
                    cats["shootmk"] = {"xefg": round(num / den, 3),
                                       "efg": round(float(efg), 3),
                                       "diff": round(float(efg) - num / den, 3),
                                       "n_fga": int(den)}
        else:
            print(f"seasavgs {site_yr}: §9 geometry gate failed — leagueZones/shootmk withheld")
        # league percentile ranks (0 lowest .. 1 highest) for the chip panel
        RANK_METRICS = ("adv.ts_pct", "adv.usg_pct", "adv.net_rating", "adv.pie",
                        "drives.drive_pts", "drives.drive_fg_pct",
                        "passing.ast_points_created", "paint.paint_touch_pts",
                        "catch_shoot.catch_shoot_fg_pct", "pullup.pull_up_efg_pct",
                        "speed.dist_miles", "hustle.deflections", "defense.d_fg_pct")
        for path in RANK_METRICS:
            sec, k = path.split(".")
            vals = []
            for eid, cats in players.items():
                v = (cats.get(sec) or {}).get(k)
                if isinstance(v, (int, float)):
                    vals.append((eid, v))
            if len(vals) < 30:
                continue
            vals.sort(key=lambda t: t[1])
            for i, (eid, _) in enumerate(vals):
                players[eid].setdefault("pct_ranks", {})[path] = round(i / (len(vals) - 1), 3)
        # position-pool ranks (METRICS.md advantage framework): G/F/C pools, floor 40
        pools: dict[str, list] = {}
        for eid, cats in players.items():
            p = cats.get("pos")
            if isinstance(p, str):
                pools.setdefault(p, []).append(eid)
        for p, eids in pools.items():
            if len(eids) < 40:
                continue
            for path in RANK_METRICS:
                sec, k = path.split(".")
                vals = []
                for eid in eids:
                    v = (players[eid].get(sec) or {}).get(k)
                    if isinstance(v, (int, float)):
                        vals.append((eid, v))
                if len(vals) < 30:
                    continue
                vals.sort(key=lambda t: t[1])
                for i, (eid, _) in enumerate(vals):
                    players[eid].setdefault("pct_ranks_pos", {})[path] = round(i / (len(vals) - 1), 3)
        counts[f"seasavgs_{site_yr}_pospools"] = {p: len(e) for p, e in pools.items()}
        jwrite_gz(out / f"seasavgs_{site_yr}.json.gz",
                  {"season": site_yr, "players": players,
                   "leagueZones": lgz if gate else None})
        counts[f"seasavgs_{site_yr}"] = len(players)

    # balldontlie layers — box merge, v2-advanced roll-ups, career arcs,
    # standings, and the cross-source agreement check that gates the box merge
    bdl2espn_of.update(bdl2espn)
    bdl_team_abbr.update(bdl_team)
    bdl_check_info = bdl_espn_check(gg, pgx, id2abbr)
    print("bdl vs espn (2025):", json.dumps(bdl_check_info))
    try:
        g, b = bdl_check_info["games"], bdl_check_info["boxes"]
        counts["bdl_check"] = (f"{g['matched']} games, {g['score_exact']} score-exact; "
                               f"{b['matched']:,} boxes, pts/reb/ast "
                               f"{b['pts_exact']:.0%}/{b['reb_exact']:.0%}/{b['ast_exact']:.0%} exact")
    except (KeyError, TypeError):
        pass  # stub result on empty harvest — reads.json keeps the static line
    seasons_meta.update(merge_bdl_box(board, pdocs, team_seasons, season_rows, out, counts))
    starters_info = merge_bdl_starters(board, pdocs, team_seasons, counts)
    team_pkg = merge_bdl_team_analytics(team_seasons, season_rows, counts, tgx, gg, id2abbr)
    advagg_phase(out, counts)
    careers_phase(out, counts)
    standings_phase(out, counts)
    reads_phase(out, counts)
    methods_phase(out, counts)

    # playershots_{season}.json.gz — half-court heat grids from ESPN x/y ------
    # coordinates are feet on the attacking half (x 0-50, y 0 baseline -> 47);
    # sentinels and wild values are dropped at the court boundary
    sh_ok = sh[(sh.x >= -5) & (sh.x <= 55) & (sh.y >= -5) & (sh.y <= 50)].copy()
    sh_ok["season_year"] = sh_ok.game_id.map(gg["season_year"])
    for hs in (2027, 2025):
        hg = sh_ok[sh_ok.season_year == hs]
        if len(hg) < 1000:
            continue
        grid_players: dict[str, dict] = {}
        for ath, rows in hg.groupby("shooter_id"):
            xs = (rows.x // 2.5).astype(int)
            ys = (rows.y // 2.5).astype(int)
            cells = []
            for (ix, iy), cr in rows.groupby([xs, ys]):
                cells.append([int(ix), int(iy), int(len(cr)), int(cr.made.sum())])
            grid_players[str(int(ath))] = {"n": int(len(rows)), "fgm": int(rows.made.sum()),
                                           "cells": sorted(cells)}
        jwrite_gz(out / f"playershots_{hs}.json.gz",
                  {"season": int(hs), "binsize": 2.5, "players": grid_players})
        counts[f"playershots_{hs}"] = len(grid_players)

    # game/{gid}.json.gz -----------------------------------------------------------------
    pg_by = {k: v for k, v in pgx.groupby("game_id")}
    sh_by = {k: v for k, v in sh.groupby("game_id")}
    tg_by = {k: v for k, v in tg.groupby("game_id")}
    n_games = 0
    for gid, gss in pb.groupby("game_id"):
        gr = gg.loc[gid]
        boxes = {}
        for team_id, prow in pg_by.get(gid, pd.DataFrame()).groupby("team_id"):
            abbr = id2abbr.get(str(int(team_id))) or f"t{int(team_id)}"
            rows = []
            for r in prow.sort_values(["starter", "pts"], ascending=[False, False],
                                      na_position="last").itertuples():
                rows.append({"name": r.name, "pos": sv(r.position), "starter": bool(r.starter),
                             "dnp": bool(r.did_not_play), "min": fv(r.min), "pts": iv(r.pts),
                             "reb": iv(r.reb), "ast": iv(r.ast), "stl": iv(r.stl), "blk": iv(r.blk),
                             "tov": iv(r.to), "pf": iv(r.pf), "pm": iv(r.plus_minus),
                             "fg": None if iv(r.fga) is None else f"{iv(r.fgm)}-{iv(r.fga)}",
                             "tp": None if iv(r.tpa) is None else f"{iv(r.tpm)}-{iv(r.tpa)}",
                             "ft": None if iv(r.fta) is None else f"{iv(r.ftm)}-{iv(r.fta)}"})
            boxes[abbr] = rows
        shooter = {str(r.athlete_id): r.name
                   for r in pg_by.get(gid, pd.DataFrame()).itertuples() if pd.notna(r.name)}
        shots = [{"p": iv(r.period), "t": fv(r.period_elapsed), "x": fv(r.x), "y": fv(r.y),
                  "m": bool(r.made), "v": iv(r.points_made) or 0, "pa": iv(r.points_attempted),
                  "a": id2abbr.get(str(int(r.team_id))) if pd.notna(r.team_id) else None,
                  "s": shooter.get(str(r.shooter_id)),
                  "ty": r.shot_type}
                 for r in sh_by.get(gid, pd.DataFrame()).itertuples()]
        plays = [{"p": iv(r.period), "t": fv(r.period_elapsed), "ty": r.type_text, "tx": r.text,
                  "a": id2abbr.get(str(int(r.team_id))) if pd.notna(r.team_id) else None,
                  "hs": iv(r.home_score), "as": iv(r.away_score)}
                 for r in gss.sort_values("seq").itertuples()]
        teams_out = []
        for r in tg_by.get(gid, pd.DataFrame()).itertuples():
            teams_out.append({"abbr": id2abbr.get(str(int(r.team_id))), "side": r.home_away,
                              "points": iv(r.points),
                              "paint": iv(getattr(r, "pointsInPaint", None)),
                              "fastbreak": iv(getattr(r, "fastBreakPoints", None)),
                              "reb": iv(getattr(r, "totalRebounds", None)),
                              "ast": iv(getattr(r, "assists", None)),
                              "tov": iv(getattr(r, "totalTurnovers", None))})
        jwrite_gz(out / "game" / f"{gid}.json.gz", {
            "game": game_row(gr, gid), "teams": teams_out, "boxes": boxes,
            "shots": shots, "plays": plays})
        n_games += 1
    counts["game_files"] = n_games

    # deferred writes: teams, players, player docs, meta -----------------------
    for s in season_rows:
        season_rows[s].sort(key=lambda r: -(r["w"] + r["l"]))
    jwrite(out / "teams.json", {"seasons": season_rows,
                                "league": team_pkg.get("league", {})})
    for abbr, seasons in team_seasons.items():
        jwrite_gz(out / "team" / f"{abbr.lower()}.json.gz", {"seasons": seasons})
    counts["teams"] = len(team_seasons)
    jwrite(out / "players.json", {"seasons": board})
    counts["players"] = sum(len(v) for v in board.values())
    opp_records = {s: {t["abbr"]: (t["w"], t["l"]) for t in rows}
                   for s, rows in season_rows.items()}
    for doc in pdocs.values():
        schedule_splits(doc, opp_records)
    for ath, doc in pdocs.items():
        jwrite_gz(out / "player" / f"{ath}.json.gz", doc)
    counts["player_files"] = len(pdocs)
    validation = dict(luma)
    if bdl_check_info:
        validation["bdl"] = bdl_check_info
    if team_pkg.get("gate"):
        validation["team_gate_0d"] = team_pkg["gate"]
    jwrite(out / "meta.json", {
        "seasons": seasons_meta, "validation": validation, "starters": starters_info,
        "note": "descriptive Phase 1: raw box values, averages and per-36 only; "
                "2022-23/2023-24 seasons and the advanced/tracking roll-ups come from "
                "balldontlie (GOAT-trial snapshot 2026-11) — internal research, public "
                "surfaces carry them only while a subscription is active"})
    return counts


# exploration-lane outputs (pipeline/explore.py) live beside the bake but are
# not rebuilt by it — excluded from the no-op drift gate
EXPLORE_KEYS = {"similar.json.gz", "surplus.json.gz", "clutch.json.gz",
                "rebound.json.gz", "aging.json.gz"}


def check() -> int:
    """Rebuild every payload in a temp dir; report keys whose bytes would change."""
    before = {}
    if OUT.exists():
        for p in OUT.rglob("*"):
            if p.is_file() and str(p.relative_to(OUT)) not in EXPLORE_KEYS:
                before[str(p.relative_to(OUT))] = p.read_bytes()
    with tempfile.TemporaryDirectory() as td:
        bake(Path(td))
        after = {str(p.relative_to(Path(td))): p.read_bytes()
                 for p in Path(td).rglob("*") if p.is_file()}
    drift = sorted(k for k in set(before) | set(after)
                   if k not in EXPLORE_KEYS and before.get(k) != after.get(k))
    print(f"hoops bake check: {len(after)} files, {len(drift)} would change")
    for k in drift[:20]:
        print("  ", k)
    return 1 if drift else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify a re-bake is a no-op")
    a = ap.parse_args()
    if a.check:
        sys.exit(check())
    print(bake())
