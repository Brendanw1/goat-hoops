import Link from "next/link";
import { notFound } from "next/navigation";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsContracts, getHoopsPlayers, getHoopsSurplus, getHoopsTeam, getHoopsTeams } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const money = (v: number | null | undefined) => {
  if (v == null) return "—";
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${Math.round((v ?? 0) / 1e3)}K`;
};
const seasonLabelOf = (s: number) => `${s - 1}-${String(s).slice(2)}`;
const surplusSeason = 2026; // the surplus doc's production season (2025-26)

/** One club: season aggregates and the game list (each row links its report). */
export default async function HoopsTeamPage({ params }: {
  params: Promise<{ abbr: string }>;
}) {
  const { abbr } = await params;
  const key = abbr.toUpperCase();
  const doc = await getHoopsTeam(key);
  if (!doc || !Object.keys(doc.seasons).length) notFound();
  const seasons = Object.keys(doc.seasons).sort((a, b) => Number(b) - Number(a));
  const latest = doc.seasons[seasons[0]];

  // franchise name from the teams board (the team file carries it too, but the
  // board is already in hand server-side and covers every baked season)
  const [board, playersDoc, surplusDoc, contracts] = await Promise.all([
    getHoopsTeams(), getHoopsPlayers(), getHoopsSurplus(), getHoopsContracts()]);
  const name = board?.seasons[seasons[0]]?.find((t) => t.abbr === key)?.name ?? key;
  const names = new Map<string, string>();
  for (const rows of Object.values(playersDoc?.seasons ?? {})) {
    for (const r of rows) names.set(r.id, r.name);
  }
  // roster value (descriptive): salaries by team, joined to the surplus doc
  const roster = Object.entries(contracts?.salaries ?? {})
    .filter(([, s]) => s.team === key && (s.cap_hit ?? 0) > 0)
    .map(([eid, s]) => ({
      eid, name: names.get(eid) ?? eid, sal: s.cap_hit ?? 0,
      surplus: surplusDoc?.players[eid]?.surplus ?? null,
    }));
  const withSurplus = roster.filter((r) => r.surplus != null);
  const totSal = roster.reduce((a, r) => a + r.sal, 0);
  const wAvg = withSurplus.length
    ? withSurplus.reduce((a, r) => a + r.sal * (r.surplus as number), 0) / withSurplus.reduce((a, r) => a + r.sal, 0)
    : null;
  const best = [...withSurplus].filter((r) => r.sal >= 2e6)
    .sort((x, y) => (y.surplus as number) - (x.surplus as number)).slice(0, 3);
  const worst = [...withSurplus].filter((r) => r.sal >= 2e6)
    .sort((x, y) => (x.surplus as number) - (y.surplus as number))[0];

  return (
    <div className="space-y-5">
      <BackLink fallback="/teams" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div>
        <h1 className="text-lg font-semibold text-text-primary">
          {key} <span className="text-text-dim font-normal">{name}</span>
        </h1>
        <p className="text-xs text-text-dim">
          {seasons.map((s) => doc.seasons[s]).map((s) => `${s.w}-${s.l}`).join(" · ")} across{" "}
          {seasons.length} baked season{seasons.length > 1 ? "s" : ""} (latest: {latest.w}-{latest.l})
        </p>
      </div>

      {withSurplus.length > 0 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-3xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Roster value <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabelOf(surplusSeason)} production vs {seasonLabelOf(surplusSeason + 1)} cap hit · descriptive
            </span>
          </h2>
          <div className="text-text-secondary tabular-nums mb-1.5">
            {roster.length} salaried players · {money(totSal)} cap hit ·{" "}
            cap-weighted surplus{" "}
            <span className={wAvg != null && wAvg >= 0.05 ? "text-pos font-medium" : wAvg != null && wAvg <= -0.05 ? "text-neg font-medium" : "text-text-primary"}>
              {wAvg != null ? `${wAvg >= 0 ? "+" : ""}${(wAvg * 100).toFixed(0)} pct pts` : "—"}
            </span>
          </div>
          <div className="space-y-0.5">
            {best.map((r) => (
              <div key={r.eid} className="text-[11px] text-text-secondary">
                <span className="text-pos font-medium">+{((r.surplus as number) * 100).toFixed(0)}</span>{" "}
                <Link href={`/players/${r.eid}`} className="hover:underline">{r.name}</Link>{" "}
                <span className="text-text-dim tabular-nums">{money(r.sal)}</span>
              </div>
            ))}
            {worst && (
              <div className="text-[11px] text-text-secondary pt-0.5 border-t border-border-subtle/40">
                <span className="text-neg font-medium">{(worst.surplus as number) * 100 >= 0 ? "+" : ""}{((worst.surplus as number) * 100).toFixed(0)}</span>{" "}
                <Link href={`/players/${worst.eid}`} className="hover:underline">{worst.name}</Link>{" "}
                <span className="text-text-dim tabular-nums">{money(worst.sal)}</span>
              </div>
            )}
          </div>
          <div className="text-[10px] text-text-dim/70 mt-1.5">
            RESULTS-HOOPS §-style descriptive lens — production percentile vs cap-hit
            percentile, one season offset; not a valuation model
          </div>
        </div>
      )}

      {seasons.map((s) => {
        const agg = doc.seasons[s];
        return (
          <div key={s} className="space-y-2">
            <h2 className="text-sm font-medium text-text-primary">
              {Number(s) - 1}-{String(s).slice(2)} · {agg.w}-{agg.l} · {agg.pts} pts/g ·{" "}
              opp {agg.opp_pts} · REB {agg.reb} · AST {agg.ast} · TOV {agg.tov}
            </h2>
            {agg.starters5?.length ? (
              <p className="text-[11px] text-text-dim max-w-3xl">
                Most-used starting fives:{" "}
                {agg.starters5.map((u) => (
                  <span key={u.names.join()} className="text-text-secondary">
                    {u.names.join(" / ")}{" "}
                    <span className="tabular-nums">({u.g}g)</span>{" · "}
                  </span>
                ))}
                <span className="text-text-dim/70"> balldontlie starters pull — partial season</span>
              </p>
            ) : null}
            <div className="grid gap-1.5 sm:grid-cols-2">
              {agg.games.map((g) =>
                g.ext ? (
                  <div key={g.id}
                    className="flex items-center justify-between rounded-lg border border-border-subtle px-3 py-1.5 text-xs opacity-80">
                    <span className="text-text-secondary">
                      <span className={g.res === "W" ? "text-pos font-medium" : "text-neg"}>
                        {g.res}
                      </span>{" "}
                      {g.home ? `vs ${g.opp}` : `@ ${g.opp}`} {g.pts}–{g.opp_pts}
                    </span>
                    <span className="text-text-dim tabular-nums">{g.date}</span>
                  </div>
                ) : (
                  <Link key={g.id} href={`/games/${g.id}`}
                    className="flex items-center justify-between rounded-lg border border-border-subtle px-3 py-1.5 text-xs hover:bg-white/[0.04]">
                    <span className="text-text-primary">
                      <span className={g.res === "W" ? "text-pos font-medium" : "text-neg"}>
                        {g.res}
                      </span>{" "}
                      {g.home ? `vs ${g.opp}` : `@ ${g.opp}`} {g.pts}–{g.opp_pts}
                    </span>
                    <span className="text-text-dim tabular-nums">{g.date}</span>
                  </Link>
                ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
