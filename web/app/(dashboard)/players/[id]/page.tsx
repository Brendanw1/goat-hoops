import Link from "next/link";
import { notFound } from "next/navigation";
import { BackLink } from "@/components/ui/back-link";
import { ShotHeatMap } from "@/components/ui/shot-heatmap";
import {
  getHoopsAdvAgg, getHoopsCareers, getHoopsClutch, getHoopsContracts, getHoopsMeta, getHoopsPlayer,
  getHoopsPlayerShots, getHoopsProjections, getHoopsRates, getHoopsRebound, getHoopsSeasAvgs,
  getHoopsSimilar, getHoopsSurplus,
} from "@/lib/data-hoops";
import type { HoopsContractDeal, HoopsSSCat } from "@/lib/data-hoops";
import { teamColor } from "@/lib/team-colors";
import { pctTone, pctBarTone } from "@/lib/tone";
import { PercentileRadar } from "@/components/ui/percentile-radar";
import { ShotQuadrant } from "@/components/ui/shot-quadrant";
import { ShotCreation } from "@/components/ui/shot-creation";

export const revalidate = 300; // prod: 5-min route cache; dev renders per request

const money = (v: number | null | undefined) => {
  if (v == null) return "—";
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${v}`;
};

const fnum = (v: number | string | null | undefined, dp = 1) => {
  if (typeof v === "number") return v.toFixed(dp);
  if (v == null) return "—";
  return v;
};
const rate = (v: number | string | null | undefined, dp = 1) =>
  typeof v === "number" ? `${(v * 100).toFixed(dp)}%` : "—";
const makePct = (m?: number | null, a?: number | null) =>
  m != null && a != null && a > 0 ? `${((m / a) * 100).toFixed(1)}%` : "—";

const dealSpan = (d: HoopsContractDeal) =>
  d.start != null && d.end != null ? `${d.start}-${String(d.end).slice(2)}` :
  d.start != null ? `${d.start}-` : "—";

const ord = (n: number) => {
  const v = Math.round(n * 100);
  const mod10 = v % 10, mod100 = v % 100;
  return `${v}${mod10 === 1 && mod100 !== 11 ? "st" : mod10 === 2 && mod100 !== 12 ? "nd" : mod10 === 3 && mod100 !== 13 ? "rd" : "th"}`;
};

const seasonLabel = (s: string | number) => `${Number(s) - 1}-${String(s).slice(2)}`;

/** League-distribution percentiles baked per season in advagg.json.gz. */
type Dist = Record<string, number | undefined>;
const distOf = (lg: Record<string, unknown> | undefined, key: string): Dist | undefined =>
  (lg?.[`${key}|dist`] as Dist | undefined) ?? undefined;

/**
 * Judgment color, one rule for every vs-league value: top decile green
 * (medium weight), bottom decile red, next bands tinted, middle neutral.
 * `lower` flips the direction for allowance stats (DRtg, opp FG%...).
 */
const tier = (v: number | null | undefined, d: Dist | undefined, lower = false): string => {
  if (typeof v !== "number" || !d || d.p25 == null || d.p75 == null) return "text-text-primary";
  if (d.p10 != null && d.p90 != null) {
    if (lower ? v <= d.p10 : v >= d.p90) return "text-pos font-medium";
    if (lower ? v >= d.p90 : v <= d.p10) return "text-neg font-medium";
  }
  if (lower ? v <= d.p25 : v >= d.p75) return "text-pos";
  if (lower ? v >= d.p75 : v <= d.p25) return "text-neg";
  return "text-text-primary";
};

const RateChip = ({ label, value, cls }: { label: string; value: React.ReactNode; cls?: string }) => (
  <div className="bg-white/[0.03] rounded px-2 py-1">
    <div className="text-text-dim text-[10px]">{label}</div>
    <div className={`font-medium tabular-nums ${cls ?? "text-text-primary"}`}>{value}</div>
  </div>
);

const PanelNote = ({ children }: { children: React.ReactNode }) => (
  <div className="text-[10px] text-text-dim/70 mt-1">{children}</div>
);

/** Career arc: PPG bars over a TS% line, one season per step (2005-26). */
function CareerArc({ rows }: { rows: number[][] }) {
  if (!rows?.length) return null;
  const W = 560, padL = 26, padR = 12, gapT = 8;
  const hPpg = 78, hTs = 62, hAxis = 18, padT = 6;
  const H = padT + hPpg + gapT + hTs + hAxis;
  const n = rows.length;
  const step = (W - padL - padR) / n;
  const bw = Math.min(step * 0.62, 26);
  const maxP = Math.max(...rows.map((r) => r[4] ?? 0), 10);
  const yPpg = (v: number) => padT + hPpg * (1 - v / maxP);
  const tsLo = 0.42, tsHi = 0.75;
  const yTs = (v: number) => padT + hPpg + gapT + hTs * (1 - (v - tsLo) / (tsHi - tsLo));
  const xc = (i: number) => padL + step * (i + 0.5);
  const tsPts = rows.map((r, i) => (r[7] != null ? `${xc(i)},${yTs(r[7])}` : null)).filter(Boolean) as string[];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
      aria-label="Career scoring and true-shooting arc by season">
      <text x={2} y={padT + 10} className="fill-current text-text-dim" fontSize="9">ppg</text>
      {rows.map((r, i) => {
        const p = r[4] ?? 0;
        return (
          <g key={r[0]}>
            <rect x={xc(i) - bw / 2} y={yPpg(p)} width={bw} height={Math.max(yPpg(0) - yPpg(p), 0)}
              rx={2} className="fill-current text-usf-green/70">
              <title>{`${seasonLabel(r[0])} · ${r[2]} gp · ${fnum(r[3])} mpg · ${fnum(r[4])} ppg · ${fnum(r[5])} rpg · ${fnum(r[6])} apg`}</title>
            </rect>
            {i === n - 1 && (
              <text x={xc(i)} y={yPpg(p) - 3} fontSize="9" textAnchor="middle"
                className="fill-current text-text-primary">{fnum(p)}</text>
            )}
          </g>
        );
      })}
      <text x={2} y={padT + hPpg + gapT + 10} className="fill-current text-text-dim" fontSize="9">TS%</text>
      {tsPts.length > 1 && (
        <polyline points={tsPts.join(" ")} fill="none" strokeWidth="1.5"
          className="stroke-current text-usf-gold/80" />
      )}
      {rows.map((r, i) => r[7] != null ? (
        <circle key={r[0]} cx={xc(i)} cy={yTs(r[7])} r={2.5} className="fill-current text-usf-gold">
          <title>{`${seasonLabel(r[0])} · TS ${(r[7] * 100).toFixed(1)}% · USG ${r[8] != null ? (r[8] * 100).toFixed(1) : "—"}%`}</title>
        </circle>
      ) : null)}
      <line x1={padL} x2={W - padR} y1={padT + hPpg + gapT + hTs + 6} y2={padT + hPpg + gapT + hTs + 6}
        className="stroke-current text-white/10" strokeWidth="1" />
      <text x={padL} y={H - 2} fontSize="9" className="fill-current text-text-dim">{seasonLabel(rows[0][0])}</text>
      <text x={W - padR} y={H - 2} fontSize="9" textAnchor="end" className="fill-current text-text-dim">
        {seasonLabel(rows[n - 1][0])}
      </text>
    </svg>
  );
}

/** One player: full stat tables (basic + advanced), career arc, category
 *  panels, and game logs across every baked season. */
export default async function HoopsPlayerPage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const doc = await getHoopsPlayer(id);
  if (!doc || !Object.keys(doc.seasons).length) notFound();
  const seasons = Object.keys(doc.seasons).sort((a, b) => Number(b) - Number(a));
  const [cdoc, advDoc, careers, meta, ss26, ss25, ps27, ps25,
         similarDoc, surplusDoc, clutchDoc, reboundDoc, projDoc, ratesDoc] = [
    await getHoopsContracts(), await getHoopsAdvAgg(), await getHoopsCareers(), await getHoopsMeta(),
    await getHoopsSeasAvgs(2026), await getHoopsSeasAvgs(2025),
    await getHoopsPlayerShots(2027), await getHoopsPlayerShots(2025),
    await getHoopsSimilar(), await getHoopsSurplus(), await getHoopsClutch(),
    await getHoopsRebound(), await getHoopsProjections(), await getHoopsRates()];
  const ssDoc = ss26 ?? ss25;
  // §0i shot creation: latest season with at least 50 attempts
  const crSeason = Object.keys(ratesDoc?.seasons ?? {}).sort((a, b) => Number(b) - Number(a))
    .find((s) => {
      const z = ratesDoc?.seasons[s]?.players[id]?.zones;
      return z && Object.values(z).reduce((n, v) => n + v[0], 0) >= 50;
    });
  const crP = crSeason ? ratesDoc?.seasons[crSeason]?.players[id] : undefined;
  const ss = ssDoc?.players[id];
  const pt = ss?.playtype ?? [];
  const adv = ss?.adv;
  const ranks = ss?.pct_ranks;
  const ps = ps27?.players[id] ? { grid: ps27.players[id], label: "2026-27 (live)" }
    : ps25?.players[id] ? { grid: ps25.players[id], label: "2024-25" } : null;
  const deals = cdoc?.deals[id] ?? [];
  const salary = cdoc?.salaries[id];
  const current = deals.find((d) => d.status === "CURRENT") ?? deals[0];
  const prior = current ? deals.filter((d) => d !== current) : deals;
  const ssLabel = ssDoc ? seasonLabel(ssDoc.season) : "";
  const arc = careers?.players[id];
  const advPool = advDoc?.seasons ?? {};
  const advSeasons = Object.keys(advPool).sort((a, b) => Number(b) - Number(a))
    .filter((s) => advPool[s]?.players?.[id]);
  const defSeason = advSeasons.find((s) => (advPool[s]?.players?.[id]?.min ?? 0) > 0);
  const defP = defSeason ? advPool[defSeason]?.players?.[id] ?? null : null;
  const defLg = defSeason ? advDoc?.league[defSeason] : undefined;
  const lower = new Set(advDoc?.lower_better ?? []);
  const partial = (s: string) => {
    const m = meta?.seasons[s];
    return m && m.games < 800 ? { games: m.games, src: (m as { source?: string }).source } : null;
  };
  // exploration layer (descriptive): archetype + neighbors, surplus, clutch, rebounds
  const simP = similarDoc?.players[id];
  const arch = simP ? similarDoc?.archetypes[String(simP.a)] : null;
  const surplusP = surplusDoc?.players[id] ?? null;
  const surplusNote = surplusDoc
    ? `${seasonLabel(surplusDoc.season_prod)} production vs ${seasonLabel(surplusDoc.season_salary)} cap hit · descriptive`
    : "";
  const clutchYears = clutchDoc?.seasons ?? {};
  const clutchSeason = ["2026", "2025", "2024"].find((s) => clutchYears[s]?.[id]) ?? null;
  const clutchP = clutchSeason ? clutchYears[clutchSeason]?.[id] ?? null : null;
  const rebBooks = reboundDoc?.seasons ?? {};
  const rebSeasons = [defSeason, "2026", "2025"].find(
    (s) => s && rebBooks[s]?.players?.[id]);
  const rebRow = rebSeasons ? rebBooks[rebSeasons]?.players?.[id] ?? null : null;
  const rebDist = rebSeasons ? rebBooks[rebSeasons]?.dist : undefined;

  return (
    <div className="space-y-5">
      <BackLink fallback="/players" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div>
        <h1 className="text-lg font-semibold text-text-primary">{doc.name}</h1>
        {(() => {
          const teams = [...new Set(seasons.map((s) => doc.seasons[s].team).filter(Boolean))];
          const cur = teams[0];
          return (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-block h-1 w-14 rounded-full align-middle"
                style={{ background: teamColor(cur) ?? "var(--color-border-subtle)" }} />
              <p className="text-xs text-text-dim">
                {teams.map((t, i) => (
                  <span key={t}>
                    {i > 0 && " · "}
                    <Link href={`/teams/${t}`} className="hover:underline inline-flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 rounded-full"
                        style={{ background: teamColor(t) }} />
                      <span className="text-text-secondary hover:text-text-primary">{t}</span>
                    </Link>
                  </span>
                ))}
                {arch && <span className="text-text-secondary"> · {arch.label}</span>}
              </p>
            </div>
          );
        })()}
      </div>

      {(current || salary) && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs space-y-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
            <h2 className="text-sm font-medium text-text-primary">Contract</h2>
            {salary && (
              <span className="text-text-secondary tabular-nums">
                {salary.season ? `${seasonLabel(salary.season)} · ` : ""}
                cap hit {money(salary.cap_hit)}
                {salary.base_salary != null && salary.base_salary !== salary.cap_hit &&
                  ` · base ${money(salary.base_salary)}`}
                {salary.team ? ` · ${salary.team}` : ""}
              </span>
            )}
          </div>
          {current && (
            <>
              <div className="text-text-secondary">
                <span className="text-text-primary font-medium">{current.type ?? "Deal"}</span>
                {current.team ? ` · ${current.team}` : ""}
                {current.years != null && <> · {dealSpan(current)} ({current.years} yr{current.years === 1 ? "" : "s"})</>}
                {current.total_value != null && <> · {money(current.total_value)}</>}
                {current.avg_salary != null && <> · {money(current.avg_salary)}/yr</>}
              </div>
              <div className="text-text-dim">
                {current.guaranteed != null && <>guaranteed {money(current.guaranteed)} · </>}
                {current.signed_using && <>signed using {current.signed_using} · </>}
                {current.fa_year != null &&
                  <>FA {current.fa_year}{current.fa_status ? ` (${current.fa_status})` : ""}</>}
              </div>
              {current.notes && <div className="text-text-dim">{current.notes}</div>}
            </>
          )}
          {surplusP?.surplus != null && (
            <div className="text-text-secondary tabular-nums pt-0.5">
              production percentile {(surplusP.prod_pct * 100).toFixed(0)} vs cap-hit
              percentile {(surplusP.sal_pct ?? 0) * 100 >= 0 ? (surplusP.sal_pct! * 100).toFixed(0) : "—"} →{" "}
              <span className={surplusP.surplus >= 0.15 ? "text-pos font-medium"
                : surplusP.surplus <= -0.15 ? "text-neg font-medium" : "text-text-primary"}>
                {surplusP.surplus >= 0 ? "+" : ""}{(surplusP.surplus * 100).toFixed(0)} pct pts
              </span>
              <span className="text-text-dim"> · {surplusNote}</span>
            </div>
          )}
          {prior.length > 0 && (
            <div className="text-text-dim tabular-nums pt-0.5 border-t border-border-subtle/50">
              {prior.map((d, i) => (
                <span key={i}>
                  {i > 0 && " · "}
                  {d.type ?? "Deal"} {dealSpan(d)}
                  {d.total_value != null ? ` (${money(d.total_value)})` : ""}
                </span>
              ))}
            </div>
          )}
          <div className="text-[10px] text-text-dim/70">balldontlie snapshot — internal research</div>
        </div>
      )}

      {projDoc?.players?.[id] && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-sm font-medium text-text-primary">
              {seasonLabel(projDoc.players[id].site)} projection
              <span className="text-text-dim font-normal text-[10px]">
                {" "}· ridge §11 · as of {projDoc.as_of}
              </span>
            </h2>
            <span className="text-[10px] text-text-dim">gate PASS 5/5 folds · intervals §14</span>
          </div>
          <div className="grid grid-cols-4 gap-2 mt-1.5 tabular-nums">
            {([["PTS/36", "pts36"], ["REB/36", "reb36"], ["AST/36", "ast36"], ["MPG", "mpg"]] as const).map(
              ([k, key]) => {
                const v = projDoc.players[id][key];
                const lo = projDoc.players[id].lo?.[key];
                const hi = projDoc.players[id].hi?.[key];
                return (
                  <div key={k}>
                    <p className="text-lg font-medium text-text-primary">{v}</p>
                    <p className="text-[10px] text-text-dim">{k}</p>
                    {lo != null && hi != null && (
                      <p className="text-[10px] text-text-dim/70 tabular-nums">
                        90% {lo}–{hi}
                      </p>
                    )}
                  </div>
                );
              })}
          </div>
          <div className="text-[10px] text-text-dim/70 mt-1.5">
            Forecast of stats, not value · beat all §10 baselines on 5/5 rolling-origin
            folds (composite ≤ 0.82) · <Link href="/research" className="hover:underline">the read</Link>
          </div>
        </div>
      )}

      {/* Season statistics — every baked season, basic box line -------------- */}
      <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs overflow-x-auto">
        <h2 className="text-sm font-medium text-text-primary mb-1.5">Season statistics</h2>
        <table className="w-full text-[11px] tabular-nums min-w-[640px]">
          <thead>
            <tr className="text-text-dim text-left">
              <th className="font-normal pr-2">Season</th><th className="font-normal">Team</th>
              <th className="font-normal">GP</th><th className="font-normal">GS</th>
              <th className="font-normal">MPG</th>
              <th className="font-normal">FG%</th><th className="font-normal">3P%</th>
              <th className="font-normal">FT%</th>
              <th className="font-normal">RPG</th><th className="font-normal">APG</th>
              <th className="font-normal">SPG</th><th className="font-normal">BPG</th>
              <th className="font-normal">TOV</th><th className="font-normal">PPG</th>
            </tr>
          </thead>
          <tbody>
            {seasons.map((s) => {
              const r = doc.seasons[s];
              const sh = r.shoot;
              const flag = partial(s);
              return (
                <tr key={s} className="border-t border-border-subtle/50">
                  <td className="pr-2 text-text-secondary whitespace-nowrap">
                    {seasonLabel(s)}
                    {flag && <span className="text-flag text-[9px] ml-1" title={`${flag.games} games covered${flag.src === "bdl" ? " — balldontlie partial" : ""}`}>partial</span>}
                  </td>
                  <td>{r.team ?? "—"}</td>
                  <td>{r.gp}</td><td>{r.gs ?? "—"}</td><td>{r.per_game.min}</td>
                  <td>{makePct(sh?.fg[0], sh?.fg[1])}</td>
                  <td>{makePct(sh?.tp[0], sh?.tp[1])}</td>
                  <td>{makePct(sh?.ft[0], sh?.ft[1])}</td>
                  <td>{r.per_game.reb}</td><td>{r.per_game.ast}</td>
                  <td>{r.per_game.stl}</td><td>{r.per_game.blk}</td>
                  <td>{r.per_game.tov}</td>
                  <td className="font-medium text-text-primary">{r.per_game.pts}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <PanelNote>
          sources: <span className="text-text-secondary">ESPN</span> for {seasons.filter((s) => doc.seasons[s].gs != null).map(seasonLabel).join(", ") || "—"},
          balldontlie for the rest — the cross-source agreement check (2024-25: 688/688 games, box lines exact)
          is in meta.json. &ldquo;partial&rdquo; seasons carry fewer than 800 league games.
        </PanelNote>
      </div>

      {/* Schedule splits — context cuts, neutral by rule (METRICS.md §4) ----- */}
      {(() => {
        const latest = seasons[0];
        const sp = doc.seasons[latest]?.splits;
        if (!sp) return null;
        const rows: [string, string, { g: number } & Record<string, number>][] = [];
        for (const [dim, buckets] of Object.entries(sp)) {
          const labels: Record<string, string> = dim === "rest"
            ? { b2b: "B2B", one: "1 day rest", two_plus: "2+ days rest" }
            : dim === "venue" ? { home: "Home", away: "Away" }
            : { top: "vs winning teams", bottom: "vs losing teams" };
          for (const [k, b] of Object.entries(buckets)) {
            rows.push([dim === "vs" ? "Opponent" : dim === "rest" ? "Rest" : "Venue",
                       labels[k] ?? k, b]);
          }
        }
        return (
          <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs overflow-x-auto">
            <h2 className="text-sm font-medium text-text-primary mb-1.5">
              Schedule splits <span className="text-text-dim font-normal text-[10px]">
                · {seasonLabel(latest)} · context cuts from the game log — neutral by rule
              </span>
            </h2>
            <table className="w-full text-[11px] tabular-nums min-w-[420px]">
              <thead>
                <tr className="text-text-dim text-left">
                  <th className="font-normal pr-2">Split</th><th className="font-normal">G</th>
                  <th className="font-normal">MPG</th><th className="font-normal">PTS</th>
                  <th className="font-normal">REB</th><th className="font-normal">AST</th>
                  <th className="font-normal">TOV</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([dim, label, b]) => (
                  <tr key={dim + label} className="border-t border-border-subtle/50">
                    <td className="pr-2 text-text-dim">{dim === label ? label : `${dim} · ${label}`}</td>
                    <td className={b.g < 10 ? "text-flag" : "text-text-primary"}>{b.g}</td>
                    <td className="text-text-primary font-medium">{b.min ?? "—"}</td>
                    <td>{b.pts ?? "—"}</td><td>{b.reb ?? "—"}</td>
                    <td>{b.ast ?? "—"}</td><td>{b.tov ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <PanelNote>violet G = under 10 games — small sample; no grade coloring until a
              persistence test passes (docs/explorations-2026-11.md)</PanelNote>
          </div>
        );
      })()}

      {/* Career arc ----------------------------------------------------------- */}
      {arc && arc.length > 1 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Career arc <span className="text-text-dim font-normal text-[10px]">· {seasonLabel(arc[0][0])} → {seasonLabel(arc[arc.length - 1][0])} · hover a point for the line</span>
          </h2>
          <CareerArc rows={arc} />
          <PanelNote>balldontlie season averages, regular seasons — internal research</PanelNote>
        </div>
      )}

      {/* Advanced rates by season --------------------------------------------- */}
      {advDoc && advSeasons.length > 0 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs overflow-x-auto">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Advanced rates <span className="text-text-dim font-normal text-[10px]">· green top quartile, red bottom · vs league, per season</span>
          </h2>
          <table className="w-full text-[11px] tabular-nums min-w-[640px]">
            <thead>
              <tr className="text-text-dim text-left">
                <th className="font-normal pr-2">Season</th><th className="font-normal">GP</th>
                <th className="font-normal">TS%</th><th className="font-normal">eFG%</th>
                <th className="font-normal">USG%</th><th className="font-normal">AST%</th>
                <th className="font-normal">ORB%</th><th className="font-normal">DRB%</th>
                <th className="font-normal">ORtg</th><th className="font-normal">DRtg</th>
                <th className="font-normal">NET</th><th className="font-normal">PIE</th>
              </tr>
            </thead>
            <tbody>
              {advSeasons.map((s) => {
                const p = advPool[s]?.players?.[id];
                if (!p) return null;
                const lg = advDoc?.league[s];
                const cov = advDoc?.coverage?.[s];
                const flagCovered = cov ? cov.full === false : (Number(lg?.rows ?? 0) || 0) < 20000;
                const v = (k: string) => (typeof p[k] === "number" ? (p[k] as number) : null);
                return (
                  <tr key={s} className="border-t border-border-subtle/50">
                    <td className="pr-2 text-text-secondary whitespace-nowrap">
                      {seasonLabel(s)}
                      {flagCovered && <span className="text-flag text-[9px] ml-1" title={cov ? `the advanced feed covered ${cov.games.toLocaleString()}${cov.spine ? ` of ~${cov.spine.toLocaleString()}` : ""} games this season` : "the advanced feed covered only part of this season"}>partial</span>}
                    </td>
                    <td>{p.gp}</td>
                    <td className={tier(v("ts_pct"), distOf(lg, "ts_pct"))}>{rate(v("ts_pct"))}</td>
                    <td className={tier(v("efg_pct"), distOf(lg, "efg_pct"))}>{rate(v("efg_pct"))}</td>
                    <td>{rate(v("usg_pct"))}</td>
                    <td className={tier(v("ast_pct"), distOf(lg, "ast_pct"))}>{rate(v("ast_pct"))}</td>
                    <td className={tier(v("orb_pct"), distOf(lg, "orb_pct"))}>{rate(v("orb_pct"))}</td>
                    <td className={tier(v("drb_pct"), distOf(lg, "drb_pct"))}>{rate(v("drb_pct"))}</td>
                    <td className={tier(v("ortg"), distOf(lg, "ortg"))}>{fnum(v("ortg"))}</td>
                    <td className={tier(v("drtg"), distOf(lg, "drtg"), true)}>{fnum(v("drtg"))}</td>
                    <td className={tier(v("net"), distOf(lg, "net"))}>{fnum(v("net"))}</td>
                    <td className={tier(v("pie"), distOf(lg, "pie"))}>{rate(v("pie"))}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <PanelNote>
            balldontlie v2-advanced game rows rolled up per season (minutes-weighted rates) — internal research
          </PanelNote>
        </div>
      )}

      {/* Similar players — descriptive exploration, not a forecast ------------ */}
      {simP && arch && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Similar players <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabel(similarDoc.season)} · {arch.label} · cosine on {similarDoc.fields.length} advanced fields
            </span>
          </h2>
          <div className="space-y-1">
            {simP.n.map(([eid, s, nm]) => (
              <div key={eid} className="flex items-center gap-2">
                <Link href={`/players/${eid}`} className="w-44 truncate text-text-primary hover:underline shrink-0">
                  {nm ?? eid}
                </Link>
                <div className="flex-1 h-2 bg-white/[0.04] rounded-sm overflow-hidden">
                  <div className="h-full bg-white/25"
                    style={{ width: `${Math.round(Math.min(Math.max((s - 0.55) / 0.45, 0), 1) * 100)}%` }} />
                </div>
                <span className="w-12 text-right text-text-dim tabular-nums">{s.toFixed(3)}</span>
              </div>
            ))}
          </div>
          <PanelNote>explore.py z-vectors over the season pool (gp ≥ 15, 250+ min) — descriptive exploration</PanelNote>
        </div>
      )}

      {ss && (
        <div className="max-w-5xl space-y-3">
          {adv && (
            <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
              <h2 className="text-sm font-medium text-text-primary mb-1.5">
                Category rates <span className="text-text-dim font-normal text-[10px]">· {ssLabel} (balldontlie season averages)</span>
              </h2>
              <div className="grid grid-cols-4 gap-1.5">
                <RateChip label="TS%" value={rate(adv.ts_pct)} />
                <RateChip label="eFG%" value={rate(adv.efg_pct)} />
                <RateChip label="USG%" value={rate(adv.usg_pct)} />
                <RateChip label="AST%" value={rate(adv.ast_pct)} />
                <RateChip label="ORtg" value={fnum(adv.off_rating)} />
                <RateChip label="DRtg" value={fnum(adv.def_rating)} />
                <RateChip label="Net" value={fnum(adv.net_rating)} />
                <RateChip label="PIE" value={fnum(adv.pie)} />
              </div>
              <PanelNote>balldontlie snapshot — internal research</PanelNote>
            </div>
          )}
          {ss && (() => {
            const KEYS = [["TS%", "adv.ts_pct"], ["USG%", "adv.usg_pct"],
              ["Net rtg", "adv.net_rating"], ["PIE", "adv.pie"],
              ["Drive pts", "drives.drive_pts"], ["AST created", "passing.ast_points_created"],
              ["Distance", "speed.dist_miles"], ["Deflections", "hustle.deflections"]] as const;
            const radarAxes = KEYS
              .filter(([, k]) => typeof ranks?.[k] === "number")
              .map(([label, k]) => ({ label: String(label), v: Number(ranks![k]),
                                     pos: ss.pct_ranks_pos?.[k] }));
            return (
            <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
              <h2 className="text-sm font-medium text-text-primary mb-1.5">
                League percentile <span className="text-text-dim font-normal text-[10px]">· {ssLabel} · blue top-decile, green top-quartile, red bottom-quartile</span>
              </h2>
              <div className="flex flex-col sm:flex-row gap-3 items-center">
                <div className="shrink-0 w-[210px]">
                  <PercentileRadar axes={radarAxes} />
                  <p className="text-[10px] text-text-dim/70 text-center -mt-1">
                    blue = league · dashed gold = {ss.pos ?? "position"} pool
                  </p>
                </div>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="grid grid-cols-4 gap-1.5">
                    {KEYS
                      .filter(([, k]) => typeof ranks?.[k] === "number")
                      .map(([label, k]) => {
                        const v = ranks![k] as number;
                        return (
                          <div key={k} className="bg-white/[0.03] rounded px-2 py-1">
                            <div className="text-text-dim text-[10px]">{label}</div>
                            <div className={`font-medium tabular-nums ${pctTone(v)}`}>{ord(v)}</div>
                          </div>
                        );
                      })}
                  </div>
                  {ss.pos && ss.pct_ranks_pos && Object.keys(ss.pct_ranks_pos).length > 0 && (
                    <>
                      <div className="text-text-dim text-[10px] pt-0.5">vs {ss.pos} pool (40+ players)</div>
                      <div className="grid grid-cols-4 gap-1.5">
                        {([["TS%", "adv.ts_pct"], ["Net rtg", "adv.net_rating"], ["PIE", "adv.pie"],
                           ["Deflections", "hustle.deflections"]] as const)
                          .filter(([, k]) => typeof ss.pct_ranks_pos?.[k] === "number")
                          .map(([label, k]) => {
                            const v = ss.pct_ranks_pos![k];
                            return (
                              <div key={label} className="bg-white/[0.03] rounded px-2 py-1">
                                <div className="text-text-dim text-[10px]">{label}</div>
                                <div className={`font-medium tabular-nums ${pctTone(v)}`}>{ord(v)}</div>
                              </div>
                            );
                          })}
                      </div>
                    </>
                  )}
                </div>
              </div>
              <PanelNote>computed at bake time from the balldontlie category rows — internal research</PanelNote>
            </div>
            );
          })()}
          {pt.length > 0 && (
            <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
              <h2 className="text-sm font-medium text-text-primary mb-1.5">
                Play types <span className="text-text-dim font-normal text-[10px]">· {ssLabel} · poss per game · bar = league percentile</span>
              </h2>
              <div className="space-y-1">
                {pt.filter((d) => Number(d.poss) > 0).map((d) => {
                  const pc = Number(d.percentile ?? 0);
                  return (
                    <div key={String(d.play_type)} className="flex items-center gap-2">
                      <span className="w-20 text-text-secondary shrink-0">{String(d.play_type).replace("nba_", "")}</span>
                      <div className="flex-1 h-2.5 bg-white/[0.04] rounded-sm overflow-hidden">
                        <div className={`h-full ${pctBarTone(pc)}`}
                          style={{ width: `${Math.round(pc * 100)}%` }} />
                      </div>
                      <span className="w-16 text-right text-text-primary tabular-nums">{fnum(d.ppp, 2)} ppp</span>
                      <span className="w-16 text-right text-text-dim tabular-nums">{fnum(d.poss)} poss</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {(() => {
            const rows: [string, string, number | string | null | undefined][] = [];
            if (ss.speed) rows.push(["Speed", "mph", ss.speed.avg_speed], ["Distance", "mi/g", ss.speed.dist_miles]);
            if (ss.drives) rows.push(["Drives", "/g", ss.drives.drives], ["Drive pts", "/g", ss.drives.drive_pts], ["Drive FG%", "%", ss.drives.drive_fg_pct]);
            if (ss.passing) rows.push(["Passes", "/g", ss.passing.passes_made], ["AST pts created", "/g", ss.passing.ast_points_created]);
            if (ss.paint) rows.push(["Paint touches", "/g", ss.paint.paint_touches], ["Paint pts", "/g", ss.paint.paint_touch_pts]);
            if (ss.catch_shoot) rows.push(["C&S FGA", "/g", ss.catch_shoot.catch_shoot_fga], ["C&S FG%", "%", ss.catch_shoot.catch_shoot_fg_pct]);
            if (ss.pullup) rows.push(["Pull-up FGA", "/g", ss.pullup.pull_up_fga], ["Pull-up FG%", "%", ss.pullup.pull_up_fg_pct]);
            if (ss.hustle) rows.push(["Deflections", "/g", ss.hustle.deflections], ["Charges", "/g", ss.hustle.charges_drawn], ["Screen asts", "/g", ss.hustle.screen_assists]);
            if (ss.defense) rows.push(["Contested FG%", "%", ss.defense.d_fg_pct]);
            return rows.length > 0 ? (
              <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
                <h2 className="text-sm font-medium text-text-primary mb-1.5">
                  Tracking <span className="text-text-dim font-normal text-[10px]">· {ssLabel}</span>
                </h2>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
                  {rows.map(([l, unit, v]) => (
                    <div key={l} className="bg-white/[0.03] rounded px-2 py-1">
                      <div className="text-text-dim text-[10px]">{l}</div>
                      <div className="text-text-primary font-medium tabular-nums">
                        {unit === "%" ? rate(v) : fnum(v)} <span className="text-text-dim text-[10px]">{unit === "%" ? "" : typeof v === "number" ? unit : ""}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null;
          })()}
        </div>
      )}

      {/* Defense & activity — v2-advanced matchup/tracking roll-up ----------- */}
      {defP && defSeason && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Defense &amp; activity <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabel(defSeason)} · per 36 · colored vs league bands
            </span>
          </h2>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
            {([
              ["Matchup min", fnum((defP.matchup_min ?? 0) as number), false, "matchup_min"],
              ["Opp FG% matched", rate(defP.matchup_fg_pct as number | null), true, "matchup_fg_pct"],
              ["Opp 3P% matched", rate(defP.matchup_3pt_pct as number | null), true, "matchup_3pt_pct"],
              ["Rim FG% allowed", rate(defP.d_rim_fg_pct as number | null), true, "d_rim_fg_pct"],
              ["Contested", fnum(defP.contested as number | null, 1), false, "contested"],
              ["Contested FG%", rate(defP.contested_fg_pct as number | null), true, "contested_fg_pct"],
              ["Deflections", fnum(defP.deflections as number | null, 1), false, "deflections"],
              ["Charges", fnum(defP.charges as number | null, 1), false, "charges"],
              ["Box outs", fnum(defP.boxouts as number | null, 1), false, "boxouts"],
              ["Screen ast", fnum(defP.screen_ast as number | null, 1), false, "screen_ast"],
              ["Loose balls", fnum(defP.loose as number | null, 1), false, "loose"],
              ["Reb chances", fnum(defP.reb_ch as number | null, 1), false, "reb_ch"],
              ["Passes", fnum(defP.passes as number | null, 1), false, "passes"],
              ["Touches", fnum(defP.touches as number | null, 1), false, "touches"],
              ["2nd ast", fnum(defP.sec_ast as number | null, 1), false, "sec_ast"],
              ["Blocks against", fnum(defP.blka as number | null, 1), true, "blka"],
              ...(rebRow ? [["Reb conversion", rate(rebRow.conv, 0), false, "reb_conv"] as [string, string, boolean, string]] : []),
            ] as [string, string, boolean, string][]).map(([label, value, isLower, key]) => (
              <RateChip key={label} label={label} value={value}
                cls={key === "reb_conv" ? tier(rebRow?.conv, rebDist)
                  : typeof defP[key] === "number" ? tier(defP[key] as number, distOf(defLg, key), isLower)
                  : undefined} />
            ))}
          </div>
          <PanelNote>
            matchup minutes, contested shots, box outs and rebound chances from balldontlie&apos;s
            v2-advanced feed — internal research
          </PanelNote>
        </div>
      )}

      {/* Clutch vs overall — descriptive deltas, small samples flagged -------- */}
      {clutchP && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Clutch vs overall <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabel(Number(clutchSeason))} · {clutchP.gp != null ? `${clutchP.gp} clutch games` : "clutch games n/a"}
              {clutchP.gp != null && clutchP.gp < 25 && <span className="text-flag"> · small sample</span>}
            </span>
          </h2>
          <div className="grid grid-cols-4 gap-1.5">
            {([["TS% Δ", clutchP.ts_d, 0.015, true], ["USG% Δ", clutchP.usg_d, null, false],
               ["Net Δ", clutchP.net_d, 1.5, false], ["PIE Δ", clutchP.pie_d, 0.01, true]] as const)
              .filter(([, v]) => typeof v === "number")
              .map(([label, v, t, pctish]) => {
                const n = v as number;
                const shown = pctish ? `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}` : `${n >= 0 ? "+" : ""}${n.toFixed(1)}`;
                return (
                  <RateChip key={label} label={label} value={shown}
                    cls={t != null && Math.abs(n) >= t ? (n > 0 ? "text-pos" : "text-neg") : undefined} />
                );
              })}
          </div>
          <PanelNote>clutch-category minus overall season rates (balldontlie season averages) — descriptive deltas, not a clutch gene</PanelNote>
        </div>
      )}

      {ss && ss.zones && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">Shot zones <span className="text-text-dim font-normal text-[10px]">· {ssLabel}</span></h2>
          {(() => {
            const mk = ss.shootmk;
            return mk && typeof mk.diff === "number" ? (
              <div className="grid grid-cols-3 gap-1.5 mb-2.5">
                <RateChip label="Shot diet eFG (expected)" value={rate(mk.xefg)} />
                <RateChip label="Real eFG" value={rate(mk.efg)} />
                <RateChip label="Shot-making Δ"
                  value={`${mk.diff >= 0 ? "+" : ""}${(mk.diff * 100).toFixed(1)}`}
                  cls={mk.diff >= 0.02 ? "text-pos" : mk.diff <= -0.02 ? "text-neg" : undefined} />
              </div>
            ) : null;
          })()}
          <table className="w-full text-[11px] tabular-nums">
            <thead>
              <tr className="text-text-dim text-left">
                <th className="font-normal pr-2">Zone</th>
                <th className="font-normal">FGA/g</th>
                <th className="font-normal">FG%</th>
                <th className="font-normal">Lg FG%</th>
                <th className="font-normal">Δ</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(ss.zones).filter(([, z]) => Number(z.fga) >= 0.3).map(([z, v]) => {
                const lgz = ssDoc?.leagueZones?.[z];
                const p = Number(v.fg_pct);
                const d = lgz ? p - lgz.fgp : null;
                return (
                  <tr key={z} className="border-t border-border-subtle/50">
                    <td className="pr-2 text-text-secondary">{z.replace(/_/g, " ")}</td>
                    <td className="text-text-primary">{fnum(v.fga, 0)}</td>
                    <td>{rate(p)}</td>
                    <td className="text-text-dim">{lgz ? rate(lgz.fgp) : "—"}</td>
                    <td className={d == null ? "" : d >= 0.10 ? "text-pos font-medium" : d >= 0.03 ? "text-pos" : d <= -0.10 ? "text-neg font-medium" : d <= -0.03 ? "text-neg" : ""}>
                      {d != null ? `${d >= 0 ? "+" : ""}${(d * 100).toFixed(1)}` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <PanelNote>
            zones vs the same-season league pool (10+ FGA rows; colored at ±3 / ±10 pts) ·
            shot-making = real eFG minus the player&apos;s shot diet priced at league rates
            (RESULTS-HOOPS §9) — descriptive benchmark, internal research
          </PanelNote>
        </div>
      )}
      {ps && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Shot heat map <span className="text-text-dim font-normal text-[10px]">· ESPN shot x/y · 2.5 ft bins</span>
          </h2>
          <ShotHeatMap grid={ps.grid} label={ps.label} />
          {ss?.shootmk && ssDoc && (() => {
            const pool = Object.entries(ssDoc.players)
              .filter(([, p]) => p.shootmk && (p.shootmk.n_fga ?? 0) >= 100)
              .map(([pid, p]) => ({
                id: pid, name: p.shootmk!.name ?? pid,
                x: p.shootmk!.xefg, y: p.shootmk!.diff, n: p.shootmk!.n_fga,
              }));
            if (pool.length < 30) return null;
            const xMid = pool.map((q) => q.x).sort((a, b) => a - b)[Math.floor(pool.length / 2)];
            return (
              <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs">
                <h2 className="text-sm font-medium text-text-primary mb-1.5">
                  Shot quality quadrant <span className="text-text-dim font-normal text-[10px]">
                    · {ssLabel} · {pool.length} players ≥ 100 FGA · dot area = FGA · §9 diet/making
                  </span>
                </h2>
                <ShotQuadrant pool={pool} highlight={id} xMid={xMid} />
                <PanelNote>x = the league&apos;s eFG in the zones the player takes (the diet); y = actual eFG minus
                  that (the making) — RESULTS-HOOPS §9, descriptive benchmark</PanelNote>
              </div>
            );
          })()}
          <div className="text-[10px] text-text-dim/70">ESPN-derived coordinates — internal research</div>
        </div>
      )}
      {crP?.zones && crP.types && (() => {
        const chip = (k: string, label: string, f: (v: number) => string) => {
          const v = crP[k], pc = (crP[`${k}|pct`] as { all?: number } | undefined)?.all;
          return typeof v === "number" ? (
            <RateChip label={label} cls={pctTone(pc != null ? pc / 100 : null)}
              value={<>{f(v)}{pc != null && <span className="text-text-dim font-normal text-[10px]"> · {pc}th</span>}</>} />
          ) : null;
        };
        return (
          <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
            <h2 className="text-sm font-medium text-text-primary mb-1.5">
              Shot creation <span className="text-text-dim font-normal text-[10px]">· {seasonLabel(crSeason!)} · regular season</span>
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 mb-2.5">
              {chip("pct_unast", "Self-created share of makes", (v) => rate(v))}
              {chip("unast36", "Self-created makes / 36", (v) => v.toFixed(1))}
              {chip("ast_pts36", "Points from assists / 36", (v) => v.toFixed(1))}
              {chip("gmsc", "Game Score / game", (v) => v.toFixed(1))}
            </div>
            <ShotCreation zones={crP.zones} types={crP.types} />
            <PanelNote>
              ESPN play-by-play: zones and assisted share passed §0i against an independent source
              (RESULTS-HOOPS); shot types are ESPN&apos;s labels, descriptive · percentiles vs qualified
              players that season · descriptive, not a forecast
            </PanelNote>
          </div>
        );
      })()}

      {/* Game logs — every baked season --------------------------------------- */}
      {seasons.map((s) => {
        const r = doc.seasons[s];
        const flag = partial(s);
        return (
          <div key={s} className="space-y-1">
            <h2 className="text-sm font-medium text-text-primary">
              {seasonLabel(s)} game log
              {r.team ? <span className="text-text-dim font-normal"> · {r.team}</span> : null}
              {flag && <span className="text-flag text-[10px] font-normal"> · partial ({flag.games} league games covered)</span>}
            </h2>
            <table className="w-full text-[11px] tabular-nums">
              <thead>
                <tr className="text-text-dim text-left">
                  <th className="font-normal pr-2">Date</th><th className="font-normal">Opp</th>
                  <th className="font-normal">Res</th><th className="font-normal">MIN</th>
                  <th className="font-normal">PTS</th><th className="font-normal">REB</th>
                  <th className="font-normal">AST</th><th className="font-normal">STL</th>
                  <th className="font-normal">BLK</th><th className="font-normal">TO</th>
                  <th className="font-normal">PF</th><th className="font-normal">FG</th>
                  <th className="font-normal">3PT</th><th className="font-normal">FT</th>
                  <th className="font-normal">+/-</th>
                </tr>
              </thead>
              <tbody>
                {[...r.games].reverse().map((g) => {
                  const dateCell = g.ext
                    ? <span className="tabular-nums text-text-secondary">{g.date}</span>
                    : <Link href={`/games/${g.id}`} className="text-text-primary hover:underline tabular-nums">{g.date}</Link>;
                  return (
                    <tr key={g.id + g.date} className="border-t border-border-subtle/50 hover:bg-white/[0.03]">
                      <td className="pr-2">{dateCell}</td>
                      <td>{g.home ? "vs" : "@"} {g.opp}</td>
                      <td className={g.res === "W" ? "text-pos" : "text-neg"}>{g.res}</td>
                      <td>{g.min ?? "—"}</td><td className="font-medium">{g.pts}</td>
                      <td>{g.reb}</td><td>{g.ast}</td><td>{g.stl}</td><td>{g.blk}</td>
                      <td>{g.tov}</td><td>{g.pf}</td>
                      <td>{g.fg ?? "—"}</td><td>{g.tp ?? "—"}</td><td>{g.ft ?? "—"}</td>
                      <td className={g.pm != null && g.pm > 0 ? "text-pos" : g.pm != null && g.pm < 0 ? "text-neg" : ""}>
                        {g.pm ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
