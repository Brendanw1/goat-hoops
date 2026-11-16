import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { StatStrip, type StripPoint } from "@/components/ui/stat-strip";
import { getHoopsPlayers, getHoopsRates, type HoopsRatesPct } from "@/lib/data-hoops";
import { pctBarTone, pctTone } from "@/lib/tone";

export const metadata = { title: "Hoops leaders" };
export const revalidate = 300;

type Def = { key: string; label: string; group: string; pct?: boolean; dp: number; what: string };
const DEFS: Def[] = [
  { key: "pts", label: "Points", group: "Per game", dp: 1, what: "points per game" },
  { key: "reb", label: "Rebounds", group: "Per game", dp: 1, what: "rebounds per game" },
  { key: "ast", label: "Assists", group: "Per game", dp: 1, what: "assists per game" },
  { key: "stl", label: "Steals", group: "Per game", dp: 1, what: "steals per game" },
  { key: "blk", label: "Blocks", group: "Per game", dp: 1, what: "blocks per game" },
  { key: "bpm", label: "BPM", group: "Impact", dp: 1, what: "Box Plus/Minus 2.0 (Myers): points per 100 possessions above an average player, estimated from the box score" },
  { key: "obpm", label: "OBPM", group: "Impact", dp: 1, what: "the offensive half of BPM: Myers' published offensive coefficients, team-adjusted so a team's OBPM sums to its offensive rating above league average (§16-b)" },
  { key: "dbpm", label: "DBPM", group: "Impact", dp: 1, what: "the defensive half of BPM: BPM minus OBPM, so the two halves always add to the whole (§16-b)" },
  { key: "vorp", label: "VORP", group: "Impact", dp: 1, what: "value over a replacement player (BPM −2.0), scaled by share of team minutes and games" },
  { key: "ts_pct", label: "TS%", group: "Shooting", pct: true, dp: 1, what: "true shooting: PTS / 2(FGA + 0.44·FTA)" },
  { key: "efg_pct", label: "eFG%", group: "Shooting", pct: true, dp: 1, what: "effective FG%: (FGM + 0.5·3PM) / FGA" },
  { key: "ftr", label: "FT rate", group: "Shooting", pct: true, dp: 1, what: "free-throw attempts per field-goal attempt" },
  { key: "tpar", label: "3PA rate", group: "Shooting", pct: true, dp: 1, what: "share of field-goal attempts from three" },
  { key: "usg_pct", label: "USG%", group: "Creation", pct: true, dp: 1, what: "share of team plays the player finishes (shot, trip, turnover) while on court" },
  { key: "ast_pct", label: "AST%", group: "Creation", pct: true, dp: 1, what: "share of teammates' made shots the player assists while on court" },
  { key: "ast_to", label: "AST/TO", group: "Creation", dp: 2, what: "assists per turnover" },
  { key: "off_load", label: "Offensive Load", group: "Creation", dp: 1, what: "Ben Taylor's estimate of offensive burden per 100 possessions: shots, free-throw trips, turnovers and plays created for teammates. Volume, not quality" },
  { key: "to_ratio", label: "TO ratio", group: "Creation", dp: 1, what: "turnovers per 100 plays the player finishes or assists on (lower is better)" },
  { key: "orb_pct", label: "OREB%", group: "Rebounding", pct: true, dp: 1, what: "share of available offensive rebounds grabbed" },
  { key: "drb_pct", label: "DREB%", group: "Rebounding", pct: true, dp: 1, what: "share of available defensive rebounds grabbed" },
  { key: "reb_pct", label: "REB%", group: "Rebounding", pct: true, dp: 1, what: "share of all available rebounds grabbed" },
  { key: "putback_rate", label: "Putback rate", group: "Rebounding", pct: true, dp: 1, what: "share of the player's offensive rebounds followed by their own shot within 3 seconds" },
  { key: "fdrawn36", label: "FT fouls drawn/36", group: "Fouls drawn", dp: 2, what: "fouls drawn that sent the player to the line (each free-throw trip they start, and-ones included) per 36 minutes. Offensive and non-bonus fouls drawn aren't in the feed" },
  { key: "andones", label: "And-ones", group: "Fouls drawn", dp: 0, what: "made field goals plus a foul (the shooter's 1-of-1 free throw at the same clock)" },
  { key: "andone36", label: "And-ones/36", group: "Fouls drawn", dp: 2, what: "and-ones per 36 minutes" },
  { key: "rim_rate", label: "Rim rate", group: "Shot zones", pct: true, dp: 1, what: "share of field-goal attempts within 4 ft of the rim" },
  { key: "rim_fg", label: "Rim FG%", group: "Shot zones", pct: true, dp: 1, what: "field-goal percentage within 4 ft of the rim" },
  { key: "mid_rate", label: "Mid rate", group: "Shot zones", pct: true, dp: 1, what: "share of field-goal attempts from mid-range (long twos outside the paint)" },
  { key: "mid_fg", label: "Mid FG%", group: "Shot zones", pct: true, dp: 1, what: "mid-range field-goal percentage" },
  { key: "c3_rate", label: "Corner-3 rate", group: "Shot zones", pct: true, dp: 1, what: "share of field-goal attempts from the corners" },
  { key: "c3_fg", label: "Corner 3P%", group: "Shot zones", pct: true, dp: 1, what: "corner three-point percentage" },
  { key: "ab3_fg", label: "Above-break 3P%", group: "Shot zones", pct: true, dp: 1, what: "above-the-break three-point percentage" },
  { key: "xefg", label: "Expected eFG", group: "Shot quality", pct: true, dp: 1, what: "the eFG a league-average shooter would post on this player's shots: per-shot make model on distance, zone and shot family, no shooter identity (§20)" },
  { key: "smk", label: "Shot-making", group: "Shot quality", pct: true, dp: 1, what: "actual eFG minus expected eFG on the same shots (points of eFG made above or below the shot quality)" },
  { key: "pct_unast", label: "Self-created %", group: "Self-creation", pct: true, dp: 1, what: "share of made field goals that were unassisted" },
  { key: "unast36", label: "Self-created FGM/36", group: "Self-creation", dp: 2, what: "unassisted made field goals per 36 minutes" },
  { key: "unast3_36", label: "Self-created 3PM/36", group: "Self-creation", dp: 2, what: "unassisted made threes per 36 minutes" },
  { key: "pullup_rate", label: "Pull-up rate", group: "Self-creation", pct: true, dp: 1, what: "share of attempts that are pull-up or step-back jumpers (ESPN's shot labels)" },
  { key: "pullup_efg", label: "Pull-up eFG%", group: "Self-creation", pct: true, dp: 1, what: "effective FG% on pull-up and step-back jumpers" },
  { key: "ast_pts36", label: "AST points/36", group: "Playmaking", dp: 1, what: "points created by assists per 36 minutes (2 or 3 per assisted make)" },
  { key: "ast3_36", label: "AST to 3s/36", group: "Playmaking", dp: 2, what: "assists on made threes per 36 minutes" },
  { key: "ast_rim36", label: "AST at rim/36", group: "Playmaking", dp: 2, what: "assists on makes within 4 ft of the rim per 36 minutes" },
  { key: "badpass36", label: "Bad-pass TO/36", group: "Playmaking", dp: 2, what: "bad-pass turnovers per 36 minutes (lower is better)" },
  { key: "lostball36", label: "Lost-ball TO/36", group: "Playmaking", dp: 2, what: "lost-ball turnovers per 36 minutes (lower is better)" },
  { key: "stl_pct", label: "STL%", group: "Defense", pct: true, dp: 1, what: "steals per opponent possession while on court" },
  { key: "blk_pct", label: "BLK%", group: "Defense", pct: true, dp: 1, what: "share of opponent two-point attempts blocked" },
  { key: "gmsc", label: "Game Score", group: "Milestones", dp: 1, what: "Hollinger Game Score per game" },
  { key: "g30", label: "30-pt games", group: "Milestones", dp: 0, what: "games with 30 or more points" },
  { key: "g40", label: "40-pt games", group: "Milestones", dp: 0, what: "games with 40 or more points" },
  { key: "dd", label: "Double-doubles", group: "Milestones", dp: 0, what: "games with 10+ in two of points, rebounds, assists, steals, blocks" },
  { key: "td", label: "Triple-doubles", group: "Milestones", dp: 0, what: "games with 10+ in three of points, rebounds, assists, steals, blocks" },
];
const BOX = new Set(["pts", "reb", "ast", "stl", "blk"]);
const POOLS: Record<string, string> = { all: "All", G: "Guards", F: "Forwards", C: "Centers" };

const EXPO_LABEL: Record<string, string> = { min: "minutes", fga: "field-goal attempts", tsa: "shooting attempts",
  fga_sh: "field-goal attempts", sq_fga: "shots", oreb_ev: "offensive rebounds", fgm_sh: "made shots" };

const label = (s: number) => `${s - 1}-${String(s).slice(2)}`;

export default async function LeadersPage({ searchParams }: {
  searchParams: Promise<{ season?: string; stat?: string; pool?: string; n?: string; rank?: string }>;
}) {
  const sp = await searchParams;
  const [rates, board] = await Promise.all([getHoopsRates(), getHoopsPlayers()]);
  if (!rates) return <p className="text-xs text-text-dim">Leaderboards are not baked yet.</p>;

  const seasons = Object.keys(rates.seasons).map(Number).sort((a, b) => b - a);
  const season = seasons.includes(Number(sp.season)) ? Number(sp.season) : seasons[0];
  const live = new Set(rates.stats);
  const defs = DEFS.filter((d) => BOX.has(d.key) || live.has(d.key));
  const def = defs.find((d) => d.key === sp.stat) ?? defs.find((d) => d.key === "ts_pct") ?? defs[0];
  const lg = rates.league[String(season)];
  const pool = sp.pool && sp.pool in POOLS && (sp.pool === "all" || (lg.pools[sp.pool] ?? 0) >= 40)
    ? sp.pool : "all";
  const n = [25, 50, 100].includes(Number(sp.n)) ? Number(sp.n) : 25;
  const lower = rates.lower_better.includes(def.key);
  const gate = rates.gate_0h.stats?.[def.key];
  const status = BOX.has(def.key) ? "box score" : rates.status?.[def.key]
    ?? (gate && (gate.pass || gate.pass_0hb) ? "gated (§0h)" : "descriptive");
  const floor = lg[`${def.key}|floor`] as number | undefined;
  const kReg = rates.shrink_k?.[def.key];
  const byReg = kReg != null && sp.rank === "reg";
  const expo = rates.shrink_expo?.[def.key];

  const boardRows = new Map((board?.seasons[String(season)] ?? []).map((r) => [r.id, r]));
  const qualified = Object.entries(rates.seasons[String(season)]?.players ?? {})
    .filter(([, p]) => p.q && p[`${def.key}|q`] !== false && (pool === "all" || p.pos === pool))
    .flatMap(([id, p]) => {
      const b = boardRows.get(id);
      const raw = BOX.has(def.key) ? b?.[def.key as "pts"] : p[def.key];
      if (typeof raw !== "number" || !b) return [];
      const pc = p[`${def.key}|pct`] as HoopsRatesPct | undefined;
      const baked = pool === "all" ? pc?.all : pc?.pos;
      const reg = p[`${def.key}|reg`];
      return [{ id, name: b.name, team: b.team, pos: p.pos, gp: b.gp, mpg: b.min, v: raw,
                reg: typeof reg === "number" ? reg : null, pct: baked != null ? baked / 100 : null }];
    });
  // box stats carry no baked percentile — rank within the same qualified pool
  if (BOX.has(def.key)) {
    const vs = qualified.map((r) => r.v).sort((a, b) => a - b);
    for (const r of qualified) {
      const below = vs.filter((x) => x < r.v).length, eq = vs.filter((x) => x === r.v).length;
      r.pct = (below + eq / 2) / vs.length;
    }
  }
  const key = (r: { v: number; reg: number | null }) => (byReg ? r.reg ?? r.v : r.v);
  qualified.sort((a, b) => (lower ? key(a) - key(b) : key(b) - key(a)));
  const top = qualified.slice(0, n);
  const fmt = (v: number) => def.pct ? `${(v * 100).toFixed(def.dp)}%` : v.toFixed(def.dp);
  const points: StripPoint[] = qualified.map((r) => ({ id: r.id, name: r.name, v: r.v, pct: r.pct }));
  const qs = (o: Record<string, string | number>) => {
    const u = new URLSearchParams({ season: String(season), stat: def.key, pool, n: String(n), rank: byReg ? "reg" : "raw" });
    for (const [k, v] of Object.entries(o)) u.set(k, String(v));
    return `/leaders?${u}`;
  };
  const chip = (on: boolean) =>
    `rounded px-2 py-0.5 border ${on ? "border-border-subtle bg-white/[0.06] text-text-primary" : "border-transparent text-text-dim hover:text-text-secondary"}`;
  const groups = [...new Set(defs.map((d) => d.group))];

  return (
    <div className="space-y-4 max-w-5xl">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-lg font-semibold text-text-primary">Leaders · {label(season)}</h1>
        <div className="flex gap-1.5 text-[11px]">
          {seasons.map((s) => <Link key={s} href={qs({ season: s })} className={chip(s === season)}>{label(s)}</Link>)}
        </div>
      </div>

      <div className="space-y-1.5 text-[11px]">
        {groups.map((g) => (
          <div key={g} className="flex flex-wrap items-center gap-1.5">
            <span className="w-20 shrink-0 text-text-dim">{g}</span>
            {defs.filter((d) => d.group === g).map((d) => (
              <Link key={d.key} href={qs({ stat: d.key })} className={chip(d.key === def.key)}>{d.label}</Link>
            ))}
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="w-20 shrink-0 text-text-dim">Pool</span>
          {Object.entries(POOLS).filter(([k]) => k === "all" || (lg.pools[k] ?? 0) >= 40).map(([k, v]) => (
            <Link key={k} href={qs({ pool: k })} className={chip(k === pool)}>{v}</Link>
          ))}
          <span className="ml-3 text-text-dim">Show</span>
          {[25, 50, 100].map((k) => <Link key={k} href={qs({ n: k })} className={chip(k === n)}>{k}</Link>)}
          {kReg != null && <>
            <span className="ml-3 text-text-dim">Rank by</span>
            <Link href={qs({ rank: "raw" })} className={chip(!byReg)}>Raw</Link>
            <Link href={qs({ rank: "reg" })} className={chip(byReg)}>Regressed</Link>
          </>}
        </div>
      </div>

      <p className="text-xs text-text-dim">
        <span className="text-text-secondary font-medium">{def.label}</span> — {def.what}.
        {" "}Qualified: {lg.qual_min}+ minutes and {lg.qual_gp}+ games{floor ? ` and ${floor}+ attempts of this kind` : ""} ({qualified.length} {POOLS[pool].toLowerCase()}
        {pool === "all" ? " players" : ""}). Percentiles rank within this pool.
        {" "}<span className={status === "descriptive" ? "text-flag" : ""}>Status: {status}</span>
        {status === "descriptive" && " — no external reference to check it against yet."}
        {kReg != null && <> · Regressed = pulled toward the league mean as if the player had {Math.round(kReg)} more
          {" "}{EXPO_LABEL[expo ?? "min"] ?? "minutes"} of league-average play, the amount measured reliability calls for
          (§17{expo && expo !== "min" ? "-b: weighted by attempts, not minutes" : ""}).
          {byReg && " Ranked by the regressed value, which discounts hot small samples."}</>}
      </p>

      <StatStrip points={points} shown={new Set(top.map((r) => r.id))} fmt={fmt} label={def.label} lower={lower} />

      <div className="overflow-x-auto">
        <table className="w-full text-[12px] tabular-nums">
          <thead className="text-text-dim text-[10.5px] text-left">
            <tr className="border-b border-border-subtle">
              <th className="py-1.5 pr-2 w-8">#</th><th className="pr-2">Player</th><th className="pr-2">Team</th>
              <th className="pr-2">Pos</th><th className="pr-2 text-right">GP</th><th className="pr-2 text-right">MPG</th>
              <th className={`pr-3 text-right ${byReg ? "" : "text-text-secondary"}`}>{def.label}</th>
              {kReg != null && <th className={`pr-3 text-right ${byReg ? "text-text-secondary" : ""}`} title="regressed toward the league mean (§17)">Regressed</th>}
              <th className="w-48">Percentile</th>
            </tr>
          </thead>
          <tbody>
            {top.map((r, i) => (
              <tr key={r.id} className="border-b border-white/[0.04] hover:bg-white/[0.03]">
                <td className="py-1 pr-2 text-text-dim">{i + 1}</td>
                <td className="pr-2"><Link href={`/players/${r.id}`} className="text-text-primary hover:underline">{r.name}</Link></td>
                <td className="pr-2 text-text-secondary">{r.team ?? "—"}</td>
                <td className="pr-2 text-text-dim">{r.pos ?? "—"}</td>
                <td className="pr-2 text-right text-text-secondary">{r.gp}</td>
                <td className="pr-2 text-right text-text-secondary">{r.mpg.toFixed(1)}</td>
                <td className={`pr-3 text-right ${pctTone(r.pct)}`}>{fmt(r.v)}</td>
                {kReg != null && <td className="pr-3 text-right text-text-secondary">{r.reg != null ? fmt(r.reg) : "—"}</td>}
                <td>
                  {r.pct != null && (
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-36 rounded-full bg-white/[0.06]">
                        <div className={`h-1.5 rounded-full ${pctBarTone(r.pct)}`} style={{ width: `${Math.max(r.pct * 100, 2)}%` }} />
                      </div>
                      <span className="text-[10.5px] text-text-dim w-6 text-right">{Math.round(r.pct * 100)}</span>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!top.length && <p className="text-xs text-text-dim py-3">No qualified players for this pool yet.</p>}
      </div>

      <p className="text-[10px] text-text-dim/70">
        Regular season, computed from ESPN box scores with NBA.com definitions (on-court team totals
        estimated by minutes share); shot zones, self-creation and playmaking from ESPN play-by-play.
        Gated stats passed the §0h/§0h-b/§0h-c/§0i/§0j/§16/§16-b/§18/§20 checks against an independent source; see Methods.
        {def.key === "off_load" && " Offensive Load is benchmarked against LUMA Basketball Research's load channel (Lens), which is not shown here."}
        {["bpm", "vorp", "obpm", "dbpm"].includes(def.key) && " BPM and its offense/defense halves are benchmarked against LUMA Basketball Research's xPTS-RAPM (net, offense, defense), which is not shown here."}
        {" "}Every stat's feed, formula and code path: <Link href="/methods#sources" className="underline">Sources</Link>.
        Descriptive, not a forecast.
      </p>
    </div>
  );
}
