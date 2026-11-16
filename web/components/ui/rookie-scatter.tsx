/**
 * Production vs playing time for one rookie class: x = minutes played, y =
 * regressed BPM (§17: small samples pulled toward the league mean, so a high
 * dot on the left is signal, not a hot week). Reference rules at 0 (league
 * average) and −2 (replacement level, the VORP baseline). Team colors are
 * identity only; labels go to the best per-minute and the most-used rookies.
 */
/** "Mikel Brown Jr." -> "Brown": the last name without a generational suffix */
export const lastName = (n: string) => {
  const w = n.split(" ").filter((x) => !/^(jr\.?|sr\.?|ii|iii|iv|v)$/i.test(x));
  return w[w.length - 1] ?? n;
};

type Pt = { id: string; name: string; color: string; min: number; y: number };

export function RookieScatter({ points }: { points: Pt[] }) {
  if (points.length < 5) return null;
  const W = 760, H = 260, padL = 40, padR = 16, padT = 14, padB = 30;
  const xMax = Math.max(...points.map((p) => p.min)) * 1.05;
  const ys = points.map((p) => p.y);
  const yMin = Math.min(-4, ...ys) - 0.5, yMax = Math.max(3, ...ys) + 0.5;
  const X = (v: number) => padL + (v / xMax) * (W - padL - padR);
  const Y = (v: number) => padT + ((yMax - v) / (yMax - yMin)) * (H - padT - padB);
  const best = [...points].sort((a, b) => b.y - a.y).slice(0, 5);
  const most = [...points].sort((a, b) => b.min - a.min).slice(0, 3);
  const label = new Map([...best, ...most].map((p) => [p.id, p]));
  const placed: { x: number; y: number }[] = [];
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round((xMax * f) / 100) * 100);
  return (
    <figure className="space-y-1.5">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="rookie regressed BPM by minutes played">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={X(t)} x2={X(t)} y1={padT} y2={H - padB} stroke="rgba(255,255,255,0.04)" />
            <text x={X(t)} y={H - padB + 12} fontSize="8.5" textAnchor="middle" fill="rgba(255,255,255,0.35)">{t}</text>
          </g>
        ))}
        <text x={W - padR} y={H - 4} fontSize="8.5" textAnchor="end" fill="rgba(255,255,255,0.35)">minutes played →</text>
        {[Math.ceil(yMin), 0, Math.floor(yMax)].map((v) => (
          <text key={v} x={padL - 6} y={Y(v) + 3} fontSize="8.5" textAnchor="end" fill="rgba(255,255,255,0.35)">
            {v > 0 ? `+${v}` : v}
          </text>
        ))}
        <line x1={padL} x2={W - padR} y1={Y(0)} y2={Y(0)} stroke="rgba(255,255,255,0.3)" />
        <text x={padL + 4} y={Y(0) - 4} fontSize="8.5" fill="rgba(255,255,255,0.45)">league average</text>
        <line x1={padL} x2={W - padR} y1={Y(-2)} y2={Y(-2)} stroke="rgba(255,255,255,0.22)" strokeDasharray="3 3" />
        <text x={padL + 4} y={Y(-2) - 4} fontSize="8.5" fill="rgba(255,255,255,0.4)">replacement level</text>
        {points.map((p) => (
          <circle key={p.id} cx={X(p.min)} cy={Y(p.y)} r={label.has(p.id) ? 4 : 3} fill={p.color}
            fillOpacity={label.has(p.id) ? 0.95 : 0.55} stroke="rgba(0,0,0,0.4)" strokeWidth="0.6">
            <title>{`${p.name} · ${p.min} min · regressed BPM ${p.y > 0 ? "+" : ""}${p.y.toFixed(1)}`}</title>
          </circle>
        ))}
        {[...label.values()].map((p) => {
          let ly = Y(p.y) - 7;
          for (const q of placed) if (Math.abs(q.x - X(p.min)) < 70 && Math.abs(q.y - ly) < 10) ly = q.y - 11;
          placed.push({ x: X(p.min), y: ly });
          const right = X(p.min) > W - 120;
          return (
            <text key={p.id} x={X(p.min) + (right ? -6 : 6)} y={ly} fontSize="9" textAnchor={right ? "end" : "start"}
              fill="rgba(255,255,255,0.85)">{lastName(p.name)}</text>
          );
        })}
      </svg>
      <figcaption className="text-[10.5px] text-text-dim">
        High and to the left: producing beyond the minutes (the case for more of them). High and to the right:
        carrying a real role. Below the dashed line: replacement level so far, which is normal for a rookie.
      </figcaption>
    </figure>
  );
}
