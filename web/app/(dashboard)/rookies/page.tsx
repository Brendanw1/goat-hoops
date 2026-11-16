import Link from "next/link";
import {
  getHoopsDraft, getHoopsPlayers, getHoopsRates, getHoopsRookieRace, getHoopsSimilar,
} from "@/lib/data-hoops";
import { TeamDot } from "@/lib/team-dot";
import { teamColor } from "@/lib/team-colors";
import { RookieRace } from "@/components/ui/rookie-race";
import { RookieScatter } from "@/components/ui/rookie-scatter";

export const metadata = { title: "Rookies & draft classes" };
export const revalidate = 300;

const seasonLabel = (s: number | string) => `${Number(s) - 1}-${String(s).slice(2)}`;
const pickOf = (dn?: number, dr?: number) => (dn ? `#${dn}` : dr ? `Rd ${dr}` : "UDFA");
const ord = (n: number) => `${n}${[11, 12, 13].includes(n % 100) ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;

const SORTS = {
  gs: "Game Score (season total)", pts: "Points per game", bpm: "Regressed BPM", min: "Minutes",
} as const;
type SortKey = keyof typeof SORTS;

/** One rookie class: the race (weekly rank by cumulative Game Score), production
 *  vs playing time, and the class standings. Rookies = the summer's draftees
 *  (BDL draft bio) plus, from 2025-26, undrafted players new to the ESPN spine. */
export default async function RookiesPage({
  searchParams,
}: {
  searchParams: Promise<{ class?: string; sort?: string }>;
}) {
  const [draft, board, rates, raceDoc, similar] = await Promise.all([
    getHoopsDraft(), getHoopsPlayers(), getHoopsRates(), getHoopsRookieRace(), getHoopsSimilar()]);
  if (!draft || !board) {
    return <p className="text-sm text-text-dim">Draft doc not baked yet.</p>;
  }
  const sp = await searchParams;
  const boardSeasons = Object.keys(board.seasons).map(Number).sort((a, b) => b - a);
  const classes = boardSeasons.map((s) => s - 1);
  const dy = classes.includes(Number(sp.class)) ? Number(sp.class) : Math.max(...classes);
  const season = dy + 1;
  const race = raceDoc?.[String(season)];
  const rp = rates?.seasons[String(season)]?.players ?? {};
  const boardRows = new Map((board.seasons[String(season)] ?? []).map((r) => [r.id, r]));
  const ids = race ? Object.keys(race.players)
    : [...boardRows.keys()].filter((id) => draft.players[id]?.dy === dy);

  const rows = ids.map((id) => {
    const b = boardRows.get(id), r = rp[id], rc = race?.players[id];
    const breg = r?.["bpm|reg"];
    return {
      id, name: b?.name ?? rc?.name ?? id, team: b?.team ?? null,
      pick: pickOf(draft.players[id]?.dn ?? rc?.dn, draft.players[id]?.dr),
      gp: b?.gp ?? rc?.gp ?? 0, mpg: b?.min ?? 0, min: typeof r?.min === "number" ? r.min : 0,
      pts: b?.pts ?? 0, reb: b?.reb ?? 0, ast: b?.ast ?? 0,
      ts: typeof r?.ts_pct === "number" ? r.ts_pct : null,
      bpm: typeof breg === "number" ? breg : null,
      vorp: typeof r?.vorp === "number" ? r.vorp : null,
      gs: rc?.gs_total ?? null,
    };
  }).filter((r) => r.gp > 0);
  const sort: SortKey = (sp.sort && sp.sort in SORTS ? sp.sort : race ? "gs" : "pts") as SortKey;
  const val = (r: (typeof rows)[number]) =>
    sort === "gs" ? r.gs ?? -1 : sort === "pts" ? r.pts : sort === "bpm" ? r.bpm ?? -99 : r.min;
  rows.sort((a, b) => val(b) - val(a));

  const color = (team: string | null) => teamColor(team) ?? "#9aa3b2";
  const runners = race ? Object.entries(race.players).map(([id, p]) => ({
    id, name: p.name, color: color(boardRows.get(id)?.team ?? null), cum: p.cum,
  })) : [];
  const scatter = rows.filter((r) => r.bpm != null && r.min >= 100).map((r) => ({
    id: r.id, name: r.name, color: color(r.team), min: r.min, y: r.bpm as number,
  }));
  const compOf = new Map<string, string>();
  for (const [eid, p] of Object.entries(similar?.players ?? {})) {
    const top = p.n?.[0];
    if (top?.[2]) compOf.set(eid, top[2]);
  }
  const href = (q: Record<string, string>) =>
    `/rookies?${new URLSearchParams({ class: String(dy), ...(sort !== "gs" ? { sort } : {}), ...q })}`;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Rookies &amp; draft classes</h1>
          <p className="text-xs text-text-dim max-w-2xl">
            Every rookie&apos;s season: the race for the top of the class, who is producing beyond
            their minutes, and the standings. Rookies are the summer&apos;s draftees (balldontlie
            draft bio) plus, from 2025-26 on, undrafted players new to the ESPN box-score spine.
          </p>
        </div>
        <form method="get" className="flex items-center gap-2">
          <select name="class" defaultValue={String(dy)}
            className="rounded-md border border-border-subtle bg-surface-1 px-2 py-1.5 text-xs text-text-primary">
            {classes.map((y) => (
              <option key={y} value={y}>{y} class · {seasonLabel(y + 1)}</option>
            ))}
          </select>
          <button type="submit"
            className="rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-secondary hover:text-text-primary">
            Go
          </button>
        </form>
      </div>

      {race && runners.length > 1 && race.weeks > 1 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            The rookie race <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabel(season)} · rank by cumulative Game Score at the end of each week · top 8 and every leader
            </span>
          </h2>
          <RookieRace players={runners} weeks={race.weeks} start={race.start} />
          <p className="text-[10px] text-text-dim/70 mt-1">
            Game Score is Hollinger&apos;s box-score formula (points, makes, misses, rebounds, assists, steals,
            blocks, fouls, turnovers), summed over games: it rewards both quality and availability, which is
            what a season-long race measures. ESPN box scores; descriptive, not a forecast.
          </p>
        </div>
      )}

      {scatter.length >= 5 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-5xl">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Production vs playing time <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabel(season)} · regressed BPM by minutes · rookies with 100+ minutes
            </span>
          </h2>
          <RookieScatter points={scatter} />
          <p className="text-[10px] text-text-dim/70 mt-1">
            BPM 2.0 (Myers&apos; published coefficients, §16 — benchmarked against LUMA Basketball Research&apos;s
            xPTS-RAPM), regressed toward the league mean by measured reliability (§17). A box-score estimate,
            weak on defense; not a forecast.
          </p>
        </div>
      )}

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs overflow-x-auto max-w-5xl">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1.5">
          <h2 className="text-sm font-medium text-text-primary">
            {dy} class standings <span className="text-text-dim font-normal text-[10px]">
              · {seasonLabel(season)} · {rows.length} rookies · ranked by {SORTS[sort].toLowerCase()}
            </span>
          </h2>
          <div className="flex gap-1 text-[10px]">
            {(Object.keys(SORTS) as SortKey[]).filter((k) => race || k !== "gs").map((k) => (
              <Link key={k} href={href({ sort: k })}
                className={`rounded px-1.5 py-0.5 border ${k === sort ? "border-text-secondary text-text-primary" : "border-border-subtle text-text-dim hover:text-text-secondary"}`}>
                {SORTS[k]}
              </Link>
            ))}
          </div>
        </div>
        <table className="w-full text-[11px] tabular-nums min-w-[820px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-text-dim border-b border-border-subtle">
              <th className="text-right py-1.5 pr-2 font-medium">#</th>
              <th className="text-left px-2 font-medium">Player</th>
              <th className="text-left px-2 font-medium">Pick</th>
              <th className="text-left px-2 font-medium">Team</th>
              <th className="text-right px-2 font-medium">GP</th>
              <th className="text-right px-2 font-medium">MPG</th>
              <th className="text-right px-2 font-medium">PTS</th>
              <th className="text-right px-2 font-medium">REB</th>
              <th className="text-right px-2 font-medium">AST</th>
              <th className="text-right px-2 font-medium">TS%</th>
              <th className="text-right px-2 font-medium" title="regressed BPM (§16/§17)">BPM*</th>
              <th className="text-right px-2 font-medium">VORP</th>
              {race && <th className="text-right px-2 font-medium">GmSc</th>}
              <th className="text-left px-2 font-medium">Top comp</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className="border-b border-border-subtle/40 hover:bg-white/[0.03]">
                <td className="py-1 pr-2 text-right text-text-dim">{ord(i + 1)}</td>
                <td className="px-2">
                  <Link href={`/players/${r.id}`} className="text-text-primary hover:underline">{r.name}</Link>
                </td>
                <td className="px-2 text-text-dim">{r.pick}</td>
                <td className="px-2">{r.team && <TeamDot abbr={r.team} size={16} />}</td>
                <td className="text-right px-2 text-text-secondary">{r.gp}</td>
                <td className="text-right px-2 text-text-secondary">{r.mpg ? r.mpg.toFixed(1) : "—"}</td>
                <td className={`text-right px-2 ${sort === "pts" ? "text-text-primary font-medium" : "text-text-secondary"}`}>{r.pts.toFixed(1)}</td>
                <td className="text-right px-2 text-text-secondary">{r.reb.toFixed(1)}</td>
                <td className="text-right px-2 text-text-secondary">{r.ast.toFixed(1)}</td>
                <td className="text-right px-2 text-text-secondary">{r.ts != null ? `${(r.ts * 100).toFixed(1)}%` : "—"}</td>
                <td className={`text-right px-2 ${sort === "bpm" ? "text-text-primary font-medium" : r.bpm == null ? "text-text-dim" : r.bpm >= 0 ? "text-pos" : r.bpm < -2 ? "text-neg" : "text-text-secondary"}`}>
                  {r.bpm != null ? `${r.bpm > 0 ? "+" : ""}${r.bpm.toFixed(1)}` : "—"}
                </td>
                <td className="text-right px-2 text-text-secondary">{r.vorp != null ? r.vorp.toFixed(1) : "—"}</td>
                {race && <td className={`text-right px-2 ${sort === "gs" ? "text-text-primary font-medium" : "text-text-secondary"}`}>{r.gs != null ? r.gs.toFixed(0) : "—"}</td>}
                <td className="px-2 text-text-dim">{compOf.get(r.id) ?? <span className="text-text-dim/60">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[10px] text-text-dim/70 mt-1.5">
          BPM* = regressed BPM: green at or above league average, red below replacement (−2). Box lines from
          the validated board (ESPN boxes; balldontlie for 2023-24), rates from the ESPN rebuild (§0h, §16,
          §17). Comps are the cosine neighbors from the {similar ? seasonLabel(similar.season) : ""} pool (15+
          gp), so the live class earns them as games accumulate. Descriptive, not a forecast.
        </p>
      </div>

      {rows.length >= 2 && (
        <form method="get" action="/compare" className="flex flex-wrap items-center gap-2 text-xs max-w-5xl">
          <input type="hidden" name="s" value={season} />
          <span className="text-text-dim">Compare two rookies</span>
          {(["a", "b"] as const).map((k, i) => (
            <select key={k} name={k} defaultValue={rows[i].id}
              className="rounded-md border border-border-subtle bg-surface-1 px-2 py-1.5 text-text-primary">
              {rows.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          ))}
          <button type="submit"
            className="rounded-md border border-border-subtle px-2.5 py-1.5 text-text-secondary hover:text-text-primary">
            Compare
          </button>
        </form>
      )}
    </div>
  );
}
