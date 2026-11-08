/**
 * Multi-series game-by-game trend: one line per leader in that player's TEAM
 * color (identity channel), dots at games, end labels with the last value.
 * Pure SVG, zero client JS. Y axis auto-scales from the data.
 */
export function LineTrend({ series, unit }: {
  series: { name: string; color: string; points: (number | null)[] }[];
  unit?: string;
}) {
  const W = 720, H = 190, padL = 30, padR = 108, padT = 12, padB = 20;
  const nMax = Math.max(...series.map((s) => s.points.length), 2);
  const vals = series.flatMap((s) => s.points.filter((v): v is number => v != null));
  const vMax = Math.max(...vals, 1) * 1.08;
  const X = (i: number) => padL + (i / (nMax - 1)) * (W - padL - padR);
  const Y = (v: number) => H - padB - (v / vMax) * (H - padT - padB);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="leaders trend">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={padL} y1={Y(vMax * f)} x2={W - padR} y2={Y(vMax * f)}
            stroke="rgba(255,255,255,0.07)" />
          <text x={padL - 5} y={Y(vMax * f) + 3} fontSize="8.5"
            fill="rgba(255,255,255,0.35)" textAnchor="end">{Math.round(vMax * f)}</text>
        </g>
      ))}
      {series.map((s) => {
        const pts = s.points.map((v, i) => ({ v, i })).filter((d): d is { v: number; i: number } => d.v != null);
        const last = pts[pts.length - 1];
        return (
          <g key={s.name}>
            <polyline points={pts.map((d) => `${X(d.i)},${Y(d.v)}`).join(" ")}
              fill="none" stroke={s.color} strokeWidth="1.6" opacity="0.9" />
            {pts.map((d) => (
              <circle key={d.i} cx={X(d.i)} cy={Y(d.v)} r="2.1" fill={s.color} />
            ))}
            <circle cx={X(last.i)} cy={Y(last.v)} r="3.1" fill={s.color} />
            <text x={W - padR + 6} y={Y(last.v) + 3} fontSize="9" fill={s.color}>
              {s.name} {last.v}{unit ? ` ${unit}` : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
