"""Source registry: for every stat on the site, the feed it is computed from, the
method, the code that computes it, the gate that cleared it and the published
reference it follows. Baked as `sources.json` (rendered on /methods#sources)
and written to `docs/SOURCES.md` so a knowledge base can cite each number back
to a feed call and a line of code.

`refs` point at the owner's knowledge base (`LLM_knowledgeBase/library/...`)
where a copy of the reference is filed, plus the public URL. Reference-only
sources (Basketball-Reference, NBA.com) are cited for definitions, never
scraped. Run `python pipeline/sources.py` to regenerate the doc from the last
bake's meta.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

FEEDS = {
    "espn_scoreboard": {
        "name": "ESPN scoreboard", "call": f"GET {ESPN}/scoreboard?dates=YYYYMMDD",
        "gives": "game ids, dates, status, final scores", "terms": "public API, no key",
        "store": "hoops_mart data/mart/games.parquet"},
    "espn_schedule": {
        "name": "ESPN team schedule", "call": f"GET {ESPN}/teams/{{team_id}}/schedule?season=YYYY",
        "gives": "the authoritative game list (the scoreboard misses some games on their date)",
        "terms": "public API, no key", "store": "hoops_mart data/mart/games.parquet"},
    "espn_box": {
        "name": "ESPN game summary: box score", "call": f"GET {ESPN}/summary?event={{game_id}}",
        "gives": "player and team box scores, starters, minutes", "terms": "public API, no key",
        "store": "hoops_mart data/mart/player_game.parquet, team_game.parquet"},
    "espn_pbp": {
        "name": "ESPN game summary: play-by-play", "call": f"GET {ESPN}/summary?event={{game_id}}",
        "gives": "every play with clock, score, type text and participants; shots carry x/y",
        "terms": "public API, no key",
        "store": "hoops_mart data/mart/pbp.parquet, shots.parquet",
        "caveat": "`seq` is not chronological (late scorer corrections get a higher seq); every reader "
                  "orders by period, game clock, then running score (creation.ordered). The mart's "
                  "clock_sec is null under one minute ('SS.T' clocks); readers refill it (creation.clock_seconds)."},
    "bdl": {
        "name": "balldontlie (BDL)", "call": "GET https://api.balldontlie.io/v1|v2/... (key: BDL_KEY)",
        "gives": "player bios, draft year and pick, advanced per-period box (NBA.com ids)",
        "terms": "terms §6 permit republication while subscribed; subscription lapsed 2026-11-09, "
                 "licensing decision pending with the owner",
        "store": "hoops_mart data/bdl, data/mart/bdl_*.parquet"},
    "luma": {
        "name": "LUMA Basketball Research (CourtShare)", "call": "luma MCP server (key: LUMA_KEY)",
        "gives": "xPTS-RAPM, Lens channels, on/off: validation reference only",
        "terms": "never republished; credited wherever its numbers touched a gate",
        "store": "data/derived/*luma* caches (local)"},
}

KB = "LLM_knowledgeBase/library/sources/basketball/"
REFS = {
    "nba_glossary": ("NBA.com stats glossary", "https://www.nba.com/stats/help/glossary", KB + "nba-com-307fac94d2.md"),
    "bref_glossary": ("Basketball-Reference glossary (Oliver/Hollinger formulas)",
                      "https://www.basketball-reference.com/about/glossary.html", KB + "basketball-reference-com-6af5e19612.md"),
    "bpm2": ("Myers, About Box Plus/Minus (BPM 2.0)", "https://www.basketball-reference.com/about/bpm2.html",
             KB + "basketball-reference-com-457a28b29d.md"),
    "taylor": ("Ben Taylor, Thinking Basketball (Offensive Load, box creation)", "https://thinkingbasketball.net/",
               KB + "thinkingbasketball-net-ca74207430.md"),
    "ssq": ("Synergy Shot Quality (per-shot expected value)",
            "https://sportradar.com/content-hub/blog/explaining-synergy-shot-quality/", KB + "sportradar-com-410bbf9ec3b9.md"),
    "stabilize": ("Basketball Index, Your impact stat isn't coming back next year (regression to the mean)",
                  "https://www.bball-index.com/projecting-impact/", KB + "bball-index-com-8fe1c7bbe5.md"),
    "rapm": ("Squared Statistics, Deep dive on RAPM I-III", "https://squared2020.com/2017/09/18/deep-dive-on-regularized-adjusted-plus-minus-i-introductory-example/",
             KB + "squared2020-com-220902e1f1.md"),
    "wowy": ("With or without you (WOWY)", "https://www.americansocceranalysis.com/home/2019/8/14/with-or-without-you-wowy-a-plus-minus-alternative-",
             KB + "americansocceranalysis-com-34fc07b4fe4b.md"),
}

# One row per stat family: keys, feeds, method, code, gate section, refs.
FAMILIES = [
    {"family": "Box score per game", "keys": ["pts", "reb", "ast", "stl", "blk"], "feeds": ["espn_box"],
     "method": "season totals / games played, regular season", "code": "pipeline/hoops_export.py",
     "gate": "box check (ESPN vs BDL player boxes, 2024-25: points, rebounds, assists 100% exact)",
     "refs": ["nba_glossary"]},
    {"family": "Milestones and Game Score", "keys": ["gmsc", "g30", "g40", "dd", "td"], "feeds": ["espn_box"],
     "method": "Hollinger Game Score: PTS + 0.4FGM - 0.7FGA - 0.4(FTA-FTM) + 0.7ORB + 0.3DRB + STL + 0.7AST "
               "+ 0.7BLK - 0.4PF - TOV; game counts", "code": "pipeline/creation.py (gmsc)", "gate": "box check (as above)",
     "refs": ["bref_glossary"]},
    {"family": "Efficiency and usage rates", "keys": ["ts_pct", "efg_pct", "ftr", "tpar", "usg_pct", "ast_pct", "ast_to",
     "to_ratio", "orb_pct", "drb_pct", "reb_pct", "stl_pct", "blk_pct"], "feeds": ["espn_box"],
     "method": "NBA.com definitions; on-court team and opponent totals estimated by minutes share",
     "code": "pipeline/rates.py", "gate": "§0h", "refs": ["nba_glossary", "bref_glossary"]},
    {"family": "Shot zones", "keys": ["rim_rate", "rim_fg", "mid_rate", "mid_fg", "c3_rate", "c3_fg", "ab3_fg"],
     "feeds": ["espn_pbp"], "method": "shot x/y binned: rim within 4 ft, mid-range long twos, corner and above-break threes",
     "code": "pipeline/creation.py", "gate": "§0i", "refs": ["nba_glossary"]},
    {"family": "Self-creation and playmaking", "keys": ["pct_unast", "unast36", "unast3_36", "pullup_rate", "pullup_efg",
     "ast_pts36", "ast3_36", "ast_rim36", "badpass36", "lostball36"], "feeds": ["espn_pbp"],
     "method": "assist attribution and ESPN shot/turnover type text, per 36 minutes",
     "code": "pipeline/creation.py", "gate": "§0i", "refs": ["nba_glossary"]},
    {"family": "Fouls drawn and putbacks", "keys": ["fdrawn36", "andones", "andone36", "putback_rate"], "feeds": ["espn_pbp"],
     "method": "free-throw trips started (and-one = make plus a 1-of-1 at the same clock); putback = own shot within 3 s "
               "of own offensive rebound", "code": "pipeline/creation.py (pbp_flags)", "gate": "§18",
     "refs": ["nba_glossary"]},
    {"family": "Shot quality", "keys": ["xefg", "smk"], "feeds": ["espn_pbp"],
     "method": "per-shot make model (distance, zone, shot family; no shooter identity) fit on completed seasons; "
               "shot-making = eFG - xeFG", "code": "pipeline/xefg.py", "gate": "§20", "refs": ["ssq"]},
    {"family": "Offensive Load", "keys": ["off_load"], "feeds": ["espn_box", "espn_pbp"],
     "method": "Taylor's published Offensive Load formula", "code": "pipeline/rates.py", "gate": "§0j", "refs": ["taylor"]},
    {"family": "Box Plus/Minus and VORP", "keys": ["bpm", "vorp", "obpm", "dbpm"], "feeds": ["espn_box"],
     "method": "BPM 2.0 published coefficients and position/role estimates; team adjustment to net rating (BPM) and "
               "offensive rating (OBPM); DBPM = BPM - OBPM; VORP = (BPM + 2) x minutes share x games/82",
     "code": "pipeline/bpm.py", "gate": "§16 / §16-b", "refs": ["bpm2"]},
    {"family": "Regressed values", "keys": ["*|reg"], "feeds": ["espn_box", "espn_pbp"],
     "method": "empirical-Bayes shrink toward the exposure-weighted league mean; k from split-half reliability; "
               "exposure = minutes, or attempts where §17-b adopted them", "code": "pipeline/shrink.py",
     "gate": "§17 / §17-b", "refs": ["stabilize"]},
    {"family": "On/off and lineups", "keys": ["onoff", "units"], "feeds": ["espn_pbp", "espn_box"],
     "method": "stint walk from substitutions on clock-ordered events, with players who act added to the floor; "
               "net rating on vs off court per 100 possessions; raw, not adjusted for teammates or opponents; "
               "a season in progress shows on/off from 500 possessions with a 90% range (§0f amendment)",
     "code": "pipeline/possessions.py, pipeline/lineups_build.py", "gate": "§0f / §21",
     "refs": ["wowy", "rapm"]},
    {"family": "Team four factors, SOS, clutch", "keys": ["four_factors", "sos", "clutch"], "feeds": ["espn_box", "espn_pbp"],
     "method": "Oliver's four factors from team box; SOS = games-weighted mean opponent net rating; clutch = last 5 min, margin within 5",
     "code": "pipeline/rates.py, pipeline/clutch.py, SOS in web/app/(dashboard)/teams/[abbr]/page.tsx", "gate": None, "refs": ["bref_glossary", "nba_glossary"]},
    {"family": "Rookie race", "keys": ["rookie_race"], "feeds": ["espn_box", "bdl"],
     "method": "rookies = BDL draft year = season - 1, plus undrafted first-year players in the ESPN spine; weekly "
               "cumulative Game Score", "code": "pipeline/rookies.py", "gate": None, "refs": ["bref_glossary"]},
]


def build(gates: dict | None = None, status: dict | None = None) -> dict:
    """`gates`: meta.json validation.gates; `status`: rates.json per-stat status,
    so a family never claims a gate for a member stat that is still descriptive."""
    gates, status = gates or {}, status or {}
    fams = []
    for f in FAMILIES:
        g = [s.strip() for s in (f["gate"] or "").split("/") if s.strip()]
        fams.append({**f, "gates": {s: gates[s] for s in g if s in gates},
                     "descriptive": [k for k in f["keys"] if status.get(k) == "descriptive"],
                     "refs": [dict(zip(("title", "url", "kb"), REFS[r])) for r in f["refs"]]})
    return {"feeds": FEEDS, "families": fams,
            "note": "pipeline/sources.py; every stat names its feed call, method, code path, gate and reference"}


def rate_status(out: Path) -> dict:
    import gzip
    f = out / "rates.json.gz"
    return json.load(gzip.open(f)).get("status", {}) if f.exists() else {}


def markdown(doc: dict) -> str:
    out = ["# Sources", "", "Generated by `pipeline/sources.py` from the last bake. Every number on the site traces to a "
           "feed call, a method, a code path, a pre-registered gate (`pipeline/results/RESULTS-HOOPS.md`) and a "
           "published reference.", "", "## Feeds", ""]
    for k, f in doc["feeds"].items():
        out.append(f"- **{f['name']}** (`{k}`): `{f['call']}`. {f['gives']}. Terms: {f['terms']}. Stored: {f['store']}."
                   + (f" Caveat: {f['caveat']}" if f.get("caveat") else ""))
    out += ["", "## Stats", "", "| Family | Stats | Feeds | Method | Code | Gate | Reference |", "|---|---|---|---|---|---|---|"]
    for f in doc["families"]:
        gate = f["gate"] or "descriptive"
        if f["descriptive"]:
            gate += f"<br>descriptive: {', '.join(f['descriptive'])}"
        for s, g in f["gates"].items():
            gate += f"<br>{s}: {g.get('credit', '')}, ran {g.get('ran', '')}"
        refs = "<br>".join(f"[{r['title']}]({r['url']}) (`{r['kb']}`)" for r in f["refs"])
        out.append(f"| {f['family']} | {', '.join(f['keys'])} | {', '.join(f['feeds'])} | {f['method']} | `{f['code']}` "
                   f"| {gate} | {refs} |")
    return "\n".join(out) + "\n"


def _selfcheck() -> None:
    d = build({"§16": {"credit": "x", "ran": "d"}}, {"pullup_rate": "descriptive", "rim_fg": "gated (§0i)"})
    assert next(f for f in d["families"] if "pullup_rate" in f["keys"])["descriptive"] == ["pullup_rate"]
    bpm = next(f for f in d["families"] if "bpm" in f["keys"])
    assert bpm["gates"] == {"§16": {"credit": "x", "ran": "d"}} and bpm["refs"][0]["kb"].endswith(".md")
    assert all(r in REFS for f in FAMILIES for r in f["refs"]) and all(x in FEEDS for f in FAMILIES for x in f["feeds"])
    assert "| Box Plus/Minus" in markdown(d)


if __name__ == "__main__":
    _selfcheck()
    meta = ROOT / "data/export/web/meta.json"
    gates = json.loads(meta.read_text())["validation"].get("gates", {}) if meta.exists() else {}
    (ROOT / "docs/SOURCES.md").write_text(markdown(build(gates, rate_status(ROOT / "data/export/web"))))
    print("selfcheck ok; wrote docs/SOURCES.md", file=sys.stderr)
