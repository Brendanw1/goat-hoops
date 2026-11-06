import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsAdvAgg, getHoopsPlayers, getHoopsSimilar } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const seasonLabel = (s: string | number) => `${Number(s) - 1}-${String(s).slice(2)}`;
const rate = (v: number | string | null | undefined, dp = 1) =>
  typeof v === "number" ? `${(v * 100).toFixed(dp)}%` : "—";
const fnum = (v: number | string | null | undefined, dp = 1) => {
  if (typeof v === "number") return v.toFixed(dp);
  if (v == null) return "—";
  return v;
};

/** League-distribution percentiles baked per season in advagg.json.gz. */
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

/** label -> [advagg key, formatter] for the headline comp row. */
const HEAD: [string, string, "rate" | "num", boolean?][] = [
  ["TS%", "ts_pct", "rate"], ["eFG%", "efg_pct", "rate"], ["USG%", "usg_pct", "rate"],
  ["AST%", "ast_pct", "rate"], ["DRB%", "drb_pct", "rate"], ["3PA share", "pct_fga_3pt", "rate"],
  ["NET", "net", "num"], ["PIE", "pie", "rate"],
];

export default async function Page({ searchParams }: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const [simDoc, board, advDoc] = await Promise.all([
    getHoopsSimilar(), getHoopsPlayers(), getHoopsAdvAgg()]);
  const season = simDoc?.season ?? 2026;
  const names = new Map((board?.seasons[String(season)] ?? []).map((r) => [r.id, r]));
  const advPool = advDoc?.seasons[String(season)]?.players ?? {};
  const lg = advDoc?.league[String(season)] as Record<string, unknown> | undefined;
  const archs = simDoc?.archetypes ?? {};
  const pool = simDoc?.players ?? {};
  const ids = Object.keys(pool).sort((a, b) =>
    (names.get(a)?.name ?? a).localeCompare(names.get(b)?.name ?? b));

  const arch = sp.arch != null && sp.arch !== "" && archs[sp.arch] ? sp.arch : null;
  const pid = sp.p && pool[sp.p] ? sp.p : null;
  const qs = (over: Record<string, string>) => {
    const q = new URLSearchParams({ ...(arch ? { arch } : {}), ...(pid ? { p: pid } : {}), ...over });
    return `/comps?${q}`;
  };
  const nameOf = (id: string) => names.get(id)?.name ?? `(${id})`;

  const fmtCell = (v: number | null, kind: "rate" | "num") => (kind === "rate" ? rate(v) : fnum(v));
  const fieldCls = (id: string, key: string) => {
    const p = advPool[id] as Record<string, unknown> | undefined;
    const v = p ? (p[key] as number | null) ?? null : null;
    return { v, cls: tier(v, distOf(lg, key)) };
  };
  const selectIds = arch ? ids.filter((id) => String(pool[id].a) === arch) : ids;

  return (
    <div className="space-y-4">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <h1 className="text-lg font-semibold text-text-primary">
        Comps finder{" "}
        <span className="text-text-dim font-normal">· {seasonLabel(season)} · {ids.length} players · k-means archetypes + cosine neighbors</span>
      </h1>

      {/* archetype strip */}
      <div className="flex flex-wrap gap-1.5 text-[11px]">
        {Object.entries(archs).map(([k, a]) => (
          <Link key={k} href={qs({ arch: arch === k ? "" : k })}
            className={`rounded px-2 py-0.5 border ${arch === k ? "border-border-subtle bg-white/[0.06] text-text-primary" : "border-transparent text-text-dim hover:text-text-secondary"}`}>
            {a.label} <span className="text-text-dim/70">({a.size})</span>
          </Link>
        ))}
        {arch && (
          <Link href={qs({ arch: "" })} className="text-text-dim hover:text-text-secondary underline underline-offset-2">
            clear
          </Link>
        )}
      </div>

      {/* archetype roster */}
      {arch && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
          <div className="text-text-dim text-[10px] mb-1.5">
            {archs[arch].label} — defining z-scores vs league:{" "}
            {archs[arch].centroid.map(([f, z]) => `${f} +${z.toFixed(2)}`).join(" · ")}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5">
            {ids.filter((id) => String(pool[id].a) === arch).map((id) => (
              <Link key={id} href={qs({ p: id })} className="hover:text-text-secondary">
                {nameOf(id)} <span className="text-text-dim">{names.get(id)?.team ?? ""}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* picker */}
      <form action="/comps" method="get" className="flex flex-wrap items-center gap-2 text-xs">
        {arch && <input type="hidden" name="arch" value={arch} />}
        <select name="p" defaultValue={pid ?? ""} aria-label="Player"
          className="bg-transparent border border-border-subtle rounded px-1.5 py-0.5 max-w-64">
          <option value="">Pick a player…</option>
          {selectIds.map((id) => <option key={id} value={id}>{nameOf(id)}</option>)}
        </select>
        <button className="rounded px-2 py-0.5 border border-border-subtle hover:bg-white/[0.06]">Find comps</button>
      </form>

      {/* selected player + neighbors */}
      {pid && (
        <div className="space-y-3">
          <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs overflow-x-auto">
            <div className="mb-1.5">
              <Link href={`/players/${pid}`} className="text-sm font-medium text-text-primary hover:text-text-secondary">
                {nameOf(pid)}
              </Link>
              <span className="text-text-dim ml-2">
                {names.get(pid)?.team ?? "—"} · {archs[String(pool[pid].a)]?.label ?? "—"}
              </span>
            </div>
            <table className="w-full text-[11px] tabular-nums min-w-[620px]">
              <thead>
                <tr className="text-text-dim text-left">
                  {HEAD.map(([label]) => <th key={label} className="font-normal pr-2">{label}</th>)}
                </tr>
              </thead>
              <tbody>
                <tr>
                  {HEAD.map(([_, key, kind]) => {
                    const { v, cls } = fieldCls(pid, key);
                    return <td key={key} className={`pr-2 ${cls}`}>{fmtCell(v, kind)}</td>;
                  })}
                </tr>
              </tbody>
            </table>
            <div className="text-[10px] text-text-dim/70 mt-1">
              green top quartile (top decile bold), red bottom · vs league
            </div>
          </div>

          <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs overflow-x-auto">
            <h2 className="text-sm font-medium text-text-primary mb-1.5">
              Closest comps <span className="text-text-dim font-normal text-[10px]">· cosine over {simDoc?.fields.length ?? 0} z-scored advanced fields</span>
            </h2>
            <table className="w-full text-[11px] tabular-nums min-w-[720px]">
              <thead>
                <tr className="text-text-dim text-left">
                  <th className="font-normal pr-2">#</th><th className="font-normal pr-2">Comp</th>
                  <th className="font-normal pr-2">cos</th><th className="font-normal pr-2">Archetype</th>
                  {HEAD.map(([label]) => <th key={label} className="font-normal pr-2">{label}</th>)}
                </tr>
              </thead>
              <tbody>
                {pool[pid].n.map(([nid, cos], i) => (
                  <tr key={nid} className="border-t border-border-subtle/50">
                    <td className="pr-2 text-text-dim">{i + 1}</td>
                    <td className="pr-2">
                      <Link href={`/players/${nid}`} className="hover:text-text-secondary">{nameOf(nid)}</Link>
                      <Link href={qs({ p: nid })} className="text-text-dim/60 ml-1.5 hover:text-text-secondary" title="use this player as the reference">↺</Link>
                    </td>
                    <td className="pr-2 text-text-secondary">{cos.toFixed(3)}</td>
                    <td className="pr-2 text-text-dim">{archs[String(pool[nid]?.a)]?.label ?? "—"}</td>
                    {HEAD.map(([_, key, kind]) => {
                      const { v, cls } = fieldCls(nid, key);
                      return <td key={key} className={`pr-2 ${cls}`}>{fmtCell(v, kind)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-[10px] text-text-dim/70 mt-1.5">
              {simDoc?.note ?? "descriptive exploration"} — a comp shares the role profile, not the talent level; the
              tier-colored fields are how they differ.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
