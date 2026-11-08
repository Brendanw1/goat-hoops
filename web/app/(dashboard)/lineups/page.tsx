import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsLineups, type HoopsOnOffRow, type HoopsUnitRow } from "@/lib/data-hoops";

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
              <td className="text-right px-2">{u.ortg.toFixed(1)}</td>
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

function OnOffCard({ title, rows, tone }: {
  title: string; rows: HoopsOnOffRow[]; tone: "pos" | "neg";
}) {
  return (
    <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs min-w-0">
      <h3 className="text-sm font-medium text-text-primary mb-1.5">{title}</h3>
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.pid} className="flex items-baseline justify-between gap-2">
            <span className="text-text-secondary truncate">
              <Link href={`/players/${r.pid}`} className="hover:underline">{r.name}</Link>
              <span className="text-text-dim/70 ml-1.5 text-[10px] tabular-nums">
                on {r.on_net > 0 ? "+" : ""}{r.on_net.toFixed(1)} / off {r.off_net > 0 ? "+" : ""}{r.off_net.toFixed(1)}
              </span>
            </span>
            <span className={`tabular-nums font-medium shrink-0 ${tone === "pos" ? "text-pos" : "text-neg"}`}>
              {r.diff > 0 ? "+" : ""}{r.diff.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Five-man units + on/off from the §0f-gated stint walk (descriptive, PARTIAL). */
export default async function HoopsLineupsPage({
  searchParams,
}: {
  searchParams: Promise<{ team?: string }>;
}) {
  const doc = await getHoopsLineups();
  if (!doc || !Object.keys(doc.seasons).length) {
    return <p className="text-sm text-text-dim">Lineups doc not baked yet.</p>;
  }
  const { team } = await searchParams;
  const seasonKey = Object.keys(doc.seasons).sort((a, b) => Number(b) - Number(a))[0];
  const season = doc.seasons[seasonKey];
  const teamKeys = Object.keys(season.teams).sort();
  const abbr = team && season.teams[team.toUpperCase()] ? team.toUpperCase() : "OKC";
  const data = season.teams[abbr];
  const cov = season.coverage;

  const hero = data.units[0];
  const best = [...data.units].sort((a, b) => (b.net ?? -99) - (a.net ?? -99))[0];
  const onoff = [...data.onoff].sort((a, b) => b.diff - a.diff);
  const upside = onoff.slice(0, 6);
  const downside = onoff.slice(-6).reverse();

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
            possession-stint walk ({cov.games} of {cov.of} games,{" "}
            <span className="text-flag">PARTIAL</span>). Minutes are
            possession-proportional estimates (§0f); ratings are possession-exact.
          </p>
        </div>
        <form method="get" className="flex items-center gap-2">
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
                {" "}ORtg {hero.ortg.toFixed(1)} · DRtg {hero.drtg?.toFixed(1)}
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
          Units <span className="text-text-dim font-normal text-[10px]">· ≥ 100 possessions · sorted by minutes</span>
        </h2>
        <UnitTable units={data.units} />
      </section>

      <section className="space-y-2 max-w-5xl">
        <h2 className="text-sm font-medium text-text-primary">
          On/off <span className="text-text-dim font-normal text-[10px]">· ≥ 1,500 on-court poss · net differential vs floor time without him</span>
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          <OnOffCard title="Rises with him" rows={upside} tone="pos" />
          <OnOffCard title="Sinks with him" rows={downside} tone="neg" />
        </div>
      </section>

      <p className="text-[10px] text-text-dim/70 max-w-5xl">
        §0f-gated stint walk over ESPN PBP (score reconciliation {doc.gate_0f.score_exact != null ? `${(doc.gate_0f.score_exact * 100).toFixed(1)}%` : "—"}
        exact vs finals; skipped {cov.of - cov.games} index-mismatched games).
        *Minutes estimated by possession share — real clock minutes land with the
        interval-lineage rerun (§0f read). Descriptive only: lineup net ratings are
        small-sample, roster-mix confounded, and are not impact ratings.
      </p>
    </div>
  );
}
