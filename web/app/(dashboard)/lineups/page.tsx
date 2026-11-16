import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { OnOffBars } from "@/components/ui/onoff-bars";
import { getHoopsLineups, type HoopsUnitRow } from "@/lib/data-hoops";

export const revalidate = 300; // prod: 5-min route cache; dev renders per request

const seasonLabelOf = (s: number) => `${s - 1}-${String(s).slice(2)}`;

const NET_TONE = (v: number | null) =>
  v == null ? "text-text-dim" : v >= 5 ? "text-pos font-medium"
    : v <= -5 ? "text-neg font-medium" : "text-text-secondary";

/** diverging net bar: zero-centered, pos green / neg red, ±20 clips */
function NetBar({ v }: { v: number | null }) {
  if (v == null) return <span className="text-text-dim">—</span>;
  const w = Math.min(Math.abs(v) / 20, 1) * 50;
  return (
    <div className="relative h-2 w-28 rounded-sm bg-white/[0.05]">
      <div className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
      <div className={`absolute inset-y-0 rounded-sm ${v >= 0 ? "bg-pos/70 left-1/2" : "bg-neg/70 right-1/2"}`}
        style={{ width: `${w}%` }} />
    </div>
  );
}

function UnitTable({ units }: { units: HoopsUnitRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-text-dim border-b border-border-subtle">
            <th className="text-left py-1.5 pr-3 font-medium">Unit</th>
            <th className="text-right px-2 font-medium">Min*</th>
            <th className="text-right px-2 font-medium">Poss</th>
            <th className="text-right px-2 font-medium">GP</th>
            <th className="text-right px-2 font-medium">ORtg</th>
            <th className="text-right px-2 font-medium">DRtg</th>
            <th className="text-right px-2 font-medium">Net</th>
            <th className="py-1.5 pl-3 font-medium text-left w-28"> </th>
          </tr>
        </thead>
        <tbody>
          {units.map((u) => (
            <tr key={u.ids.join()} className="border-b border-border-subtle/40">
              <td className="py-1.5 pr-3 text-text-secondary">
                {u.names.map((n) => n.split(" ").slice(-1)[0]).join(" · ")}
              </td>
              <td className="text-right px-2">{u.min.toFixed(0)}</td>
              <td className="text-right px-2">{u.poss.toLocaleString()}</td>
              <td className="text-right px-2">{u.gp}</td>
              <td className="text-right px-2">{u.ortg?.toFixed(1) ?? "—"}</td>
              <td className="text-right px-2">{u.drtg?.toFixed(1) ?? "—"}</td>
              <td className={`text-right px-2 ${NET_TONE(u.net)}`}>
                {u.net != null ? `${u.net > 0 ? "+" : ""}${u.net.toFixed(1)}` : "—"}
              </td>
              <td className="py-1.5 pl-3"><NetBar v={u.net} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Five-man units + on/off from the §0f-gated stint walk (descriptive, PARTIAL). */
export default async function HoopsLineupsPage({
  searchParams,
}: {
  searchParams: Promise<{ team?: string; season?: string }>;
}) {
  const doc = await getHoopsLineups();
  if (!doc || !Object.keys(doc.seasons).length) {
    return <p className="text-sm text-text-dim">Lineups doc not baked yet.</p>;
  }
  const { team, season: seasonParam } = await searchParams;
  const seasonKeys = Object.keys(doc.seasons).sort((a, b) => Number(b) - Number(a));
  const seasonKey = seasonParam && doc.seasons[seasonParam] ? seasonParam : seasonKeys[0];
  const season = doc.seasons[seasonKey];
  const live = seasonKey === seasonKeys[0] && season.coverage.partial && seasonKeys.length > 1;
  const teamKeys = Object.keys(season.teams).sort();
  // the live season only lists teams with a qualifying unit yet — fall back
  // gracefully when a ?team= carried over from the other season isn't here:
  // OKC if present, else the team whose top unit has logged the most together
  const want = team?.toUpperCase();
  const deepest = [...teamKeys].sort((x, y) =>
    (season.teams[y].units[0]?.poss ?? 0) - (season.teams[x].units[0]?.poss ?? 0))[0];
  const abbr = want && season.teams[want] ? want : season.teams.OKC ? "OKC" : deepest;
  const data = season.teams[abbr] ?? { units: [], onoff: [] };
  const cov = season.coverage;
  const gate = season.gate_0f ?? doc.gate_0f;
  const fullKey = seasonKeys.find((k) => !doc.seasons[k].coverage.partial
    || doc.seasons[k].coverage.games >= 1000);

  const hero = data.units[0];
  const best = [...data.units].sort((a, b) => (b.net ?? -99) - (a.net ?? -99))[0];
  const onoff = data.onoff;
  const early = !!cov.early;
  const fl = cov.floors ?? { onoff_on: 1500, onoff_off: 500, unit_rated: 100, units_per_team: null };

  return (
    <div className="space-y-5">
      <BackLink fallback="/teams" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">
            Lineups <span className="text-text-dim font-normal">{abbr}</span>
          </h1>
          <p className="text-xs text-text-dim max-w-2xl">
            {seasonLabelOf(Number(seasonKey))} · five-man units and on/off from the
            possession-stint walk (
            {live ? <>live · {cov.games} games in</> : <>{cov.games.toLocaleString()} of {cov.of.toLocaleString()} games</>},{" "}
            <span className="text-flag">PARTIAL</span>). Minutes are
            possession-proportional estimates (§0f); ratings are possession-exact.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <nav aria-label="season" className="flex rounded-md border border-border-subtle overflow-hidden text-xs">
            {seasonKeys.map((k) => {
              const on = k === seasonKey;
              const isLive = k === seasonKeys[0] && doc.seasons[k].coverage.partial && seasonKeys.length > 1;
              return (
                <Link key={k} href={`/lineups?season=${k}&team=${abbr}`}
                  aria-current={on ? "page" : undefined}
                  className={`px-2.5 py-1.5 ${on ? "bg-surface-1 text-text-primary font-medium"
                    : "text-text-dim hover:text-text-secondary"}`}>
                  {seasonLabelOf(Number(k))}{isLive && <span className="ml-1 text-flag">live</span>}
                </Link>
              );
            })}
          </nav>
          <form method="get" className="flex items-center gap-2">
            <input type="hidden" name="season" value={seasonKey} />
            <select name="team" defaultValue={abbr}
              className="rounded-md border border-border-subtle bg-surface-1 px-2 py-1.5 text-xs text-text-primary">
              {teamKeys.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <button type="submit"
              className="rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-secondary hover:text-text-primary">
              Go
            </button>
          </form>
        </div>
      </div>
      {live && (
        <p className="text-[11px] text-text-dim max-w-5xl -mt-2">
          {early ? (
            <>Early season: each team&apos;s {fl.units_per_team} most-used units are listed at any
              sample (ratings from {fl.unit_rated} possessions together), and on/off starts at{" "}
              {fl.onoff_on.toLocaleString()} on-court possessions with a 90% range. At this sample a
              swing of ±15 is within noise; the full floors (1,500) return when the season is
              further along.</>
          ) : (
            <>Early-season window: a unit appears at 100 possessions together and on/off at
              1,500 on-court possessions. {teamKeys.length} of 30 teams have a qualifying unit so far.</>
          )}
          {fullKey && fullKey !== seasonKey && (
            <> The full table is in{" "}
              <Link href={`/lineups?season=${fullKey}&team=${abbr}`} className="underline hover:text-text-secondary">
                {seasonLabelOf(Number(fullKey))}
              </Link>.</>
          )}
        </p>
      )}

      {hero && (
        <div className="rounded-xl border border-border-subtle bg-surface-1 px-4 py-3.5 max-w-5xl">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-text-dim/70">
                The default five · by minutes
              </p>
              <p className="text-base font-medium text-text-primary mt-0.5">
                {hero.names.join(" · ")}
              </p>
              <p className="text-[11px] text-text-dim tabular-nums mt-0.5">
                {hero.min.toFixed(0)} est min · {hero.poss.toLocaleString()} poss · {hero.gp} games ·
                {hero.ortg != null && <>{" "}ORtg {hero.ortg.toFixed(1)} · DRtg {hero.drtg?.toFixed(1)}</>}
              </p>
            </div>
            <div className="text-right">
              <p className={`text-3xl font-semibold tabular-nums ${NET_TONE(hero.net)}`}>
                {hero.net != null ? `${hero.net > 0 ? "+" : ""}${hero.net.toFixed(1)}` : "—"}
              </p>
              <p className="text-[10px] text-text-dim">net per 100 poss</p>
            </div>
          </div>
          {best && best.ids !== hero.ids && best.net != null && hero.net != null && (
            <p className="text-[11px] text-text-dim mt-2 pt-2 border-t border-border-subtle/40">
              Best by net:{" "}
              <span className="text-text-secondary">
                {best.names.map((n) => n.split(" ").slice(-1)[0]).join(" · ")}
              </span>{" "}
              <span className={NET_TONE(best.net)}>
                {best.net > 0 ? "+" : ""}{best.net.toFixed(1)}
              </span>{" "}
              over {best.poss.toLocaleString()} poss
            </p>
          )}
        </div>
      )}

      <section className="space-y-2 max-w-5xl">
        <h2 className="text-sm font-medium text-text-primary">
          Units <span className="text-text-dim font-normal text-[10px]">
            {early ? `· ${fl.units_per_team} most-used · ratings from ${fl.unit_rated} possessions · sorted by minutes`
              : "· ≥ 100 possessions · sorted by minutes"}</span>
        </h2>
        {data.units.length ? <UnitTable units={data.units} /> : (
          <p className="text-xs text-text-dim">No {abbr} unit has reached 100 possessions together yet.</p>
        )}
      </section>

      <section className="space-y-2 max-w-5xl">
        <h2 className="text-sm font-medium text-text-primary">
          On/off <span className="text-text-dim font-normal text-[10px]">
            · ≥ {fl.onoff_on.toLocaleString()} on-court poss · net differential vs floor time without him
            {early ? " · whiskers: 90% range · ordered by possessions" : ""}</span>
        </h2>
        {onoff.length ? (
          <OnOffBars rows={onoff} abbr={abbr} early={early} />
        ) : (
          <p className="text-xs text-text-dim">
            No {abbr} player has {fl.onoff_on.toLocaleString()} on-court possessions yet — the floor keeps
            small-sample on/off swings off the page.
          </p>
        )}
      </section>

      <p className="text-[10px] text-text-dim/70 max-w-5xl">
        §0f-gated stint walk over ESPN PBP — {gate.verdict} for {seasonLabelOf(Number(seasonKey))}
        {gate.score_exact != null && (
          <> (stint points reconcile to finals on {(gate.score_exact * 100).toFixed(1)}% of game-sides
            {gate.skipped_index_mismatch != null && <>; {gate.skipped_index_mismatch} index-mismatched games skipped</>})</>
        )}.
        *Minutes estimated by possession share — real clock minutes land with the
        interval-lineage rerun (§0f read). Descriptive only: lineup net ratings are
        small-sample, roster-mix confounded, and are not impact ratings.
      </p>
    </div>
  );
}
