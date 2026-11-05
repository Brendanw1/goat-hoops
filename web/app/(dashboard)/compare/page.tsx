import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import {
  getHoopsAdvAgg, getHoopsCareers, getHoopsMeta, getHoopsPlayers,
  getHoopsSeasAvgs, getHoopsSimilar, hoopsSeasons,
} from "@/lib/data-hoops";
import type { HoopsPlayerRow } from "@/lib/data-hoops";

export const metadata = { title: "Hoops compare" };
export const dynamic = "force-dynamic";

const seasonLabel = (s: number | string) => `${Number(s) - 1}-${String(s).slice(2)}`;
const rate = (v: number | null | undefined, dp = 1) =>
  typeof v === "number" ? `${(v * 100).toFixed(dp)}%` : "—";
const fnum = (v: number | null | undefined, dp = 1) =>
  typeof v === "number" ? v.toFixed(dp) : "—";

type Dist = Record<string, number | undefined>;
const distOf = (lg: Record<string, unknown> | undefined, key: string): Dist | undefined =>
  (lg?.[`${key}|dist`] as Dist | undefined) ?? undefined;
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

type Disp = { dp?: number; pct?: boolean; lower?: boolean; neutral?: boolean };
type BasicRow = Disp & { label: string; get: (r: HoopsPlayerRow) => number | null };
type AdvRow = Disp & { label: string; get: (p: Record<string, unknown>) => number | null };

const BASIC_ROWS: BasicRow[] = [
  { label: "GP", get: (r) => r.gp, neutral: true },
  { label: "GS", get: (r) => r.gs ?? null, neutral: true },
  { label: "MPG", get: (r) => r.min, dp: 1, neutral: true },
  { label: "PTS", get: (r) => r.pts, dp: 1 },
  { label: "REB", get: (r) => r.reb, dp: 1 },
  { label: "AST", get: (r) => r.ast, dp: 1 },
  { label: "STL", get: (r) => r.stl, dp: 1 },
  { label: "BLK", get: (r) => r.blk, dp: 1 },
  { label: "TOV", get: (r) => r.tov, dp: 1, lower: true },
  { label: "FG%", get: (r) => r.fgp ?? null, pct: true, neutral: true },
  { label: "3P%", get: (r) => r.tpp ?? null, pct: true, neutral: true },
  { label: "FT%", get: (r) => r.ftp ?? null, pct: true, neutral: true },
];

const ADV_ROWS: AdvRow[] = [
  { label: "TS%", get: (p) => (typeof p.ts_pct === "number" ? p.ts_pct : null), pct: true },
  { label: "eFG%", get: (p) => (typeof p.efg_pct === "number" ? p.efg_pct : null), pct: true },
  { label: "USG%", get: (p) => (typeof p.usg_pct === "number" ? p.usg_pct : null), pct: true, neutral: true },
  { label: "AST%", get: (p) => (typeof p.ast_pct === "number" ? p.ast_pct : null), pct: true },
  { label: "ORB%", get: (p) => (typeof p.orb_pct === "number" ? p.orb_pct : null), pct: true },
  { label: "DRB%", get: (p) => (typeof p.drb_pct === "number" ? p.drb_pct : null), pct: true },
  { label: "ORtg", get: (p) => (typeof p.ortg === "number" ? p.ortg : null), dp: 1 },
  { label: "DRtg", get: (p) => (typeof p.drtg === "number" ? p.drtg : null), dp: 1, lower: true },
  { label: "NET", get: (p) => (typeof p.net === "number" ? p.net : null), dp: 1 },
  { label: "PIE", get: (p) => (typeof p.pie === "number" ? p.pie : null), pct: true },
];

const ZONE_LABEL: Record<string, string> = {
  restricted_area: "Restricted area",
  "in_the_paint_(non-ra)": "Paint (non-RA)",
  "mid-range": "Mid-range",
  left_corner_3: "Left corner 3",
  right_corner_3: "Right corner 3",
  above_the_break_3: "Above break 3",
  backcourt: "Backcourt",
};

export default async function HoopsComparePage({ searchParams }: {
  searchParams: Promise<{ s?: string; a?: string; b?: string }>;
}) {
  const sp = await searchParams;
  const [seasons, meta, board, advDoc, similarDoc, careers] = await Promise.all([
    hoopsSeasons(), getHoopsMeta(), getHoopsPlayers(), getHoopsAdvAgg(),
    getHoopsSimilar(), getHoopsCareers()]);
  const established = seasons.find((s) => (meta?.seasons[String(s)]?.games ?? 0) >= 400);
  const season = Number(sp.s) || (established ?? seasons[0]);

  const rows = (board?.seasons[String(season)] ?? []).filter((r) => r.gp >= 10);
  const byId = new Map(rows.map((r) => [r.id, r]));
  const byName = new Map(rows.map((r) => [r.name, r]));
  const defA = byId.get("3945274") ? "3945274" : rows[0]?.id;
  const defB = byName.get("Shai Gilgeous-Alexander")?.id ?? rows[1]?.id;
  const aId = sp.a && byId.has(sp.a) ? sp.a : defA;
  const bId = sp.b && byId.has(sp.b) ? sp.b : defB;
  const aRow = aId ? byId.get(aId) : undefined;
  const bRow = bId ? byId.get(bId) : undefined;

  const advPool = advDoc?.seasons[String(season)]?.players ?? {};
  const lg = advDoc?.league[String(season)];
  const lowerSet = new Set(advDoc?.lower_better ?? []);
  const ssSeason = ([2026, 2025, 2024] as const).find((s) => s === season) ?? null;
  const ss = ssSeason ? await getHoopsSeasAvgs(ssSeason) : null;
  const ssA = ss?.players[aId ?? ""];
  const ssB = ss?.players[bId ?? ""];
  const archOf = (id?: string) => {
    const p = id ? similarDoc?.players[id] : null;
    return p ? similarDoc?.archetypes[String(p.a)]?.label : null;
  };
  const ageOf = (id?: string) => {
    const crows = id ? careers?.players[id] : null;
    if (!crows) return null;
    const hit = crows.find((r) => r[0] === season);
    return hit ? hit[1] : null;
  };
  const neighborRank = (a?: string, b?: string) => {
    const na = a ? similarDoc?.players[a] : null;
    if (!na || !b) return null;
    const i = na.n.findIndex(([eid]) => eid === b);
    return i >= 0 ? { rank: i + 1, cos: na.n[i][1] } : null;
  };
  const sim = neighborRank(aId, bId) ?? neighborRank(bId, aId);

  const cell = (v: number | null, def: Disp) =>
    def.pct ? rate(v) : fnum(v, def.dp ?? 0);
  const leaderMark = (va: number | null, vb: number | null, def: Disp) => {
    if (def.neutral || va == null || vb == null || va === vb) return ["", ""];
    if ((def.lower ? va < vb : va > vb)) return ["text-pos font-semibold", ""];
    return ["", "text-pos font-semibold"];
  };

  const qs = (over: Record<string, string | number>) => {
    const p = new URLSearchParams({ s: String(season), a: aId ?? "", b: bId ?? "", ...over });
    return `/compare?${p}`;
  };

  return (
    <div className="space-y-4">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-text-primary">
          Compare <span className="text-text-dim font-normal">· {seasonLabel(season)}</span>
        </h1>
        <div className="flex gap-1.5 text-[11px]">
          {seasons.map((s) => (
            <Link key={s} href={qs({ s })}
              className={`rounded px-2 py-0.5 border ${s === season ? "border-border-subtle bg-white/[0.06] text-text-primary" : "border-transparent text-text-dim hover:text-text-secondary"}`}>
              {seasonLabel(s)}
            </Link>
          ))}
        </div>
      </div>

      <form action="/compare" method="get" className="flex flex-wrap items-center gap-2 text-xs">
        <input type="hidden" name="s" value={season} />
        {([["a", aRow], ["b", bRow]] as const).map(([key, r]) => (
          <select key={key} name={key} defaultValue={r?.id} aria-label={key === "a" ? "Player A" : "Player B"}
            className="rounded border border-border-subtle bg-white/[0.03] px-2 py-1 text-xs max-w-56">
            {[...byId.values()].sort((x, y) => y.pts - x.pts).map((r2) => (
              <option key={r2.id} value={r2.id}>{r2.name} ({r2.pts} ppg)</option>
            ))}
          </select>
        ))}
        <button type="submit"
          className="rounded border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-white/[0.06]">
          Compare
        </button>
        {sim && (
          <span className="text-text-dim">
            neighbors: #{sim.rank} (cosine {sim.cos.toFixed(3)})
          </span>
        )}
      </form>

      {aRow && bRow ? (
        <div className="space-y-4 max-w-3xl">
          {/* headers */}
          <div className="grid grid-cols-[110px_1fr_1fr] gap-x-3 text-xs">
            <span />
            {[aRow, bRow].map((r, i) => (
              <div key={r.id}>
                <Link href={`/players/${r.id}`} className="text-text-primary hover:underline font-medium">
                  {r.name}
                </Link>
                <div className="text-text-dim text-[11px]">
                  {[r.team, r.pos, ageOf(r.id) != null ? `${ageOf(r.id)} yo` : null, archOf(r.id)]
                    .filter(Boolean).join(" · ")}
                </div>
                {i === 0 && ssA?.shootmk ? (
                  <div className="text-[11px] text-text-dim tabular-nums mt-0.5">
                    shot-making {ssA.shootmk.diff >= 0 ? "+" : ""}{(ssA.shootmk.diff * 100).toFixed(1)}
                  </div>
                ) : i === 1 && ssB?.shootmk ? (
                  <div className="text-[11px] text-text-dim tabular-nums mt-0.5">
                    shot-making {ssB.shootmk.diff >= 0 ? "+" : ""}{(ssB.shootmk.diff * 100).toFixed(1)}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {/* season line */}
          <table className="w-full text-[11px] tabular-nums">
            <thead>
              <tr className="text-text-dim text-left">
                <th className="font-normal pr-2">Season line</th>
                <th className="font-normal">{aRow.team ?? "—"}</th>
                <th className="font-normal">{bRow.team ?? "—"}</th>
              </tr>
            </thead>
            <tbody>
              {BASIC_ROWS.map((def) => {
                const va = def.get(aRow), vb = def.get(bRow);
                const [ca, cb] = leaderMark(va, vb, def);
                return (
                  <tr key={def.label} className="border-t border-border-subtle/50">
                    <td className="pr-2 text-text-dim">{def.label}</td>
                    <td className={ca}>{cell(va, def)}</td>
                    <td className={cb}>{cell(vb, def)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* advanced */}
          {Object.keys(advPool).length > 0 && (
            <table className="w-full text-[11px] tabular-nums">
              <thead>
                <tr className="text-text-dim text-left">
                  <th className="font-normal pr-2">Advanced <span className="text-text-dim/60 font-normal">· vs league bands</span></th>
                  <th className="font-normal">{aRow.team ?? "—"}</th>
                  <th className="font-normal">{bRow.team ?? "—"}</th>
                </tr>
              </thead>
              <tbody>
                {ADV_ROWS.map((def) => {
                  const pa = advPool[aId!], pb = advPool[bId!];
                  const va = pa ? def.get(pa) : null, vb = pb ? def.get(pb) : null;
                  const [ca, cb] = leaderMark(va, vb, def);
                  const lower = def.lower || lowerSet.has(ADV_KEY[def.label]);
                  const d = def.neutral ? undefined : distOf(lg, ADV_KEY[def.label]);
                  return (
                    <tr key={def.label} className="border-t border-border-subtle/50">
                      <td className="pr-2 text-text-dim">{def.label}</td>
                      <td className={`${ca} ${tier(va, d, lower)}`}>{cell(va, def)}</td>
                      <td className={`${cb} ${tier(vb, d, lower)}`}>{cell(vb, def)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {/* zones */}
          {ss && ssA?.zones && ssB?.zones && ss.leagueZones && (
            <table className="w-full text-[11px] tabular-nums">
              <thead>
                <tr className="text-text-dim text-left">
                  <th className="font-normal pr-2">Zones <span className="text-text-dim/60 font-normal">· FG% (Δ vs league)</span></th>
                  <th className="font-normal">{aRow.team ?? "—"}</th>
                  <th className="font-normal">{bRow.team ?? "—"}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ZONE_LABEL).filter(([z]) => {
                  const fa = Number(ssA.zones?.[z]?.fga ?? 0), fb = Number(ssB.zones?.[z]?.fga ?? 0);
                  return fa >= 0.3 || fb >= 0.3;
                }).map(([z, label]) => {
                  const zcell = (zz: typeof ssA) => {
                    const v = zz?.zones?.[z];
                    const fgp = v ? Number(v.fg_pct) : null;
                    const lgz = ss.leagueZones?.[z];
                    const d = fgp != null && lgz ? fgp - lgz.fgp : null;
                    const cls = d == null ? "text-text-primary"
                      : d >= 0.10 ? "text-pos font-medium" : d >= 0.03 ? "text-pos"
                      : d <= -0.10 ? "text-neg font-medium" : d <= -0.03 ? "text-neg"
                      : "text-text-primary";
                    return { txt: fgp != null ? `${rate(fgp)}${d != null ? ` (${d >= 0 ? "+" : ""}${(d * 100).toFixed(1)})` : ""}` : "—", cls };
                  };
                  const A = zcell(ssA), B = zcell(ssB);
                  return (
                    <tr key={z} className="border-t border-border-subtle/50">
                      <td className="pr-2 text-text-dim">{label}</td>
                      <td className={A.cls}>{A.txt}</td>
                      <td className={B.cls}>{B.txt}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <p className="text-[10px] text-text-dim/70 max-w-3xl">
            green = the season leader on that row (advanced rows also carry their league-band
            tier); zones colored at ±3 / ±10 pts vs the same-season pool. Descriptive — internal
            research.
          </p>
        </div>
      ) : (
        <p className="text-xs text-text-dim">Pick two players with 10+ games this season.</p>
      )}
    </div>
  );
}

// label -> advagg short field (the ADV_ROWS labels map onto these)
const ADV_KEY: Record<string, string> = {
  "TS%": "ts_pct", "eFG%": "efg_pct", "USG%": "usg_pct", "AST%": "ast_pct",
  "ORB%": "orb_pct", "DRB%": "drb_pct", ORtg: "ortg", DRtg: "drtg",
  NET: "net", PIE: "pie",
};
