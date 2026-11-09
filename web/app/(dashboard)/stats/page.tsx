import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { StatsTable, type StatsRow } from "@/components/ui/stats-table";
import { getHoopsAdvAgg, getHoopsMeta, getHoopsPlayers, getHoopsSeasAvgs, hoopsSeasons } from "@/lib/data-hoops";
import { UsageScatter, type ScatterRow } from "@/components/ui/usage-scatter";

export const metadata = { title: "Hoops stats" };
export const revalidate = 300; // prod: 5-min route cache; dev renders per request

const MIN_GP = 15;

/** The leaderboard: one sortable table per season, basic board + advanced
 *  roll-ups merged, every judged column colored against the season's own
 *  league bands. */
export default async function HoopsStatsPage({ searchParams }: {
  searchParams: Promise<{ season?: string }>;
}) {
  const sp = await searchParams;
  const [seasons, meta] = await Promise.all([hoopsSeasons(), getHoopsMeta()]);
  // default to the newest season with a real sample behind it — a two-week-old
  // live season has no qualifiers yet and an empty leaderboard reads as broken
  const established = seasons.find((s) => (meta?.seasons[String(s)]?.games ?? 0) >= 400);
  const season = Number(sp.season) || (established ?? seasons[0]);
  const [board, advDoc] = await Promise.all([getHoopsPlayers(), getHoopsAdvAgg()]);
  const advPlayers = advDoc?.seasons[String(season)]?.players ?? {};
  const lg = { ...(advDoc?.league[String(season)] ?? {}) } as Record<string, unknown>;
  const n = (v: unknown) => (typeof v === "number" ? v : null);

  const rows: StatsRow[] = (board?.seasons[String(season)] ?? [])
    .filter((r) => r.gp >= MIN_GP)
    .map((r) => {
      const a = advPlayers[r.id];
      return {
        id: r.id, name: r.name, team: r.team, gp: r.gp, gs: r.gs, min: r.min,
        pts: r.pts, reb: r.reb, ast: r.ast, stl: r.stl, blk: r.blk, tov: r.tov,
        fgp: r.fgp ?? null, tpp: r.tpp ?? null, ftp: r.ftp ?? null,
        ts: n(a?.ts_pct), usg: n(a?.usg_pct), ortg: n(a?.ortg), drtg: n(a?.drtg),
        net: n(a?.net), pie: n(a?.pie),
      };
    });

  // shooting-% league bands from the board population itself (advagg carries
  // the advanced fields' bands; the basic percentages live on board rows)
  for (const k of ["fgp", "tpp", "ftp"]) {
    const vals = rows.map((r) => r[k as "fgp"] as number | null)
      .filter((v): v is number => typeof v === "number").sort((a, b) => a - b);
    if (vals.length >= 30) {
      const at = (p: number) => vals[Math.min(Math.floor(p * vals.length), vals.length - 1)];
      lg[`${k}|dist`] = { p10: at(0.10), p25: at(0.25), p50: at(0.50), p75: at(0.75), p90: at(0.90) };
    }
  }

  // advanced fields: advagg covers through 2025-26; a season the walk hasn't
  // reached (the live one) takes usage/TS from the season-averages doc instead
  const usgCovered = rows.filter((r) => r.usg != null).length;
  let enriched = rows;
  if (usgCovered < rows.length / 2) {
    const sa = await getHoopsSeasAvgs(season);
    if (sa?.players) {
      enriched = rows.map((r) => {
        const a = sa.players[r.id]?.adv;
        return a && typeof a.usg_pct === "number" && typeof a.ts_pct === "number"
          ? { ...r, usg: a.usg_pct, ts: a.ts_pct } : r;
      });
    }
  }
  const scatterPool: ScatterRow[] = enriched.flatMap((r) =>
    r.usg != null && r.ts != null
      ? [{ id: r.id, name: r.name, team: r.team, usg: r.usg, ts: r.ts, gp: r.gp, min: r.min }]
      : []);

  const qs = (s: number) => `/stats?season=${s}`;

  return (
    <div className="space-y-4">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-text-primary">
          Stats {season ? `· ${season - 1}-${String(season).slice(2)}` : ""}
        </h1>
        <div className="flex gap-1.5 text-[11px]">
          {seasons.map((s) => (
            <Link key={s} href={qs(s)}
              className={`rounded px-2 py-0.5 border ${s === season ? "border-border-subtle bg-white/[0.06] text-text-primary" : "border-transparent text-text-dim hover:text-text-secondary"}`}>
              {s - 1}-{String(s).slice(2)}
            </Link>
          ))}
        </div>
      </div>
      <p className="text-xs text-text-dim max-w-5xl">
        {rows.length} players with {MIN_GP}+ games. Click any header to sort; a column colored
        green sits in the season&apos;s top quartile (top decile bold), red the bottom.
        Shooting % bands come from the season&apos;s own player pool; TS%/USG%/ratings from the
        balldontlie v2-advanced roll-ups.
        {season === 2024 && <> <span className="text-flag">The 2023-24 season is partial (567 of 1230 games covered).</span></>}
        {(() => {
          const cov = advDoc?.coverage?.[String(season)];
          return cov && cov.full === false ? (
            <span className="text-flag">
              {` The advanced feed covers ${cov.games.toLocaleString()}${cov.spine ? ` of ~${cov.spine.toLocaleString()}` : ""} games of ${season - 1}-${String(season).slice(2)} — advanced columns are partial-season.`}
            </span>
          ) : null;
        })()}
      </p>

      <section className="space-y-2 max-w-5xl">
        <h2 className="text-sm font-medium text-text-primary">
          Usage vs efficiency <span className="text-text-dim font-normal text-[10px]">· {season - 1}-{String(season).slice(2)} · the offensive-role map</span>
        </h2>
        <UsageScatter pool={scatterPool} seasonLabel={`${season - 1}-${String(season).slice(2)}`} />
      </section>

      <StatsTable rows={enriched} league={lg} lower={advDoc?.lower_better ?? []} />

      {!rows.length ? <p className="text-xs text-text-dim">No seasons baked for this year.</p> : null}
      <p className="text-[10px] text-text-dim/70 max-w-5xl">
        balldontlie + ESPN-derived data — internal research; public surfaces carry balldontlie
        numbers only while a subscription is active.
      </p>
    </div>
  );
}
