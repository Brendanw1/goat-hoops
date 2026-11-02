import Link from "next/link";
import { notFound } from "next/navigation";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsContracts, getHoopsPlayer } from "@/lib/data-hoops";
import type { HoopsContractDeal } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const money = (v: number | null | undefined) => {
  if (v == null) return "—";
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${v}`;
};

const dealSpan = (d: HoopsContractDeal) =>
  d.start != null && d.end != null ? `${d.start}-${String(d.end).slice(2)}` :
  d.start != null ? `${d.start}-` : "—";

/** One player: contract panel, per-season lines (per game + per 36), game log. */
export default async function HoopsPlayerPage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [doc, cdoc] = [await getHoopsPlayer(id), await getHoopsContracts()];
  if (!doc || !Object.keys(doc.seasons).length) notFound();
  const seasons = Object.keys(doc.seasons).sort((a, b) => Number(b) - Number(a));
  const latest = doc.seasons[seasons[0]];
  const deals = cdoc?.deals[id] ?? [];
  const salary = cdoc?.salaries[id];
  const current = deals.find((d) => d.status === "CURRENT") ?? deals[0];
  const prior = current ? deals.filter((d) => d !== current) : deals;

  return (
    <div className="space-y-5">
      <BackLink fallback="/players" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div>
        <h1 className="text-lg font-semibold text-text-primary">{doc.name}</h1>
        <p className="text-xs text-text-dim">
          {[...new Set(seasons.map((s) => doc.seasons[s].team).filter(Boolean))].join(" · ")}
        </p>
      </div>

      {(current || salary) && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-3xl text-xs space-y-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
            <h2 className="text-sm font-medium text-text-primary">Contract</h2>
            {salary && (
              <span className="text-text-secondary tabular-nums">
                {salary.season ? `${salary.season - 1}-${String(salary.season).slice(2)} · ` : ""}
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

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 max-w-3xl">
        {seasons.map((s) => {
          const r = doc.seasons[s];
          return (
            <div key={s} className="rounded-lg border border-border-subtle px-3 py-2 text-xs">
              <div className="text-text-primary font-medium mb-1">
                {Number(s) - 1}-{String(s).slice(2)} · {r.team ?? "—"} · {r.gp} GP ({r.gs} GS)
              </div>
              <div className="text-text-secondary tabular-nums">
                {r.per_game.pts} pts · {r.per_game.reb} reb · {r.per_game.ast} ast ·
                {" "}{r.per_game.stl} stl · {r.per_game.blk} blk · {r.per_game.tov} tov ·
                {" "}{r.per_game.min} min
              </div>
              <div className="text-text-dim tabular-nums mt-0.5">
                per 36: {r.per36.pts ?? "—"} / {r.per36.reb ?? "—"} / {r.per36.ast ?? "—"}
              </div>
            </div>
          );
        })}
      </div>

      {seasons.map((s) => {
        const r = doc.seasons[s];
        return (
          <div key={s} className="space-y-1">
            <h2 className="text-sm font-medium text-text-primary">
              {Number(s) - 1}-{String(s).slice(2)} game log
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
                {[...r.games].reverse().map((g) => (
                  <tr key={g.id} className="border-t border-border-subtle/50 hover:bg-white/[0.03]">
                    <td className="pr-2">
                      <Link href={`/games/${g.id}`} className="text-text-primary hover:underline tabular-nums">
                        {g.date}
                      </Link>
                    </td>
                    <td>{g.home ? "vs" : "@"} {g.opp}</td>
                    <td className={g.res === "W" ? "text-usf-green" : "text-[#e0654f]"}>{g.res}</td>
                    <td>{g.min ?? "—"}</td><td className="font-medium">{g.pts}</td>
                    <td>{g.reb}</td><td>{g.ast}</td><td>{g.stl}</td><td>{g.blk}</td>
                    <td>{g.tov}</td><td>{g.pf}</td>
                    <td>{g.fg}</td><td>{g.tp}</td><td>{g.ft}</td>
                    <td className={g.pm != null && g.pm > 0 ? "text-usf-green" : g.pm != null && g.pm < 0 ? "text-[#e0654f]" : ""}>
                      {g.pm ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
