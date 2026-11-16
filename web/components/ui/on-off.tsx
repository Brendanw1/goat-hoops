import type { HoopsOnOffRow, HoopsUnitRow } from "@/lib/data-hoops";

/**
 * A player's raw on/off (§0f stint walk), one row per season: the team's net
 * rating with them off the floor (hollow) and on it (filled), joined by a bar
 * colored by the swing. Beside it, where the swing ranks among teammates who
 * cleared the same floor, and the lineups they play in most. Raw on/off is not
 * adjusted for teammates or opponents, so the copy says so and small units are
 * flagged as anecdotes.
 */
export type OnOffSeason = {
  season: string; label: string; team: string; row: HoopsOnOffRow;
  mates: HoopsOnOffRow[]; units: HoopsUnitRow[];
};

const sgn = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;

export function OnOffPanel({ rows, id }: { rows: OnOffSeason[]; id: string }) {
  if (!rows.length) return null;
  const W = 560, padL = 56, padR = 12, rowH = 30, padT = 18;
  const vals = rows.flatMap((r) => [r.row.on_net, r.row.off_net]);
  const lo = Math.min(-10, ...vals) - 2, hi = Math.max(10, ...vals) + 2;
  const X = (v: number) => padL + ((v - lo) / (hi - lo)) * (W - padL - padR);
  const H = padT + rowH * rows.length + 4;
  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-2xl" role="img" aria-label="team net rating with the player off and on the floor">
        {[-10, 0, 10, 20].filter((t) => t > lo && t < hi).map((t) => (
          <g key={t}>
            <line x1={X(t)} x2={X(t)} y1={padT - 4} y2={H - 4} stroke={t === 0 ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.06)"} />
            <text x={X(t)} y={padT - 8} fontSize="8.5" textAnchor="middle" fill="rgba(255,255,255,0.35)">{t > 0 ? `+${t}` : t}</text>
          </g>
        ))}
        {rows.map((r, i) => {
          const y = padT + rowH * i + rowH / 2, up = r.row.diff >= 0;
          const c = up ? "rgb(52,211,153)" : "rgb(248,113,113)";
          return (
            <g key={r.season}>
              <text x={4} y={y + 3} fontSize="9.5" fill="rgba(255,255,255,0.7)">{r.label} {r.team}</text>
              <line x1={X(r.row.off_net)} x2={X(r.row.on_net)} y1={y} y2={y} stroke={c} strokeOpacity="0.55" strokeWidth="3" />
              <circle cx={X(r.row.off_net)} cy={y} r="4" fill="rgb(20,20,22)" stroke="rgba(255,255,255,0.6)" strokeWidth="1.3">
                <title>{`${r.label} off the floor: net ${sgn(r.row.off_net)} per 100`}</title>
              </circle>
              <circle cx={X(r.row.on_net)} cy={y} r="4.5" fill={c}>
                <title>{`${r.label} on the floor: net ${sgn(r.row.on_net)} per 100 over ${r.row.on_poss} possessions`}</title>
              </circle>
              <text x={X(r.row.on_net) + (up ? 8 : -8)} y={y + 3} fontSize="9.5" textAnchor={up ? "start" : "end"} fill={c}>
                {sgn(r.row.diff)}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="text-[10.5px] text-text-dim">
        Hollow: the team&apos;s net rating (points per 100 possessions) with the player on the bench. Filled: with them on
        the floor. The bar is the swing.
      </p>
      {rows.map((r) => {
        const rank = [...r.mates].sort((a, b) => b.diff - a.diff).findIndex((m) => m.pid === id) + 1;
        const mine = r.units.filter((u) => u.ids.includes(id)).sort((a, b) => b.poss - a.poss).slice(0, 3);
        return (
          <div key={r.season} className="grid sm:grid-cols-2 gap-3 text-[11px]">
            <div className="space-y-1">
              <div className="text-text-secondary">{r.label}: on-court ratings</div>
              <div className="tabular-nums text-text-dim">
                Offense <span className="text-text-primary">{r.row.on_ortg.toFixed(1)}</span> ·
                Defense <span className="text-text-primary">{r.row.on_drtg.toFixed(1)}</span> ·
                {" "}{r.row.on_poss.toLocaleString()} possessions, {Math.round(r.row.on_min)} min
                {r.row.on_poss < 2500 && <span className="text-flag"> · small sample (under ~2,500 possessions)</span>}
              </div>
              {r.mates.length > 1 && (
                <div className="flex items-center gap-2">
                  <svg viewBox="0 0 200 14" className="w-48" aria-label="swing among teammates">
                    {r.mates.map((m) => {
                      const ds = r.mates.map((x) => x.diff), a = Math.min(...ds), b = Math.max(...ds);
                      const x = 4 + ((m.diff - a) / (b - a || 1)) * 192;
                      return <line key={m.pid} x1={x} x2={x} y1={m.pid === id ? 1 : 4} y2={m.pid === id ? 13 : 10}
                        stroke={m.pid === id ? "white" : "rgba(255,255,255,0.3)"} strokeWidth={m.pid === id ? 2 : 1}>
                        <title>{`${m.name} ${sgn(m.diff)}`}</title></line>;
                    })}
                  </svg>
                  <span className="text-text-dim">#{rank} of {r.mates.length} {r.team} players with 1,500+ on-court possessions</span>
                </div>
              )}
            </div>
            {mine.length > 0 && (
              <div className="space-y-0.5">
                <div className="text-text-secondary">Most-used lineups</div>
                {mine.map((u) => (
                  <div key={u.ids.join()} className="flex justify-between gap-2 tabular-nums">
                    <span className="truncate text-text-dim">
                      {u.names.filter((_, j) => u.ids[j] !== id).map((n) => n.split(" ").slice(-1)[0]).join(", ")}
                    </span>
                    <span className={u.poss < 500 ? "text-text-dim" : "text-text-secondary"}>
                      {u.net != null ? sgn(u.net) : "—"} · {u.poss} poss{u.poss < 500 ? " (anecdote)" : ""}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
