# GOAT-Pro Hoops — agent collaboration protocol

Multiple agents may work in this repo. This file is the coordination surface:
read it and `git log --oneline -10` before starting work; update the ledger
when a work item lands. `AGENTS.md` rules are binding on every agent.

## Where the truth lives

| File | Role |
|---|---|
| `AGENTS.md` | Clean-room rules — binding, never bypassed |
| `docs/hoops-spec.md` | The owner's requirements (stats, models, surfaces) |
| `docs/basketball-site-plan.md` | Phases, sources, current status |
| `~/Projects/vt_baseball/hoops_mart/` | The data layer (ESPN feed, mart tables, LUMA cross-check) |
| `pipeline/RESULTS-HOOPS.md` | The evidence ledger: pre-registrations, gate numbers, verdicts |
| `COLLABORATION.md` | This file — claims and status |

## Working rules

1. **Claim before you build.** Add a ledger row with your scope (files/dirs)
   and status `in-progress` before touching shared files. Shared and
   load-bearing: `pipeline/hoops_export.py`, `web/lib/r2.ts`, anything in
   `data/export/`.
2. **Small, conventional commits**; one work item per commit; the ledger row
   is updated in the same commit.
3. **Never hand-edit `data/export/web/*.json`** — regenerate with the bake.
4. **Gate discipline is absolute**: no public number without a passed gate or
   the `descriptive` label; verdicts live in RESULTS-HOOPS.md, never in
   aspiration.
5. The baseball sibling (`~/Projects/goat-pro`) and the mart
   (`~/Projects/vt_baseball/hoops_mart`) are read-only from here: claim there
   before touching anything in their trees, and never let this repo's
   `r2_sync` touch the `goatpro/` prefix.
6. The knowledge base (`~/Projects/LLM_knowledgeBase`) is the research store:
   search it before inventing methodology, and cite the doc used in the
   results ledger.

## Status ledger

| Date | Agent | Scope | Status / outcome |
|---|---|---|---|
| 2026-10-29 | claude-model-lane | **Repo scaffold + Phase-1 migration from goat-pro** | **done, local** — this repo created per the owner's two-repos-two-subdomains decision; claims everything in the initial commit. Migrated: the 7 Phase-1 surfaces (routes de-`hoops`'d: `/games`, `/teams`, `/players`, …), `lib/data-hoops.ts` (R2 paths now prefix-relative under `R2_PREFIX=hoops`), `shot-chart.tsx`, `hoops_export.py` (bake writes this repo's `data/export/web` root), `r2_sync.py` (PREFIX=`hoops`). The mart stays in `vt_baseball/hoops_mart` (read-only; gate passed 2026-10-29, see README). goat-pro keeps baseball only, its nav pill points here; the `goatpro/hoops/*` R2 keys retire at goat-pro's next sync after its hoops family is removed from its bake. Local-first holds: nothing pushed, no domain/DNS created yet. |
| 2026-10-30 | claude-model-lane | **Claim: §1 RAPM (pre-registered before any derivation)** | **in-progress** — claims `pipeline/possessions.py` + `pipeline/rapm.py` (new), `pipeline/results/RESULTS-HOOPS.md` (append only), `data/derived/` (derived tables, gitignored). Feasibility gate already passed: 48,720 ESPN sub plays, 99.99% two-participant (in/out ids clean) — stints derivable. LUMA xpts_rapm season-2025 benchmark slice pulls BEFORE the model read. Gates fixed in the prereg: possessions vs pbpstats ±2/95%, LUMA r ≥ 0.70, split-half r ≥ 0.60. |
