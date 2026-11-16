"""Shared pipeline paths — the mart is read-only from vt_baseball."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "export" / "web"
# The data layer lives beside the baseball mart, not inside this repo; the
# env var exists for tests and for pointing at a checkout elsewhere.
MART = Path(os.environ.get(
    "HOOPS_MART",
    Path.home() / "Projects" / "vt_baseball" / "hoops_mart" / "data" / "mart"))


# The BDL page dumps (hoops_mart/data/bdl/*.pages.jsonl, several GB) may be kept zstd-compressed beside their name
# (<name>.pages.jsonl.zst) to save disk. Readers take the raw file when it is there, else stream the .zst: the same
# lines. Anything that APPENDS (a walk resume) calls restore_pages() first, so it always appends to a raw file.
def _zst(p: Path) -> Path:
    return p.with_name(p.name + ".zst")


def pages_exist(p: Path) -> bool:
    return p.exists() or _zst(p).exists()


def open_pages(p: Path):
    """Text lines of a page dump: the raw file, else its .zst (multi-frame safe), else None."""
    if p.exists():
        return open(p, "r")
    if not _zst(p).exists():
        return None
    import io
    import zstandard
    raw = zstandard.ZstdDecompressor().stream_reader(open(_zst(p), "rb"), read_across_frames=True, closefd=True)
    return io.TextIOWrapper(raw, encoding="utf-8")


def restore_pages(p: Path) -> None:
    """Before appending: a compressed-only dump goes back to raw (the .zst stays as the backup)."""
    if p.exists() or not _zst(p).exists():
        return
    import zstandard
    tmp = p.with_name(p.name + ".restoring")
    import shutil
    with zstandard.ZstdDecompressor().stream_reader(open(_zst(p), "rb"), read_across_frames=True,
                                                    closefd=True) as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    tmp.rename(p)
