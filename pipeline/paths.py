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
