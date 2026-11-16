import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { StatStrip, type StripPoint } from "@/components/ui/stat-strip";
import { getHoopsPlayers, getHoopsRates, type HoopsRatesPct } from "@/lib/data-hoops";
import { pctBarTone, pctTone } from "@/lib/tone";

export const metadata = { title: "Hoops leaders" };
export const revalidate = 300;

type Def = { key: string; label: string; group: string; pct?: boolean; dp: number; what: string };
const DEFS: Def[] = [
  { key: "pts", label: "Points", group: "Per game", dp: 1, what: "points per game" },
  { key: "reb", label: "Rebounds", group: "Per game", dp: 1, what: "rebounds per game" },
  { key: "ast", label: "Assists", group: "Per game", dp: 1, what: "assists per game" },
  { key: "stl", label: "Steals", group: "Per game", dp: 1, what: "steals per game" },
  { key: "blk", label: "Blocks", group: "Per game", dp: 1, what: "blocks per game" },
  { key: "ts_pct", label: "TS%", group: "Shooting", pct: true, dp: 1, what: "true shooting: PTS / 2(FGA + 0.44·FTA)" },
  { key: "efg_pct", label: "eFG%", group: "Shooting", pct: true, dp: 1, what: "effective FG%: (FGM + 0.5·3PM) / FGA" },
  { key: "ftr", label: "FT rate", group: "Shooting", pct: true, dp: 1, what: "free-throw attempts per field-goal attempt" },
  { key: "tpar", label: "3PA rate", group: "Shooting", pct: true, dp: 1, what: "share of field-goal attempts from three" },
  { key: "usg_pct", label: "USG%", group: "Creation", pct: true, dp: 1, what: "share of team plays the player finishes (shot, trip, turnover) while on court" },
  { key: "ast_pct", label: "AST%", group: "Creation", pct: true, dp: 1, what: "share of teammates' made shots the player assists while on court" },
  { key: "ast_to", label: "AST/TO", group: "Creation", dp: 2, what: "assists per turnover" },
  { key: "orb_pct", label: "OREB%", group: "Rebounding", pct: true, dp: 1, what: "share of available offensive rebounds grabbed" },
  { key: "drb_pct", label: "DREB%", group: "Rebounding", pct: true, dp: 1, what: "share of available defensive rebounds grabbed" },
  { key: "reb_pct", label: "REB%", group: "Rebounding", pct: true, dp: 1, what: "share of all available rebounds grabbed" },
  { key: "stl_pct", label: "STL%", group: "Defense", pct: true, dp: 1, what: "steals per opponent possession while on court" },
  { key: "blk_pct", label: "BLK%", group: "Defense", pct: true, dp: 1, what: "share of opponent two-point attempts blocked" },
];
const BOX = new Set(["pts", "reb", "ast", "stl", "blk"]);
const POOLS: Record<string, string> = { all: "All", G: "Guards", F: "Forwards", C: "Centers" };

const label = (s: number) => `${s - 1}-${String(s).slice(2)}`;

export default async function LeadersPage({ searchParams }: {
  searchParams: Promise<{ season?: string; stat?: string; pool?: string; n?: string }>;
}) {
  const sp = await searchParams;
  const [rates, board] = await Promise.all([getHoopsRates(), getHoopsPlayers()]);
  if (!rates) return <p className="text-xs text-text-dim">Leaderboards are not baked yet.</p>;

  const seasons = Object.keys(rates.seasons).map(Number).sort((a, b) => b - a);
  const season = seasons.includes(Number(sp.season)) ? Number(sp.season) : seasons[0];
  const live = new Set(rates.stats);
  const defs = DEFS.filter((d) => BOX.has(d.key) || live.has(d.key));
  const def = defs.find((d) => d.key === sp.stat) ?? defs.find((d) => d.key === "ts_pct") ?? defs[0];
  const lg = rates.league[String(season)];
  const pool = sp.pool && sp.pool in POOLS && (sp.pool === "all" || (lg.pools[sp.pool] ?? 0) >= 40)
    ? sp.pool : "all";
  const n = [25, 50, 100].includes(Number(sp.n)) ? Number(sp.n) : 25;
  const lower = rates.lower_better.includes(def.key);
  const gate = rates.gate_0h.stats?.[def.key];
  const status = BOX.has(def.key) ? "box score"
    : gate && (gate.pass || gate.pass_0hb) ? "gated (§0h)" : "descriptive";

  const boardRows = new Map((board?.seasons[String(season)] ?? []).map((r) => [r.id, r]));
  const qualified = Object.entries(rates.seasons[String(season)]?.players ?? {})
    .filter(([, p]) => p.q && (pool === "all" || p.pos === pool))
    .flatMap(([id, p]) => {
      const b = boardRows.get(id);
      const raw = BOX.has(def.key) ? b?.[def.key as "pts"] : p[def.key];
      if (typeof raw !== "number" || !b) return [];
      const pc = p[`${def.key}|pct`] as HoopsRatesPct | undefined;
      const baked = pool === "all" ? pc?.all : pc?.pos;
      return [{ id, name: b.name, team: b.team, pos: p.pos, gp: b.gp, mpg: b.min, v: raw,
                pct: baked != null ? baked / 100 : null }];
    });
  // box stats carry no baked percentile — rank within the same qualified pool
  if (BOX.has(def.key)) {
    const vs = qualified.map((r) => r.v).sort((a, b) => a - b);
    for (const r of qualified) {
      const below = vs.filter((x) => x < r.v).length, eq = vs.filter((x) => x === r.v).length;
      r.pct = (below + eq / 2) / vs.length;
    }
  }
  qualified.sort((a, b) => (lower ? a.v - b.v : b.v - a.v));
  const top = qualified.slice(0, n);
  const fmt = (v: number) => def.pct ? `${(v * 100).toFixed(def.dp)}%` : v.toFixed(def.dp);
  const points: StripPoint[] = qualified.map((r) => ({ id: r.id, name: r.name, v: r.v, pct: r.pct }));
  const qs = (o: Record<string, string | number>) => {
    const u = new URLSearchParams({ season: String(season), stat: def.key, pool, n: String(n) });
    for (const [k, v] of Object.entries(o)) u.set(k, String(v));
    return `/leaders?${u}`;
  };
  const chip = (on: boolean) =>
    `rounded px-2 py-0.5 border ${on ? "border-border-subtle bg-white/[0.06] text-text-primary" : "border-transparent text-text-dim hover:text-text-secondary"}`;
  const groups = [...new Set(defs.map((d) => d.group))];

  return (
    <div className="space-y-4 max-w-5xl">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-text-primary">Leaders · {label(season)}</h1>
        <div className="flex gap-1.5 text-[11px]">
          {seasons.map((s) => <Link key={s} href={qs({ season: s })} className={chip(s === season)}>{label(s)}</Link>)}
        </div>
      </div>

      <div className="space-y-1.5 text-[11px]">
        {groups.map((g) => (
          <div key={g} className="flex flex-wrap items-center gap-1.5">
            <span className="w-20 shrink-0 text-text-dim">{g}</span>
            {defs.filter((d) => d.group === g).map((d) => (
              <Link key={d.key} href={qs({ stat: d.key })} className={chip(d.key === def.key)}>{d.label}</Link>
            ))}
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="w-20 shrink-0 text-text-dim">Pool</span>
          {Object.entries(POOLS).filter(([k]) => k === "all" || (lg.pools[k] ?? 0) >= 40).map(([k, v]) => (
            <Link key={k} href={qs({ pool: k })} className={chip(k === pool)}>{v}</Link>
          ))}
          <span className="ml-3 text-text-dim">Show</span>
          {[25, 50, 100].map((k) => <Link key={k} href={qs({ n: k })} className={chip(k === n)}>{k}</Link>)}
        </div>
      </div>

      <p className="text-xs text-text-dim">
        <span className="text-text-secondary font-medium">{def.label}</span> — {def.what}.
        {" "}Qualified: {lg.qual_min}+ minutes and {lg.qual_gp}+ games ({qualified.length} {POOLS[pool].toLowerCase()}
        {pool === "all" ? " players" : ""}). Percentiles rank within this pool.
        {" "}<span className={status === "descriptive" ? "text-flag" : ""}>Status: {status}</span>
        {status === "descriptive" && " — no external reference to check it against yet."}
      </p>

      <StatStrip points={points} shown={new Set(top.map((r) => r.id))} fmt={fmt} label={def.label} lower={lower} />

      <div className="overflow-x-auto">
        <table className="w-full text-[12px] tabular-nums">
          <thead className="text-text-dim text-[10.5px] text-left">
            <tr className="border-b border-border-subtle">
              <th className="py-1.5 pr-2 w-8">#</th><th className="pr-2">Player</th><th className="pr-2">Team</th>
              <th className="pr-2">Pos</th><th className="pr-2 text-right">GP</th><th className="pr-2 text-right">MPG</th>
              <th className="pr-3 text-right">{def.label}</th><th className="w-48">Percentile</th>
            </tr>
          </thead>
          <tbody>
            {top.map((r, i) => (
              <tr key={r.id} className="border-b border-white/[0.04] hover:bg-white/[0.03]">
                <td className="py-1 pr-2 text-text-dim">{i + 1}</td>
                <td className="pr-2"><Link href={`/players/${r.id}`} className="text-text-primary hover:underline">{r.name}</Link></td>
                <td className="pr-2 text-text-secondary">{r.team ?? "—"}</td>
                <td className="pr-2 text-text-dim">{r.pos ?? "—"}</td>
                <td className="pr-2 text-right text-text-secondary">{r.gp}</td>
                <td className="pr-2 text-right text-text-secondary">{r.mpg.toFixed(1)}</td>
                <td className={`pr-3 text-right ${pctTone(r.pct)}`}>{fmt(r.v)}</td>
                <td>
                  {r.pct != null && (
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-36 rounded-full bg-white/[0.06]">
                        <div className={`h-1.5 rounded-full ${pctBarTone(r.pct)}`} style={{ width: `${Math.max(r.pct * 100, 2)}%` }} />
                      </div>
                      <span className="text-[10.5px] text-text-dim w-6 text-right">{Math.round(r.pct * 100)}</span>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!top.length && <p className="text-xs text-text-dim py-3">No qualified players for this pool yet.</p>}
      </div>

      <p className="text-[10px] text-text-dim/70">
        Regular season, computed from ESPN box scores with NBA.com definitions (on-court team totals
        estimated by minutes share). Gated rates passed the §0h/§0h-b checks against an independent
        source; see Methods. Descriptive, not a forecast.
      </p>
    </div>
  );
}
