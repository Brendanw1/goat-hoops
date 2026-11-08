import Link from "next/link";
import { notFound } from "next/navigation";
import { BackLink } from "@/components/ui/back-link";
import {
  getHoopsContracts, getHoopsPlayers, getHoopsSurplus, getHoopsTeam, getHoopsTeams,
  type HoopsTeamAnalytics, type HoopsPlayerRow,
} from "@/lib/data-hoops";
import { teamColor } from "@/lib/team-colors";
import { TeamDot } from "@/lib/team-dot";
import { MarginStrip } from "@/components/ui/margin-strip";

export const revalidate = 300; // prod: 5-min route cache; dev renders per request

const money = (v: number | null | undefined) => {
  if (v == null) return "—";
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${Math.round((v ?? 0) / 1e3)}K`;
};
const seasonLabelOf = (s: number) => `${s - 1}-${String(s).slice(2)}`;
const surplusSeason = 2026; // the surplus doc's production season (2025-26)
const ord = (i: number) => `${i + 1}${["st", "nd", "rd"][i] ?? "th"}`;

/** rank chips reuse the standings convention: 1-6 green, 25-30 red */
const rankTone = (i: number) =>
  i < 6 ? "text-pos" : i >= 25 ? "text-neg" : "text-text-dim";

type MetricKey = keyof Pick<HoopsTeamAnalytics,
  "ortg" | "drtg" | "net" | "efg" | "tsp" | "tov_pct" | "orb_pct" | "drb_pct"
  | "opp_efg" | "opp_tsp" | "opp_tov_pct" | "fg3ar" | "ftr" | "pace">;

/** 1 = higher is better, -1 = lower is better, 0 = no rank (context only) */
const METRIC_DIR: Record<MetricKey, 1 | -1 | 0> = {
  ortg: 1, drtg: -1, net: 1, efg: 1, tsp: 1, tov_pct: -1, orb_pct: 1,
  drb_pct: 1, opp_efg: -1, opp_tsp: -1, opp_tov_pct: 1, fg3ar: 0, ftr: 0, pace: 0,
};

/** league rank of one team's metric among the clubs carrying analytics that season */
function rankOf(
  seasonRows: { abbr: string; analytics?: HoopsTeamAnalytics }[],
  abbr: string, key: MetricKey,
): number | null {
  const dir = METRIC_DIR[key];
  if (!dir) return null;
  const rows = seasonRows.filter(
    (r) => r.analytics && (r.analytics[key] as number | null) != null);
  if (rows.length < 2) return null;
  const sorted = [...rows].sort((x, y) => dir === 1
    ? (y.analytics![key] as number) - (x.analytics![key] as number)
    : (x.analytics![key] as number) - (y.analytics![key] as number));
  const i = sorted.findIndex((r) => r.abbr === abbr);
  return i < 0 ? null : i;
}

const fmtPct = (v: number | null | undefined) =>
  v == null ? "—" : `${(v * 100).toFixed(1)}%`;

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
        <span className="block h-1 w-20 rounded-full mb-2"
          style={{ background: teamColor(key) ?? "var(--color-border-subtle)" }} />
        <h1 className="text-lg font-semibold text-text-primary">
          {key} <span className="text-text-dim font-normal">{name}</span>
        </h1>
        <p className="text-xs text-text-dim">
          {seasons.slice().reverse().map((s) => `${Number(s) - 1}-${String(s).slice(2)}: ${doc.seasons[s].w}-${doc.seasons[s].l}`).join(" · ")}
        </p>
      </div>

      {withSurplus.length > 0 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
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

      {(() => {
        const season = seasons[0];
        const roster = (playersDoc?.seasons[String(season)] ?? [])
          .filter((r) => r.team === key)
          .sort((a, b) => (b.pts ?? 0) - (a.pts ?? 0));
        const salBy = new Map(Object.entries(contracts?.salaries ?? {})
          .filter(([, s]) => s.team === key)
          .map(([eid, s]) => [eid, s.cap_hit as number]));
        if (roster.length === 0) return null;
        return (
          <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl text-xs overflow-x-auto">
            <h2 className="text-sm font-medium text-text-primary mb-1.5">
              Roster <span className="text-text-dim font-normal text-[10px]">
                · {Number(season) - 1}-{String(season).slice(2)} · per game · tap a player for the full profile
              </span>
            </h2>
            <table className="w-full text-[11px] tabular-nums min-w-[620px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-text-dim border-b border-border-subtle">
                  <th className="text-left py-1.5 pr-2 font-medium">Player</th>
                  <th className="text-left px-2 font-medium">Pos</th>
                  <th className="text-right px-2 font-medium">GP</th>
                  <th className="text-right px-2 font-medium">MPG</th>
                  <th className="text-right px-2 font-medium">PTS</th>
                  <th className="text-right px-2 font-medium">REB</th>
                  <th className="text-right px-2 font-medium">AST</th>
                  <th className="text-right px-2 font-medium">FG%</th>
                  <th className="text-right px-2 font-medium">Cap hit</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((r: HoopsPlayerRow) => (
                  <tr key={r.id} className="border-b border-border-subtle/40 hover:bg-white/[0.03]">
                    <td className="py-1 pr-2">
                      <Link href={`/players/${r.id}`} className="inline-flex items-center gap-1.5 hover:underline">
                        <TeamDot abbr={key} size={16} />
                        <span className="text-text-primary">{r.name}</span>
                      </Link>
                    </td>
                    <td className="px-2 text-text-dim">{r.pos ?? "—"}</td>
                    <td className="text-right px-2 text-text-secondary">{r.gp}</td>
                    <td className="text-right px-2 text-text-secondary">{r.min.toFixed(1)}</td>
                    <td className="text-right px-2 text-text-primary font-medium">{r.pts.toFixed(1)}</td>
                    <td className="text-right px-2 text-text-secondary">{r.reb.toFixed(1)}</td>
                    <td className="text-right px-2 text-text-secondary">{r.ast.toFixed(1)}</td>
                    <td className="text-right px-2 text-text-secondary">{r.fgp != null ? `${Math.round(r.fgp * 100)}%` : "—"}</td>
                    <td className="text-right px-2 text-text-dim">
                      {salBy.get(r.id) != null ? money(salBy.get(r.id)) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[10px] text-text-dim/70 mt-1.5">
              balldontlie board rows · cap hit from the {seasonLabelOf(Number(season) + 1)} book —
              the roster value panel below weighs production against it
            </p>
          </div>
        );
      })()}

      {seasons.map((s) => {
        const agg = doc.seasons[s];
        return (
          <div key={s} className="space-y-2">
            <h2 className="text-sm font-medium text-text-primary">
              {Number(s) - 1}-{String(s).slice(2)} · {agg.w}-{agg.l} · {agg.pts} pts/g ·{" "}
              opp {agg.opp_pts} · REB {agg.reb} · AST {agg.ast} · TOV {agg.tov}
            </h2>
            {agg.games.length > 8 && (
              <div className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 max-w-5xl">
                <MarginStrip games={[...agg.games].reverse()} />
              </div>
            )}
            {agg.starters5?.length ? (
              <p className="text-[11px] text-text-dim max-w-5xl">
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
            {agg.analytics && (() => {
              const a = agg.analytics;
              const lg = board?.league?.[s];
              const seasonRows = board?.seasons[s] ?? [];
              const cell = (label: string, mk: MetricKey, text: string) => {
                const rk = rankOf(seasonRows, key, mk);
                return (
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-text-dim">{label}</span>
                    <span className="tabular-nums text-text-primary">
                      {text}
                      {rk != null && (
                        <span className={`ml-1.5 text-[10px] ${rankTone(rk)}`}>{ord(rk)}</span>
                      )}
                    </span>
                  </div>
                );
              };
              return (
                <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
                  <div className="flex items-baseline justify-between gap-2 mb-1.5">
                    <h3 className="text-sm font-medium text-text-primary">
                      Analytics
                      <span className="text-text-dim font-normal text-[10px]">
                        {" "}· {seasonLabelOf(Number(s))} · {a.src === "espn" ? "ESPN mart" : "balldontlie boxes"}
                      </span>
                    </h3>
                    {a.partial && (
                      <span className="text-[10px] text-flag">PARTIAL</span>
                    )}
                  </div>
                  <div className="tabular-nums mb-2">
                    <span className="text-text-secondary">net </span>
                    <span className={`font-medium ${a.net == null ? "text-text-dim" : a.net >= 0 ? "text-pos" : "text-neg"}`}>
                      {a.net != null ? `${a.net > 0 ? "+" : ""}${a.net.toFixed(1)}` : "—"}
                    </span>
                    <span className="text-text-dim">
                      {" "}· ORtg {a.ortg ?? "—"} · DRtg {a.drtg ?? "—"} · pace {a.pace.toFixed(1)}
                      {lg ? ` (lg ${lg.pace?.toFixed(1)})` : ""}
                    </span>
                  </div>
                  <div className="grid gap-x-6 gap-y-0.5 sm:grid-cols-2">
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-text-dim/70 uppercase tracking-wide">Offense</p>
                      {cell("eFG", "efg", fmtPct(a.efg))}
                      {cell("TS%", "tsp", fmtPct(a.tsp))}
                      {cell("3PA share", "fg3ar", fmtPct(a.fg3ar))}
                      {cell("FT rate", "ftr", fmtPct(a.ftr))}
                      {cell("TOV%", "tov_pct", fmtPct(a.tov_pct))}
                      {cell("ORB%", "orb_pct", fmtPct(a.orb_pct))}
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-text-dim/70 uppercase tracking-wide">Defense</p>
                      {cell("DRtg", "drtg", a.drtg != null ? a.drtg.toFixed(1) : "—")}
                      {cell("opp eFG", "opp_efg", fmtPct(a.opp_efg))}
                      {cell("opp TS%", "opp_tsp", fmtPct(a.opp_tsp))}
                      {cell("opp TOV%", "opp_tov_pct", fmtPct(a.opp_tov_pct))}
                      {cell("DRB%", "drb_pct", fmtPct(a.drb_pct))}
                    </div>
                  </div>
                  <div className="text-[10px] text-text-dim/70 mt-1.5">
                    §0d-gated team grain (BDL sums vs ESPN boxes: all columns ≥ 0.99/0.97 bars) —
                    descriptive; possessions two-sided; live season flagged PARTIAL
                  </div>
                </div>
              );
            })()}
            {agg.playtype && (() => {
              const pt = agg.playtype;
              const lg = board?.playtype_league?.[s] ?? {};
              const max = Math.max(...pt.mix.map((r) => r.share), 0.01);
              return (
                <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-5xl">
                  <h3 className="text-sm font-medium text-text-primary mb-1.5">
                    Play-type mix
                    <span className="text-text-dim font-normal text-[10px]">
                      {" "}· {seasonLabelOf(Number(s))} · share of player-tracked possessions
                    </span>
                  </h3>
                  <div className="space-y-1">
                    {pt.mix.map((r) => {
                      const l = lg[r.cat];
                      return (
                        <div key={r.cat} className="flex items-center gap-2">
                          <span className="w-28 shrink-0 text-text-dim">{r.cat}</span>
                          <div className="h-2.5 flex-1 rounded-sm bg-white/[0.05] overflow-hidden">
                            <div className="h-full rounded-sm bg-white/30" style={{ width: `${(r.share / max) * 100}%` }} />
                          </div>
                          <span className="w-10 text-right tabular-nums text-text-secondary">
                            {(r.share * 100).toFixed(0)}%
                          </span>
                          <span className="w-24 text-right tabular-nums text-text-dim">
                            {r.ppp.toFixed(2)}
                            {l ? ` lg ${l.ppp.toFixed(2)}` : ""}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="text-[10px] text-text-dim/70 mt-1.5">
                    possession-weighted roll-up of player play-type rows — a close
                    proxy, not a possession-true team dashboard
                  </div>
                </div>
              );
            })()}
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
