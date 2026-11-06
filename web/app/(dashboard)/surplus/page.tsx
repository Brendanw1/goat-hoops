import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsPlayers, getHoopsSurplus } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const money = (v: number | null | undefined) => {
  if (v == null) return "—";
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${v}`;
};
const seasonLabel = (s: string | number) => `${Number(s) - 1}-${String(s).slice(2)}`;
const pct = (v: number | null | undefined) => (typeof v === "number" ? `${(v * 100).toFixed(0)}` : "—");
const surClass = (v: number | null) =>
  v == null ? "text-text-primary"
  : v >= 0.15 ? "text-pos font-medium"
  : v <= -0.15 ? "text-neg font-medium"
  : "text-text-primary";
const surFmt = (v: number | null) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(0)}`);

type SurRow = {
  id: string; name: string; team: string | null; pos: string | null; gp: number;
  prod_pct: number; sal: number | null; sal_pct: number | null; surplus: number | null;
};

const SUR_HDR = "pct pts of percentile gap";

export default async function Page({ searchParams }: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const [surDoc, board] = await Promise.all([getHoopsSurplus(), getHoopsPlayers()]);
  const prodSeason = surDoc?.season_prod ?? 2026;
  const rows0 = (board?.seasons[String(prodSeason)] ?? []) as {
    id: string; name: string; team: string | null; pos: string | null; gp: number;
  }[];
  const sur = surDoc?.players ?? {};

  const rows: SurRow[] = rows0.flatMap((r) => {
    const s = sur[r.id];
    return s ? [{ ...r, prod_pct: s.prod_pct, sal: s.sal, sal_pct: s.sal_pct, surplus: s.surplus }] : [];
  });
  const teams = [...new Set(rows.map((r) => r.team).filter((t): t is string => !!t))].sort();
  const poss = [...new Set(rows.map((r) => r.pos?.[0]).filter((p): p is string => !!p))].sort();

  const team = sp.team && teams.includes(sp.team) ? sp.team : "ALL";
  const pos = sp.pos && poss.includes(sp.pos) ? sp.pos : "ALL";
  const sort = (["surplus", "prod", "sal", "name"] as const).includes(sp.sort as "surplus")
    ? (sp.sort as "surplus" | "prod" | "sal" | "name") : "surplus";

  const filtered = rows.filter((r) =>
    (team === "ALL" || r.team === team) && (pos === "ALL" || r.pos?.[0] === pos));
  const sorted = [...filtered].sort((a, b) => {
    if (sort === "name") return a.name.localeCompare(b.name);
    if (sort === "prod") return b.prod_pct - a.prod_pct;
    if (sort === "sal") return (b.sal ?? 0) - (a.sal ?? 0);
    return (b.surplus ?? -Infinity) - (a.surplus ?? -Infinity);
  });

  const best = [...rows].sort((a, b) => (b.surplus ?? -9) - (a.surplus ?? -9)).slice(0, 3);
  const worst = [...rows].sort((a, b) => (a.surplus ?? 9) - (b.surplus ?? 9)).slice(0, 3);

  const qs = (over: Record<string, string>) => {
    const p = new URLSearchParams({ team, pos, sort, ...over });
    return `/surplus?${p}`;
  };

  return (
    <div className="space-y-4">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <h1 className="text-lg font-semibold text-text-primary">
        Contract value board{" "}
        <span className="text-text-dim font-normal">
          · {seasonLabel(prodSeason)} production vs {seasonLabel(surDoc?.season_salary ?? prodSeason + 1)} cap hit
        </span>
      </h1>

      {/* extremes strip */}
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
          <div className="text-text-dim text-[10px] mb-1.5">Best bargains · production percentile far above cap-hit percentile</div>
          {best.map((r) => (
            <div key={r.id} className="flex justify-between py-0.5 tabular-nums">
              <Link href={`/players/${r.id}`} className="hover:text-text-secondary">{r.name}</Link>
              <span className={surClass(r.surplus)}>{surFmt(r.surplus)} · {money(r.sal)}</span>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
          <div className="text-text-dim text-[10px] mb-1.5">Heaviest deals · production percentile far below cap-hit percentile</div>
          {worst.map((r) => (
            <div key={r.id} className="flex justify-between py-0.5 tabular-nums">
              <Link href={`/players/${r.id}`} className="hover:text-text-secondary">{r.name}</Link>
              <span className={surClass(r.surplus)}>{surFmt(r.surplus)} · {money(r.sal)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* filters */}
      <form action="/surplus" method="get" className="flex flex-wrap items-center gap-2 text-xs">
        <select name="team" defaultValue={team} aria-label="Team" className="bg-transparent border border-border-subtle rounded px-1.5 py-0.5">
          <option value="ALL">All teams</option>
          {teams.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select name="pos" defaultValue={pos} aria-label="Position" className="bg-transparent border border-border-subtle rounded px-1.5 py-0.5">
          <option value="ALL">All positions</option>
          {poss.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select name="sort" defaultValue={sort} aria-label="Sort" className="bg-transparent border border-border-subtle rounded px-1.5 py-0.5">
          <option value="surplus">Sort: surplus</option>
          <option value="prod">Sort: production pctile</option>
          <option value="sal">Sort: cap hit</option>
          <option value="name">Sort: name</option>
        </select>
        <button className="rounded px-2 py-0.5 border border-border-subtle hover:bg-white/[0.06]">Go</button>
        <span className="text-text-dim text-[11px]">{sorted.length} players under contract</span>
      </form>

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs overflow-x-auto">
        <table className="w-full text-[11px] tabular-nums min-w-[620px]">
          <thead>
            <tr className="text-text-dim text-left">
              <th className="font-normal pr-2">#</th><th className="font-normal pr-2">Player</th>
              <th className="font-normal pr-2">Team</th><th className="font-normal pr-2">Pos</th>
              <th className="font-normal pr-2">GP</th>
              <th className="font-normal pr-2">Prod pctile</th>
              <th className="font-normal pr-2">Cap-hit pctile</th>
              <th className="font-normal pr-2">Surplus <span className="text-text-dim/60">({SUR_HDR})</span></th>
              <th className="font-normal">Cap hit</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={r.id} className="border-t border-border-subtle/50">
                <td className="pr-2 text-text-dim">{i + 1}</td>
                <td className="pr-2"><Link href={`/players/${r.id}`} className="hover:text-text-secondary">{r.name}</Link></td>
                <td className="pr-2 text-text-secondary">{r.team ?? "—"}</td>
                <td className="pr-2 text-text-dim">{r.pos ?? "—"}</td>
                <td className={`pr-2 ${r.gp < 20 ? "text-flag" : "text-text-secondary"}`}
                  title={r.gp < 20 ? `only ${r.gp} games — production percentile is small-sample` : undefined}>{r.gp}</td>
                <td className="pr-2">{pct(r.prod_pct)}</td>
                <td className="pr-2">{pct(r.sal_pct)}</td>
                <td className={`pr-2 ${surClass(r.surplus)}`}>{surFmt(r.surplus)}</td>
                <td>{money(r.sal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-[10px] text-text-dim/70 mt-1.5">
          {surDoc?.note ?? "descriptive"} — internal research; green production percentile ≥ cap-hit percentile +15, red −15;
          violet GP = small-sample production. Not a valuation model.
        </div>
      </div>
    </div>
  );
}
