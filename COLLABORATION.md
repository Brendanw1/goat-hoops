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
| 2026-10-31 | claude-model-lane | **§1 RAPM read v3: FAIL on the benchmark gate — model family validated, roadmap set** | **done, verdict recorded** — the full pre-registered loop ran to a verdict: response moved to pbpstats possessions (points MAE 0.16 vs box, FT parser keyed on the (N PTS) scoring marker), rosters from official intervals (minutes gate 0.28 min), grid re-opened as an amendment on the corrected response. **No λ meets both gates**: stability crosses 0.60 at λ≈100k; the LUMA benchmark peaks 0.464 (λ=30k) vs the 0.70 bar. The model is real (SGA/Jokic/Tatum top-10, impact-role tier, Washington core at the bottom) — the ceiling measures single-season-raw-points vs multi-season-xPTS design distance. Roadmap in RESULTS-HOOPS: multi-season fit → xPTS response (Phase-2 shot quality) → priors. No surface ships. Commits 131306c, 50ca4d7, 97b67dc (vt_baseball possessions puller). |
| 2026-10-31 | claude-model-lane | **§2 multi-season RAPM read: FAIL both gates — benchmark 0.464 → 0.618, lever delivered, §3 named** | **done, verdict recorded** — claims `pipeline/rapm_multi.py` (new), `pipeline/model_rows.py` (new), `multi_season_pull.py` (vt_baseball, per-(player,team-stint) pulls). Three seasons pooled (554,869 possessions, 740 players) on the traded-player-corrected lineage — the mid-season-trade interval holes were clustering coverage loss by team (capture ratios 0.15–0.85); per-stint pulls lifted coverage to 71–85%. Response validated (MAE 0.16 vs box). **Verdict: FAIL** — at the CV-selected λ=10k, stability 0.481/0.60 and benchmark 0.611/0.70; peaks 0.671 stability (λ=100k) and 0.618 benchmark (λ=30k). The multi-season lever closed ~a third of the §1 gap. Next: §3 = xPTS response (Phase-2 shot quality) — the last named lever before priors. No surface ships. |
| 2026-11-01 | claude-model-lane | **§3 xPTS read v1: FAIL both gates (0.313 peak vs §1's 0.464) — the misordering re-enters via shot attribution** | **done, verdict recorded** — claims `pipeline/model_rows.py` + `pipeline/stints_from_pt.py` xPTS additions (league surface: 13 distance×value buckets from our validated shots, FT% 0.778; possession xPTS = Σ shot xPTS + FT xPTS by play index). The read: benchmark peaks 0.313, stability flat ~0.10 — WORSE than raw points. Diagnosis: the xPTS response reintroduces play attribution through shot-to-segment matching, and ESPN's misordered scoring sequences are exactly where shots live. **Corrected §3 (next session): clock-match ESPN shots to pbpstats possessions** (their windows are ordered), then repeat the single-season xPTS read, then multi-season. No surface ships. |
| 2026-11-01 | claude-model-lane | **§3 xPTS corrected read: the lever CONFIRMED (single-season 0.464 → 0.621); combined multi-season xPTS dilutes — verdict FAIL, no surface** | **done** — the Events-text response (possession xPTS parsed from pbpstats' own FGA lines: distance → surface bucket → FG% × value, made FTs × 1.0; 196k FGA, full 134k-row coverage, zero cross-source matching) beat §1's single-season points by +0.157 and matched §2's multi-season points. The combined multi-season × xPTS fit DILUTES (0.524) — a 3-season averaged rating regresses against the season-2025 LUMA slice by design. The 0.08 to the bar = surface richness (shot type, defender context) + priors — genuinely multi-session work, not a quick fix. All four designs' λ-sensitivity tables in RESULTS-HOOPS; commits 448447e, f4636d5. The three-season spine (intervals, possessions, xPTS, id joins) is permanent. |
