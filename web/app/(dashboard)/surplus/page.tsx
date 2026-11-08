import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsContracts, getHoopsPlayers, getHoopsProjections, getHoopsSeasAvgs, getHoopsSimilar, getHoopsSurplus } from "@/lib/data-hoops";
import { TeamDot } from "@/lib/team-dot";
import { pctTone } from "@/lib/tone";

export const revalidate = 300; // prod: 5-min route cache; dev renders per request

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
  const [surDoc, board, ss26, contracts, projDoc, similar] = await Promise.all([
    getHoopsSurplus(), getHoopsPlayers(), getHoopsSeasAvgs(2026), getHoopsContracts(),
    getHoopsProjections(), getHoopsSimilar()]);
  const ageOf = new Map<string, number>();
  for (const [eid, p] of Object.entries(ss26?.players ?? {})) {
    const a = (p.adv as unknown as { age?: number } | undefined)?.age;
    if (typeof a === "number") ageOf.set(eid, a);
  }
  const proj = projDoc?.players ?? {};
  const dealOf = new Map(Object.entries(contracts?.deals ?? {}).map(([eid, d]) => [eid, d]));
  const salOf = new Map(Object.entries(contracts?.salaries ?? {}).map(([eid, s]) => [eid, s]));
  const compOf = new Map<string, string>();
  for (const [eid, p] of Object.entries(similar?.players ?? {})) {
    const t = p.n?.[0];
    if (t?.[2]) compOf.set(eid, t[2]);
  }
  // the trade-value composite — weights printed with the table (transparent,
  // debatable, no black box): production percentile, aged toward the 26 peak
  const AGE_PEAK = 26;
  const tvOf = (eid: string) => {
    const prod = sur[eid]?.prod_pct;
    const age = ageOf.get(eid);
    if (prod == null || age == null) return null;
    return Math.round(prod * 100 - 2 * Math.max(0, age - AGE_PEAK) - 1 * Math.max(0, 24 - age));
  };
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

  const byName = (n: string) => rows.find((r) => r.name === n)?.id;
  const defPicks = [byName("Shai Gilgeous-Alexander"), byName("Victor Wembanyama"),
                    byName("Cooper Flagg")].filter((x): x is string => !!x);
  const picks = [sp.a ?? defPicks[0], sp.b ?? defPicks[1], sp.c ?? defPicks[2]]
    .filter((x): x is string => !!x && x in sur);
  const pickCard = (eid: string) => {
    const row = rows.find((r) => r.id === eid);
    const p = board?.seasons[String(prodSeason)]?.find((r) => r.id === eid);
    const deal = (dealOf.get(eid) ?? []).find((d) => d.status === "CURRENT") ?? (dealOf.get(eid) ?? [])[0];
    const pr = proj[eid];
    const age = ageOf.get(eid);
    const tv = tvOf(eid);
    return (
      <div key={eid} className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs min-w-0">
        <div className="flex items-center gap-1.5 mb-1">
          {p?.team && <TeamDot abbr={p.team} size={18} />}
          <Link href={`/players/${eid}`} className="text-sm font-medium text-text-primary hover:underline truncate">
            {row?.name ?? eid}
          </Link>
        </div>
        <div className="space-y-0.5 tabular-nums text-text-secondary">
          <p>age <span className="text-text-primary font-medium">{age ?? "—"}</span>
            {age != null && <span className="text-text-dim"> (peak 24-27)</span>}</p>
          <p>prod pctile <span className={`font-medium ${pctTone((sur[eid]?.prod_pct ?? 0) / 100)}`}>
            {pct(sur[eid]?.prod_pct)}</span> · cap pctile {pct(sur[eid]?.sal_pct)}</p>
          <p>surplus <span className={surClass(sur[eid]?.surplus)}>{surFmt(sur[eid]?.surplus)}</span> {SUR_HDR}</p>
          <p>per-game <span className="text-text-primary font-medium">
            {p ? `${(p.pts ?? 0).toFixed(1)}/${(p.reb ?? 0).toFixed(1)}/${(p.ast ?? 0).toFixed(1)}` : "—"}</span></p>
          <p>2027 proj <span className="text-text-primary font-medium">
            {pr ? `${pr.pts36} pts36 · ${pr.mpg} mpg` : "at the modeling floor"}</span>
            {pr?.lo && pr.pts36 != null && pr.lo.pts36 != null && (
              <span className="text-text-dim"> (90% {pr.lo.pts36}–{pr.hi?.pts36})</span>)}</p>
          <p>contract <span className="text-text-primary font-medium">
            {salOf.get(eid)?.cap_hit ? money(salOf.get(eid)?.cap_hit) : "—"}</span>
            {deal?.years ? ` · ${deal.years}y` : ""}
            {deal?.fa_year ? ` · FA ${deal.fa_year}` : ""}</p>
          <p>top comp <span className="text-text-secondary">{compOf.get(eid) ?? "—"}</span></p>
          <p className="pt-0.5 border-t border-border-subtle/40">trade value
            <span className={`ml-1.5 text-base font-semibold ${tv != null && tv >= 60 ? "text-elite" : tv != null && tv <= 20 ? "text-neg" : "text-text-primary"}`}>
              {tv ?? "—"}</span>
            <span className="text-text-dim text-[10px]"> / 100</span></p>
        </div>
      </div>
    );
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

      {/* trade analysis */}
      <div className="rounded-lg border border-border-subtle px-3 py-2.5">
        <h2 className="text-sm font-medium text-text-primary mb-1.5">Trade analysis</h2>
        <form method="get" className="flex flex-wrap items-center gap-2 mb-2.5">
          {[["a", picks[0] ?? ""], ["b", picks[1] ?? ""], ["c", picks[2] ?? ""]].map(([nm, def]) => (
            <select key={nm} name={nm} defaultValue={def}
              className="rounded-md border border-border-subtle bg-surface-1 px-2 py-1.5 text-xs text-text-primary max-w-[220px]">
              {[...filtered].sort((x, y) => x.name.localeCompare(y.name)).map((r) => (
                <option key={r.id} value={r.id}>{r.name} ({r.team ?? "?"})</option>
              ))}
            </select>
          ))}
          <button type="submit"
            className="rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-secondary hover:text-text-primary">
            Compare
          </button>
        </form>
        {picks.length > 0 && (
          <div className="grid gap-2.5 md:grid-cols-3">{picks.map(pickCard)}</div>
        )}
        <p className="text-[10px] text-text-dim/70 mt-2">
          trade value = production percentile − 2·max(0, age−26) − 1·max(0, 24−age),
          printed so the weights are debatable — a ranking lens, not a market price.
          Contract burden is the surplus line (production percentile vs cap-hit
          percentile); the projection row is the §14 model.
        </p>
      </div>

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
