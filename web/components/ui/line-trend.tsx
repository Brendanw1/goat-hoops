/**
 * Multi-series game-by-game trend: one line per leader in that player's TEAM
 * color (identity channel), dots at games, end labels with the last value.
 * Pure SVG, zero client JS. Y axis auto-scales from the data.
 */
export function LineTrend({ series, unit, xLabel = "games played" }: {
  series: { name: string; color: string; badge?: string;
            points: (number | null)[];
            /** one hover label per point (game context), same length as points */
            labels?: (string | null)[] }[];
  unit?: string;
  xLabel?: string;
}) {
  const W = 720, H = 190, padL = 30, padR = 108, padT = 12, padB = 20;
  const nMax = Math.max(...series.map((s) => s.points.length), 2);
  const vals = series.flatMap((s) => s.points.filter((v): v is number => v != null));
  const vMax = Math.max(...vals, 1) * 1.08;
  const X = (i: number) => padL + (i / (nMax - 1)) * (W - padL - padR);
  const Y = (v: number) => H - padB - (v / vMax) * (H - padT - padB);

  // end labels staggered so close finishers don't collide
  const ends: { s: (typeof series)[number]; last: { v: number; i: number }; yNudge?: number }[] =
    series.map((s) => {
      const pts = s.points.map((v, i) => ({ v, i })).filter((d): d is { v: number; i: number } => d.v != null);
      return { s, last: pts[pts.length - 1] };
    }).sort((a, b) => Y(a.last.v) - Y(b.last.v));
  for (let k = 1; k < ends.length; k++) {
    const minGap = 11;
    if (Y(ends[k].last.v) - Y(ends[k - 1].last.v) < minGap) {
      ends[k].yNudge = Y(ends[k - 1].last.v) + minGap - Y(ends[k].last.v);
    }
  }
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
        const nudge = ends.find((e) => e.s === s)?.yNudge ?? 0;
        return (
          <g key={s.name}>
            <polyline points={pts.map((d) => `${X(d.i)},${Y(d.v)}`).join(" ")}
              fill="none" stroke={s.color} strokeWidth="1.6" opacity="0.9" />
            {pts.map((d) => (
              <circle key={d.i} cx={X(d.i)} cy={Y(d.v)} r="2.1" fill={s.color}>
                <title>{s.labels?.[d.i] ?? `${s.name} — game ${d.i + 1}: ${d.v}${unit ? ` ${unit}` : ""}`}</title>
              </circle>
            ))}
            <circle cx={X(last.i)} cy={Y(last.v)} r="3.1" fill={s.color}>
              <title>{s.labels?.[last.i] ?? `${s.name}: ${last.v}${unit ? ` ${unit}` : ""}`}</title>
            </circle>
            {s.badge && (
              <text x={W - padR + 6} y={Y(last.v) + 3.5 + nudge} fontSize="10"
                fill={s.color} fontWeight="800">{s.badge}</text>
            )}
            <text x={W - padR + (s.badge ? 22 : 6)} y={Y(last.v) + 3 + nudge} fontSize="9"
              fill="rgba(255,255,255,0.82)" fontWeight="600">
              {s.name} {last.v}{unit ? ` ${unit}` : ""}
            </text>
          </g>
        );
      })}
      {/* x axis: label + game ticks */}
      <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB}
        stroke="rgba(255,255,255,0.3)" />
      {Array.from({ length: Math.min(nMax, 8) }, (_, k) => {
        const i = Math.round((k / Math.max(Math.min(nMax, 8) - 1, 1)) * (nMax - 1));
        return (
          <text key={i} x={X(i)} y={H - padB + 12} fontSize="8.5"
            fill="rgba(255,255,255,0.35)" textAnchor="middle">{i + 1}</text>
        );
      })}
      <text x={(padL + W - padR) / 2} y={H - 4} fontSize="9"
        fill="rgba(255,255,255,0.45)" textAnchor="middle">{xLabel}</text>
    </svg>
  );
}
