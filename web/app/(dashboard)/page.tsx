import Link from "next/link";
import {
  getHoopsGames, getHoopsMeta, getHoopsPlayer, getHoopsPlayers, getHoopsReads, getHoopsSimilar,
  getHoopsStandings, getHoopsTeams, hoopsSeasons,
} from "@/lib/data-hoops";
import { PlayerFinder } from "@/components/ui/player-finder";
import { TeamDot, TeamLink } from "@/lib/team-dot";
import { LineTrend } from "@/components/ui/line-trend";

export const metadata = { title: "GOAT Hoops — a basketball analytics research log" };
export const revalidate = 300; // prod: 5-min route cache; dev renders per request

const seasonLabel = (s: number | string) => `${Number(s) - 1}-${String(s).slice(2)}`;

/** The hub: the live season's playoff picture, leaderboards, the top
 *  scorers' game-by-game trends in team colors, archetypes, reads. */
export default async function HubPage() {
  const [meta, seasons, standings, reads, board, similar] = await Promise.all([
    getHoopsMeta(), hoopsSeasons(), getHoopsStandings(), getHoopsReads(), getHoopsPlayers(),
    getHoopsSimilar()]);
  const boardSeason = Number(Object.keys(board?.seasons ?? {}).sort((a, b) => Number(b) - Number(a))[0]) || null;
  const finderPlayers = boardSeason
    ? (board?.seasons[String(boardSeason)] ?? []).map((r) => ({ id: r.id, name: r.name, team: r.team }))
    : [];
  const board27 = boardSeason ? (board?.seasons[String(boardSeason)] ?? []) : [];

  // conference map from the standings doc (any season carries it)
  const confOf = new Map<string, string>();
  for (const rows of Object.values(standings?.seasons ?? {})) {
    for (const r of rows) if (r.conference) confOf.set(r.abbr, r.conference);
  }
  const gamesSeason = seasons[0];
  const gamesDoc = gamesSeason ? await getHoopsGames(gamesSeason) : null;
  const played = (gamesDoc?.games ?? []).filter((g) => g.away_score > 0 || g.home_score > 0).slice(0, 6);
  const latestReads = [...(reads?.sections ?? [])].reverse().slice(0, 3);

  // live season team rows (teams.json 2027) → projected playoff picture
  const liveTeams = boardSeason ? ((await getHoopsTeams())?.seasons?.[String(boardSeason)] ?? []) : [];
  const projected = liveTeams
    .map((t) => ({ ...t, pct: t.g > 0 ? t.w / t.g : 0, proj: Math.round((t.g > 0 ? t.w / t.g : 0) * 82) }))
    .sort((a, b) => b.proj - a.proj || b.pct - a.pct);

  const SeedTable = ({ title, list }: { title: string; list: typeof projected }) => (
    <div className="min-w-0">
      <div className="text-text-dim text-[10px] mb-1">{title}</div>
      <div className="space-y-0.5">
        {list.map((r, i) => (
          <Link key={r.abbr} href={`/teams/${r.abbr}`}
            className="flex items-center gap-1.5 py-0.5 text-xs hover:bg-white/[0.03] rounded px-1 -mx-1">
            <span className={`tabular-nums w-4 text-[10px] ${i < 6 ? "text-pos" : i < 10 ? "text-flag" : "text-text-dim/60"}`}>
              {i + 1}
            </span>
            <TeamDot abbr={r.abbr} size={16} />
            <span className="truncate flex-1 text-text-secondary">{r.abbr}</span>
            <span className="text-text-dim tabular-nums text-[10px]">{r.w}-{r.l}</span>
            <span className="text-text-primary tabular-nums w-8 text-right font-medium">
              {r.g >= 3 ? `~${r.proj}` : "—"}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );

  // leaderboards (qualified: gp >= 3)
  const q = board27.filter((r) => (r.gp ?? 0) >= 3);
  const top = (key: "pts" | "reb" | "ast", n = 6) =>
    [...q].sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0)).slice(0, n);
  const topTs = [...q].filter((r) => r.fgp != null).sort((a, b) => (b.fgp ?? 0) - (a.fgp ?? 0)).slice(0, 6);

  const Board = ({ title, rows, fmt }: {
    title: string; rows: typeof q; fmt: (r: (typeof q)[number]) => string;
  }) => (
    <div className="min-w-0">
      <div className="text-text-dim text-[10px] mb-1">{title}</div>
      <div className="space-y-0.5">
        {rows.map((r, i) => (
          <Link key={r.id} href={`/players/${r.id}`}
            className="flex items-center gap-1.5 py-0.5 text-xs hover:bg-white/[0.03] rounded px-1 -mx-1">
            <span className="text-text-dim tabular-nums w-3 text-[10px]">{i + 1}</span>
            {r.team && <TeamDot abbr={r.team} size={16} />}
            <span className="truncate flex-1 text-text-secondary">{r.name}</span>
            <span className="text-text-primary tabular-nums font-medium">{fmt(r)}</span>
          </Link>
        ))}
      </div>
    </div>
  );

  // top-5 scorers' game-by-game trends, lines in TEAM colors
  const top5 = top("pts", 5);
  const scorerDocs = await Promise.all(top5.map((r) => getHoopsPlayer(r.id)));
  const trendSeries = top5.map((r, i) => {
    const doc = scorerDocs[i];
    const s27 = doc?.seasons?.[String(boardSeason)];
    const pts = (s27?.games ?? []).slice().reverse().map((g) => g.pts);
    return { name: r.name.split(" ").slice(-1)[0], color: undefined as unknown as string,
             points: pts, team: r.team };
  });
  // team colors resolved after the map (avoid importing teamColor twice)
  const { teamColor } = await import("@/lib/team-colors");
  // two lines may share a franchise blue (PHI/DAL) — later duplicates fall
  // back to white so the race stays readable
  const seen = new Set<string>();
  for (const s of trendSeries) {
    const c = teamColor(s.team) ?? "#888";
    s.color = seen.has(c) ? "#F5F5F5" : c;
    seen.add(c);
  }

  // archetype strip: members by pts
  const archList = Object.entries(similar?.archetypes ?? {});
  const membersByA: Record<string, string[]> = {};
  for (const [eid, p] of Object.entries(similar?.players ?? {})) {
    (membersByA[p.a] ??= []).push(eid);
  }
  const nameOf = new Map(board27.map((r) => [r.id, r]));
  const archChips = archList.map(([a, arch]) => {
    const members = (membersByA[a] ?? [])
      .map((eid) => nameOf.get(eid))
      .filter((r): r is NonNullable<typeof r> => !!r)
      .sort((x, y) => (y.pts ?? 0) - (x.pts ?? 0)).slice(0, 3);
    return { a, label: arch.label, size: arch.size, members };
  });

  return (
    <div className="space-y-5">
      {/* hero */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">GOAT Hoops</h1>
          <p className="text-xs text-text-dim mt-0.5 max-w-xl">
            The live season, measured — playoff picture, leaderboards, scorer trends —
            on a validated two-source spine, with every model read and its verdict on record.
          </p>
        </div>
        <PlayerFinder players={finderPlayers} />
      </div>

      {/* playoff picture + results/reads */}
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 lg:col-span-2">
          <div className="flex items-center justify-between mb-1.5">
            <h2 className="text-sm font-medium text-text-primary">
              Playoff picture <span className="text-text-dim font-normal text-[10px]">· {boardSeason ? seasonLabel(boardSeason) : ""} live</span>
            </h2>
            <Link href="/teams" className="text-[10px] text-text-dim hover:text-text-secondary">full board</Link>
          </div>
          <div className="grid grid-cols-2 gap-x-5">
            <SeedTable title="East" list={projected.filter((r) => confOf.get(r.abbr) === "East")} />
            <SeedTable title="West" list={projected.filter((r) => confOf.get(r.abbr) === "West")} />
          </div>
          <p className="text-[10px] text-text-dim/70 mt-1.5">
            ~wins = win% held over 82 — a naive pace projection, not a model ·
            green seeds 1-6, violet 7-10 (play-in), dim = lottery
          </p>
        </div>
        <div className="space-y-3">
          <div className="rounded-lg border border-border-subtle px-3 py-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <h2 className="text-sm font-medium text-text-primary">Latest results</h2>
              <Link href="/games" className="text-[10px] text-text-dim hover:text-text-secondary">all games</Link>
            </div>
            {played.map((g) => (
              <Link key={g.id} href={`/games/${g.id}`}
                className="flex items-center justify-between py-0.5 text-xs hover:text-text-secondary">
                <span className="truncate inline-flex items-center gap-1.5">
                  <TeamDot abbr={g.away} size={14} /> @ <TeamDot abbr={g.home} size={14} />
                </span>
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
            {latestReads.map((r) => (
              <Link key={r.n} href="/research" className="flex items-center justify-between gap-2 py-0.5 text-xs hover:text-text-secondary">
                <span className="truncate"><span className="text-text-dim">{r.n}</span> {r.title}</span>
                <span className={`shrink-0 text-[10px] font-medium ${r.verdict === "PASS" ? "text-pos" : r.verdict === "FAIL" ? "text-neg" : "text-flag"}`}>{r.verdict}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* leaderboards */}
      <div className="rounded-lg border border-border-subtle px-3 py-2.5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium text-text-primary">
            Leaderboards <span className="text-text-dim font-normal text-[10px]">· {boardSeason ? seasonLabel(boardSeason) : ""} · per game, gp ≥ 3</span>
          </h2>
          <Link href="/stats" className="text-[10px] text-text-dim hover:text-text-secondary">the full board</Link>
        </div>
        <div className="grid gap-x-5 gap-y-2 grid-cols-2 lg:grid-cols-4">
          <Board title="Points" rows={top("pts")} fmt={(r) => (r.pts ?? 0).toFixed(1)} />
          <Board title="Rebounds" rows={top("reb")} fmt={(r) => (r.reb ?? 0).toFixed(1)} />
          <Board title="Assists" rows={top("ast")} fmt={(r) => (r.ast ?? 0).toFixed(1)} />
          <Board title="FG% (5+ att/g)" rows={topTs} fmt={(r) => `${Math.round((r.fgp ?? 0) * 100)}%`} />
        </div>
      </div>

      {/* scorers trend */}
      {trendSeries.length > 1 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            The scorers&apos; race <span className="text-text-dim font-normal text-[10px]">
              · {boardSeason ? seasonLabel(boardSeason) : ""} · points by game · lines in team colors
            </span>
          </h2>
          <LineTrend series={trendSeries} unit="pts" />
        </div>
      )}

      {/* archetypes */}
      {archChips.length > 0 && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-medium text-text-primary">
              Archetypes <span className="text-text-dim font-normal text-[10px]">
                · {archChips.length} player types from {similar?.k ?? 7} centroids on z-scored tracking fields
              </span>
            </h2>
            <Link href="/comps" className="text-[10px] text-text-dim hover:text-text-secondary">the map</Link>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {archChips.map((a) => (
              <Link key={a.a} href="/comps"
                className="rounded-lg border border-border-subtle/70 px-2.5 py-2 hover:bg-white/[0.04]">
                <div className="text-xs font-medium text-text-primary truncate">{a.label}</div>
                <div className="text-[10px] text-text-dim mb-1">{a.size} players</div>
                <div className="space-y-0.5">
                  {a.members.map((m) => (
                    <div key={m.id} className="flex items-center gap-1.5 text-[11px]">
                      {m.team && <TeamDot abbr={m.team} size={14} />}
                      <span className="text-text-secondary truncate">{m.name}</span>
                      <span className="text-text-dim tabular-nums ml-auto">{(m.pts ?? 0).toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* story cards */}
      <div>
        <h2 className="text-sm font-medium text-text-primary mb-2">Where to start</h2>
        <div className="grid gap-2 sm:grid-cols-3">
          <Link href="/lineups" className="rounded-lg border border-border-subtle px-3 py-2.5 hover:bg-white/[0.04]">
            <div className="text-xs font-medium text-text-primary">Five-man units</div>
            <div className="text-[11px] text-text-dim mt-0.5">Real stint minutes, unit net ratings, on/off differentials — the §0f spine.</div>
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
