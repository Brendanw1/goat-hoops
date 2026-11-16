/**
 * The rookie race as a bump chart: each line is a rookie's rank (by
 * cumulative Game Score) at the end of every week; lead changes are ringed
 * on the #1 row and narrated below. Team colors are identity only. Pure
 * SVG, no client JS; every node carries a <title> with the week, rank and
 * running total, and the right-hand labels carry the current numbers.
 */
import { lastName } from "./rookie-scatter";

type Runner = { id: string; name: string; color: string; cum: number[] };

export function rookieRanks(players: Runner[], weeks: number) {
  const ranks: Record<string, number[]> = Object.fromEntries(players.map((p) => [p.id, []]));
  const leaders: string[] = [];
  for (let w = 0; w < weeks; w++) {
    const order = [...players].sort((a, b) => b.cum[w] - a.cum[w] || a.id.localeCompare(b.id));
    order.forEach((p, i) => ranks[p.id].push(p.cum[w] > 0 ? i + 1 : Infinity));
    leaders.push(order[0].cum[w] > 0 ? order[0].id : "");
  }
  return { ranks, leaders };
}

export function RookieRace({ players, weeks, start, show = 8 }: {
  players: Runner[]; weeks: number; start: string; show?: number;
}) {
  if (weeks < 2 || players.length < 2) return null;
  const { ranks, leaders } = rookieRanks(players, weeks);
  const last = weeks - 1;
  const everFirst = new Set(leaders.filter(Boolean));
  const shown = players.filter((p) => ranks[p.id][last] <= show || everFirst.has(p.id));
  const cap = Math.max(show, ...shown.map((p) => Math.min(ranks[p.id][last], 12)));
  const W = 760, padL = 34, padR = 176, padT = 14, padB = 26, row = 22;
  const H = padT + padB + row * (cap - 1);
  const X = (w: number) => padL + (w / last) * (W - padL - padR);
  const Y = (r: number) => padT + (r - 1) * row;
  const top = [...shown].sort((a, b) => ranks[a.id][last] - ranks[b.id][last]);
  const lead = top[0], second = top[1];
  const byId = new Map(players.map((p) => [p.id, p]));
  const changes = leaders.map((id, w) => ({ id, w })).filter((d, i) => d.id && (i === 0 || leaders[i - 1] !== d.id));
  const weeksLed = leaders.filter((id) => id === lead.id).length;
  const date = (w: number) => {
    const d = new Date(`${start}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + 7 * w + 6);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  };
  const last1 = lastName;

  return (
    <figure className="space-y-1.5">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Rookie race: ${lead.name} leads with ${lead.cum[last].toFixed(0)} Game Score`}>
        {Array.from({ length: cap }, (_, i) => i + 1).map((r) => (
          <g key={r}>
            <line x1={padL} x2={W - padR} y1={Y(r)} y2={Y(r)} stroke="rgba(255,255,255,0.05)" />
            <text x={padL - 8} y={Y(r) + 3} fontSize="9" textAnchor="end"
              fill={r === 1 ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.3)"}>{r}</text>
          </g>
        ))}
        {Array.from({ length: weeks }, (_, w) => w).filter((w) => w % Math.ceil(weeks / 8) === 0 || w === last).map((w) => (
          <text key={w} x={X(w)} y={H - 8} fontSize="8.5" textAnchor="middle" fill="rgba(255,255,255,0.35)">
            {w === 0 ? `wk 1` : date(w)}
          </text>
        ))}
        {[...shown].reverse().map((p) => {
          const rk = ranks[p.id];
          const hi = rk[last] <= 3;
          // break the line where the rookie falls off the chart
          const segs: string[][] = [[]];
          rk.forEach((r, w) => {
            if (r <= cap) segs[segs.length - 1].push(`${X(w).toFixed(1)},${Y(r).toFixed(1)}`);
            else if (segs[segs.length - 1].length) segs.push([]);
          });
          return (
            <g key={p.id} opacity={hi ? 1 : 0.45}>
              {segs.filter((s) => s.length > 1).map((s, i) => (
                <polyline key={i} points={s.join(" ")} fill="none" stroke={p.color}
                  strokeWidth={hi ? 2.4 : 1.4} strokeLinejoin="round" />
              ))}
              {rk.map((r, w) => r <= cap && (
                <circle key={w} cx={X(w)} cy={Y(r)} r={hi ? 2.6 : 1.8} fill={p.color}>
                  <title>{`${p.name} · week ending ${date(w)} · #${r} · ${p.cum[w].toFixed(0)} Game Score`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        {changes.map((c) => (
          <circle key={c.w} cx={X(c.w)} cy={Y(1)} r="5" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="1.2">
            <title>{`${byId.get(c.id)?.name} takes #1 — week ending ${date(c.w)}`}</title>
          </circle>
        ))}
        {top.filter((p) => ranks[p.id][last] <= cap).map((p) => (
          <text key={p.id} x={W - padR + 8} y={Y(ranks[p.id][last]) + 3} fontSize="9.5"
            fill={ranks[p.id][last] <= 3 ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.5)"}>
            <tspan fill={p.color} fontWeight="700">■ </tspan>{p.name}
            <tspan fill="rgba(255,255,255,0.45)"> {p.cum[last].toFixed(0)}</tspan>
          </text>
        ))}
      </svg>
      <figcaption className="text-[10.5px] text-text-dim">
        <span className="text-text-secondary">{lead.name}</span> leads
        {second ? <> by {(lead.cum[last] - second.cum[last]).toFixed(0)} over {last1(second.name)}</> : null}
        {" "}and has been #1 for {weeksLed} of {weeks} week{weeks === 1 ? "" : "s"}.
        {changes.length > 1 && (
          <> Lead changes: {changes.map((c, i) => (
            <span key={c.w}>{i ? " → " : ""}{last1(byId.get(c.id)?.name ?? "")} ({date(c.w)})</span>
          ))}.</>
        )}
        {" "}Rings mark a new #1; hover any point for the week.
      </figcaption>
    </figure>
  );
}
