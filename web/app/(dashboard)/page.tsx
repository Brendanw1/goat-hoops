import Link from "next/link";
import { getHoopsGames, getHoopsMeta, getHoopsPlayers, getHoopsReads, getHoopsStandings, hoopsSeasons } from "@/lib/data-hoops";
import { PlayerFinder } from "@/components/ui/player-finder";

export const metadata = { title: "GOAT Hoops — a basketball analytics research log" };
export const dynamic = "force-dynamic";

const seasonLabel = (s: number | string) => `${Number(s) - 1}-${String(s).slice(2)}`;

/** The hub: what the league did, what we found, and how to get anywhere.
 *  Everything server-rendered; the finder is the one client widget. */
export default async function HubPage() {
  const [meta, seasons, standings, reads, board] = await Promise.all([
    getHoopsMeta(), hoopsSeasons(), getHoopsStandings(), getHoopsReads(), getHoopsPlayers()]);
  const boardSeason = Number(Object.keys(board?.seasons ?? {}).sort((a, b) => Number(b) - Number(a))[0]) || null;
  const finderPlayers = boardSeason
    ? (board?.seasons[String(boardSeason)] ?? []).map((r) => ({ id: r.id, name: r.name, team: r.team }))
    : [];
  const gamesSeason = seasons[0];
  const gamesDoc = gamesSeason ? await getHoopsGames(gamesSeason) : null;
  const played = (gamesDoc?.games ?? []).filter((g) => g.away_score > 0 || g.home_score > 0).slice(0, 5);
  const standSeason = standings ? Math.max(...Object.keys(standings.seasons).map(Number)) : null;
  const rows = (standSeason ? standings?.seasons[String(standSeason)] : undefined) ?? [];
  const conf = (c: string) => rows.filter((r) => r.conference === c).sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0)).slice(0, 8);
  const east = conf("East");
  const west = conf("West");
  const latestReads = [...(reads?.sections ?? [])].reverse().slice(0, 3);

  const PulseTable = ({ title, list }: { title: string; list: typeof rows }) => (
    <div className="min-w-0">
      <div className="text-text-dim text-[10px] mb-1">{title}</div>
      {list.map((r, i) => (
        <Link key={r.abbr} href={`/teams/${r.abbr}`}
          className="flex items-center justify-between py-0.5 text-xs hover:text-text-secondary">
          <span className="truncate">
            <span className="text-text-dim tabular-nums w-4 inline-block">{i + 1}</span>
            {r.abbr}
          </span>
          <span className="text-text-dim tabular-nums">{r.w}-{r.l}</span>
        </Link>
      ))}
    </div>
  );

  return (
    <div className="space-y-5">
      {/* hero */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">GOAT Hoops</h1>
          <p className="text-xs text-text-dim mt-0.5 max-w-xl">
            A basketball analytics research log — descriptive surfaces, preregistered
            model reads with their verdicts, and a validated two-source data spine.
          </p>
        </div>
        <PlayerFinder players={finderPlayers} />
      </div>

      {/* league pulse */}
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-border-subtle px-3 py-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <h2 className="text-sm font-medium text-text-primary">League pulse</h2>
            <Link href="/teams" className="text-[10px] text-text-dim hover:text-text-secondary">{standSeason ? seasonLabel(standSeason) : ""} · all</Link>
          </div>
          <div className="grid grid-cols-2 gap-x-4">
            <PulseTable title="East" list={east} />
            <PulseTable title="West" list={west} />
          </div>
        </div>
        <div className="rounded-lg border border-border-subtle px-3 py-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <h2 className="text-sm font-medium text-text-primary">Latest results</h2>
            <Link href="/games" className="text-[10px] text-text-dim hover:text-text-secondary">all games</Link>
          </div>
          {played.map((g) => (
            <Link key={g.id} href={`/games/${g.id}`}
              className="flex items-center justify-between py-0.5 text-xs hover:text-text-secondary">
              <span className="truncate">{g.away} @ {g.home}</span>
              <span className="text-text-dim tabular-nums">{g.away_score}-{g.home_score}</span>
            </Link>
          ))}
          {!played.length && <p className="text-xs text-text-dim">No results baked yet.</p>}
        </div>
        <div className="rounded-lg border border-border-subtle px-3 py-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <h2 className="text-sm font-medium text-text-primary">Latest reads</h2>
            <Link href="/research" className="text-[10px] text-text-dim hover:text-text-secondary">the index</Link>
          </div>
          {(reads?.sections ?? []).length === 0 && <p className="text-xs text-text-dim">reads.json.gz not baked yet.</p>}
          {latestReads.map((r) => (
            <Link key={r.n} href="/research" className="flex items-center justify-between gap-2 py-0.5 text-xs hover:text-text-secondary">
              <span className="truncate"><span className="text-text-dim">{r.n}</span> {r.title}</span>
              <span className={`shrink-0 text-[10px] font-medium ${r.verdict === "PASS" ? "text-pos" : r.verdict === "FAIL" ? "text-neg" : "text-flag"}`}>{r.verdict}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* story cards */}
      <div>
        <h2 className="text-sm font-medium text-text-primary mb-2">Where to start</h2>
        <div className="grid gap-2 sm:grid-cols-3">
          <Link href="/comps" className="rounded-lg border border-border-subtle px-3 py-2.5 hover:bg-white/[0.04]">
            <div className="text-xs font-medium text-text-primary">The archetype map</div>
            <div className="text-[11px] text-text-dim mt-0.5">Seven player types from 31 z-scored tracking fields, cosine neighbors, per-field deltas.</div>
          </Link>
          <Link href="/stats" className="rounded-lg border border-border-subtle px-3 py-2.5 hover:bg-white/[0.04]">
            <div className="text-xs font-medium text-text-primary">Shot-making board</div>
            <div className="text-[11px] text-text-dim mt-0.5">Who scores where the league can&apos;t — zone diets, Δ vs league, the +10.2 anchor.</div>
          </Link>
          <Link href="/surplus" className="rounded-lg border border-border-subtle px-3 py-2.5 hover:bg-white/[0.04]">
            <div className="text-xs font-medium text-text-primary">Contract value</div>
            <div className="text-[11px] text-text-dim mt-0.5">Production percentile vs cap-hit percentile — bargains, anchors, and the small-sample flags.</div>
          </Link>
        </div>
      </div>

      {meta?.validation ? (
        <p className="text-[10px] text-text-dim/70 max-w-2xl">
          Validation gate {meta.validation.gate}: {meta.validation.games_2024_25} game scores 2024-25
          and {meta.validation.boxes} player boxes vs {meta.validation.credit} match exactly — a
          source renders only after it agrees with the spine to the point.
        </p>
      ) : null}
    </div>
  );
}
