import Link from "next/link";
import {
  getHoopsDraft, getHoopsPlayer, getHoopsPlayers, getHoopsProjections, getHoopsSimilar,
} from "@/lib/data-hoops";
import { TeamDot } from "@/lib/team-dot";
import { LineTrend } from "@/components/ui/line-trend";
import { teamColor } from "@/lib/team-colors";

export const metadata = { title: "Rookies & draft classes" };
export const revalidate = 300;

const seasonLabel = (s: number | string) => `${Number(s) - 1}-${String(s).slice(2)}`;
const pickOf = (d?: { dr?: number; dn?: number }) =>
  d?.dn ? `#${d.dn}` : d?.dr ? `Rd ${d.dr}` : "—";

/** Draft classes: each draftee's rookie season is site year = draft year + 1.
 *  Classes render from the board seasons we hold (2024-2027 → drafts 2023-26). */
export default async function RookiesPage({
  searchParams,
}: {
  searchParams: Promise<{ class?: string }>;
}) {
  const [draft, board, projDoc, similar] = await Promise.all([
    getHoopsDraft(), getHoopsPlayers(), getHoopsProjections(), getHoopsSimilar()]);
  if (!draft || !board) {
    return <p className="text-sm text-text-dim">Draft doc not baked yet.</p>;
  }
  const { class: classParam } = await searchParams;
  const boardSeasons = Object.keys(board.seasons).map(Number).sort((a, b) => b - a);
  const classes = boardSeasons.map((s) => s - 1).filter((y) => y >= boardSeasons[boardSeasons.length - 1] - 1);
  const dy = Number(classParam) || Math.max(...classes);
  const rookieSeason = dy + 1;
  const rows = (board.seasons[String(rookieSeason)] ?? [])
    .filter((r) => draft.players[r.id]?.dy === dy)
    .sort((a, b) => (b.pts ?? 0) - (a.pts ?? 0));

  // projections + top comp where the season pool covers them
  const proj = projDoc?.players ?? {};
  const compOf = new Map<string, string>();
  for (const [eid, p] of Object.entries(similar?.players ?? {})) {
    const top = p.n?.[0];
    if (top?.[2]) compOf.set(eid, top[2]);
  }

  // the ladder: top 4 rookies' game-by-game points
  const top4 = rows.slice(0, 4);
  const docs = await Promise.all(top4.map((r) => getHoopsPlayer(r.id)));
  const series = top4.map((r, i) => ({
    name: r.name.split(" ").slice(-1)[0],
    color: teamColor(r.team) ?? "#999",
    points: ((docs[i]?.seasons?.[String(rookieSeason)]?.games ?? []).slice().reverse().map((g) => g.pts)),
  })).filter((s) => s.points.length > 1);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Rookies &amp; draft classes</h1>
          <p className="text-xs text-text-dim max-w-2xl">
            Every draftee&apos;s rookie season from the box-spine era — draft slot from
            the BDL contracts bio, stats from the validated board. Projections carry
            §14 intervals once a rookie clears the modeling floor; comps are the
            cosine neighbors from the season pool.
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

      {series.length > 1 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            The rookie ladder <span className="text-text-dim font-normal text-[10px]">
              · top {series.length} scorers of the class · points by game · team colors
            </span>
          </h2>
          <LineTrend series={series} unit="pts" />
        </div>
      )}

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs overflow-x-auto">
        <h2 className="text-sm font-medium text-text-primary mb-1.5">
          {dy} class <span className="text-text-dim font-normal text-[10px]">
            · {seasonLabel(rookieSeason)} · {rows.length} draftees on the spine
          </span>
        </h2>
        <table className="w-full text-[11px] tabular-nums min-w-[760px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-text-dim border-b border-border-subtle">
              <th className="text-left py-1.5 pr-2 font-medium">Pick</th>
              <th className="text-left px-2 font-medium">Player</th>
              <th className="text-left px-2 font-medium">Team</th>
              <th className="text-right px-2 font-medium">GP</th>
              <th className="text-right px-2 font-medium">MPG</th>
              <th className="text-right px-2 font-medium">PTS</th>
              <th className="text-right px-2 font-medium">REB</th>
              <th className="text-right px-2 font-medium">AST</th>
              <th className="text-right px-2 font-medium">FG%</th>
              <th className="text-right px-2 font-medium">2027 proj</th>
              <th className="text-left px-2 font-medium">Top comp</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const d = draft.players[r.id];
              const pr = proj[r.id];
              const comp = compOf.get(r.id);
              return (
                <tr key={r.id} className="border-b border-border-subtle/40 hover:bg-white/[0.03]">
                  <td className="py-1 pr-2 text-text-dim">{pickOf(d)}</td>
                  <td className="px-2">
                    <Link href={`/players/${r.id}`} className="text-text-primary hover:underline">{r.name}</Link>
                  </td>
                  <td className="px-2">{r.team && <TeamDot abbr={r.team} size={16} />}</td>
                  <td className="text-right px-2 text-text-secondary">{r.gp}</td>
                  <td className="text-right px-2 text-text-secondary">{r.min.toFixed(1)}</td>
                  <td className="text-right px-2 text-text-primary font-medium">{r.pts.toFixed(1)}</td>
                  <td className="text-right px-2 text-text-secondary">{r.reb.toFixed(1)}</td>
                  <td className="text-right px-2 text-text-secondary">{r.ast.toFixed(1)}</td>
                  <td className="text-right px-2 text-text-secondary">{r.fgp != null ? `${Math.round(r.fgp * 100)}%` : "—"}</td>
                  <td className="text-right px-2 text-text-secondary">
                    {pr ? `${pr.pts36} / ${pr.mpg}` : <span className="text-text-dim/60">at the floor</span>}
                  </td>
                  <td className="px-2 text-text-dim">{comp ?? <span className="text-text-dim/60">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="text-[10px] text-text-dim/70 mt-1.5">
          proj = the §14 ridge&apos;s points-per-36 and mpg for {seasonLabel(rookieSeason + 1)} —
          the 250-minute modeling floor keeps most early-season rookies off it until
          the games accumulate; comps come from the {similar ? seasonLabel(similar.season) : ""} pool
          (15+ gp), so the current class earns them as the season grows. Pre-NBA
          prospect rankings remain a documented gap (no college feed).
        </p>
      </div>
    </div>
  );
}
