"""advanced_walk_resume.py — streaming resume of the BDL v2 advanced walk.

Their paged() (hoops_mart/bdl_pull.py) re-parses the whole checkpoint into
memory before resuming — the 1.5 GB advanced_2025.pages.jsonl becomes
~8-12 GB of Python objects, which this Mac can't spare while the baseball
session's training job is peaking. This driver reads only the checkpoint's
TAIL for the live cursor, then appends pages in the same
{"cursor": ..., "rows": [...]} jsonl format their tooling and the
goat-hoops bake (jsonl-first dedup) already consume. Nothing under
vt_baseball is modified except appending to the walk's own checkpoint
data file — the path their pull_advanced writes on every page.

    python3 pipeline/advanced_walk_resume.py --label 2025 --pages 2500

Each page lands in the checkpoint before the next request (the paged()
crash-resume contract); every page costs one rate-limited request via
their get() (13 s pause = the 5 req/min trial rule, shared with the odds
loop). A round ends when the feed returns no next_cursor (exhausted —
print COMPLETE) or at --pages (partial — a later window resumes free).
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Projects/vt_baseball/hoops_mart"))
from bdl_pull import get, API_ROOT, PER_PAGE  # noqa: E402  (auth + rate limit + retries)

CK_DIR = Path.home() / "Projects/vt_baseball/hoops_mart/data/bdl"


def last_complete_line(path: Path, scan: int = 4 * 1024 * 1024) -> tuple[str, int]:
    """(live cursor, line count) — the cursor rides at the START of each
    page line, so scan backwards until a newline-bounded line parses."""
    size = path.stat().st_size
    n_lines = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            n_lines += chunk.count(b"\n")
        # reverse scan for the last complete line
        start = max(0, size - scan)
        f.seek(start)
        tail = f.read(size - start)
    lines = [l for l in tail.split(b"\n") if l.strip()]
    for l in reversed(lines):
        try:
            d = json.loads(l)
            return str(d.get("cursor") or ""), n_lines
        except json.JSONDecodeError:
            continue  # torn tail from a crash mid-write
    return "", n_lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="2025", help="checkpoint label (advanced_<label>.pages.jsonl)")
    ap.add_argument("--pages", type=int, default=2500)
    ap.add_argument("--deadline", default="",
                    help="local 'YYYY-MM-DD HH:MM' — stop cleanly when the trial window ends")
    a = ap.parse_args()
    deadline = time.mktime(time.strptime(a.deadline, "%Y-%m-%d %H:%M")) if a.deadline else None

    ck = CK_DIR / f"advanced_{a.label}.pages.jsonl"
    if not ck.exists():
        sys.exit(f"no checkpoint at {ck}")
    cursor, n_cached = last_complete_line(ck)
    print(f"resume advanced_{a.label}: {n_cached:,} pages cached, "
          f"cursor {'END (exhausted)' if not cursor else '...' + cursor[-6:]}", flush=True)
    if not cursor:
        print("COMPLETE (nothing to resume)", flush=True)
        return

    t0 = time.monotonic()
    fetched = rows = 0
    with ck.open("a") as f:
        while fetched < a.pages:
            if deadline and time.time() >= deadline:
                print(f"DEADLINE REACHED after {fetched} pages (+{rows:,} rows) — "
                      f"checkpoint kept, trial window over", flush=True)
                return
            d = get(f"{API_ROOT}/nba/v2/stats/advanced?season={a.label}"
                    f"&per_page={PER_PAGE}&cursor={cursor}")
            page = d.get("data", [])
            raw = (d.get("meta") or {}).get("next_cursor")
            nxt = "" if raw is None else str(raw)  # BDL sends ints; str keeps slicing honest
            f.write(json.dumps({"cursor": nxt, "rows": page}) + "\n")
            f.flush()
            fetched += 1
            rows += len(page)
            cursor = nxt
            if fetched % 100 == 0:
                rate = fetched / max(time.monotonic() - t0, 1) * 60
                print(f"  {fetched}/{a.pages} pages | +{rows:,} rows | "
                      f"{rate:.1f} pages/min | cursor ...{cursor[-6:]}", flush=True)
            if not nxt:
                print(f"COMPLETE after {fetched} pages (+{rows:,} rows) — "
                      f"feed exhausted, receipt ok on their next pull run", flush=True)
                break
        else:
            print(f"ROUND PARTIAL: {fetched} pages (+{rows:,} rows) at cap — "
                  f"checkpoint kept, resume again in a later window", flush=True)


if __name__ == "__main__":
    main()
