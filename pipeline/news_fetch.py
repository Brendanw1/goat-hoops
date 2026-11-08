"""news_fetch.py — the ticker's data feed (ESPN public JSON APIs).

    python pipeline/news_fetch.py

Sources (keyless, documented, same etiquette as the mart's ESPN ingest —
one fetch per RUN, never per site visitor; 1.5 s pause, honest UA):
  - site.api.espn.com/.../nba/injuries  — league injury report (team, player,
    status Out/Day-To-Day/Questionable/..., shortComment with game context)
  - site.api.espn.com/.../nba/news?limit=12 — headlines
NBA.com hosts are blocked from this network (the gap map) and are not touched;
paid feeds (BDL injuries) lapse with the trial — ESPN replaces them.

Output: data/news/espn.json — normalized ticker items; the bake folds it into
export/web/ticker.json where the site reads it. The site NEVER calls ESPN.
"""

import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news"
UA = "goat-hoops-research/1.0 (local analytics; contact: site owner)"
PAUSE_S = 1.5

INJURIES_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries")
NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news?limit=12"

# full team name -> site abbreviation (the injuries payload uses full names)
NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GS", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NO", "New York Knicks": "NY", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SA", "Toronto Raptors": "TOR", "Utah Jazz": "UTAH",
    "Washington Wizards": "WSH",
}


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    inj = get(INJURIES_URL)
    time.sleep(PAUSE_S)
    news = get(NEWS_URL)

    items = []
    for t in inj.get("injuries", []):
        team_full = t.get("displayName", "")
        abbr = NAME_TO_ABBR.get(team_full)
        for i in t.get("injuries", []):
            status = i.get("status") or "Unknown"
            athlete = (i.get("athlete") or {}).get("displayName", "?")
            comment = (i.get("shortComment") or i.get("longComment") or "").strip()
            items.append({"kind": "injury", "status": status,
                          "player": athlete, "team": abbr,
                          "team_full": team_full,
                          "comment": comment[:120],
                          "date": (i.get("date") or "")[:16]})
    headlines = []
    for a in news.get("articles", [])[:12]:
        headlines.append({"headline": a.get("headline", ""),
                          "link": (a.get("links") or {}).get("web") or a.get("link", {}).get("href"),
                          "published": (a.get("published") or "")[:16],
                          "byline": a.get("byline") or ""})

    doc = {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "season": inj.get("season", {}).get("year"),
           "injuries": items, "news": headlines}
    (OUT / "espn.json").write_text(json.dumps(doc, indent=1))
    statuses = {}
    for it in items:
        statuses[it["status"]] = statuses.get(it["status"], 0) + 1
    print(f"injury items: {len(items)} {statuses} | headlines: {len(headlines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
