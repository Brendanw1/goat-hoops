/**
 * Shot-quality quadrant — the §9 story as a picture. x = the league-expected
 * eFG of the zones the player takes (his DIET), y = actual eFG minus that
 * expectation (his MAKING). The whole league pool renders dim (dot area ∝
 * FGA); the highlighted player renders gold with the quadrant grid at the
 * pool's median diet. Pure SVG, zero client JS. Descriptive: §9's gate
 * passed; quadrant labels are names, not grades.
 */
const W = 360, H = 300, pad = 34;

export function ShotQuadrant({ pool, highlight, xMid }: {
  pool: { id: string; name: string; x: number; y: number; n: number }[];
  highlight: string;
  xMid: number;
}) {
  const xs = pool.map((p) => p.x);
  const ys = pool.map((p) => p.y);
  const x0 = Math.min(...xs, 0.4), x1 = Math.max(...xs, 0.62);
  const y0 = Math.min(...ys, -0.09), y1 = Math.max(...ys, 0.09);
  const X = (v: number) => pad + ((v - x0) / (x1 - x0)) * (W - 2 * pad);
  const Y = (v: number) => H - pad - ((v - y0) / (y1 - y0)) * (H - 2 * pad);
  const nMax = Math.max(...pool.map((p) => p.n), 1);
  const me = pool.find((p) => p.id === highlight);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
      aria-label="shot quality quadrant">
      {/* quadrant split: median diet, zero making */}
      <line x1={X(xMid)} y1={Y(y0) - 8} x2={X(xMid)} y2={Y(y1) + 8}
        stroke="rgba(255,255,255,0.16)" strokeDasharray="3 4" />
      <line x1={X(x0) - 8} y1={Y(0)} x2={X(x1) + 8} y2={Y(0)}
        stroke="rgba(255,255,255,0.16)" strokeDasharray="3 4" />
      <text x={X(x1) - 2} y={Y(y1) + 12} fontSize="8.5" fill="rgba(255,255,255,0.35)"
        textAnchor="end">easy diet, makes it</text>
      <text x={X(x0) + 2} y={Y(y1) + 12} fontSize="8.5" fill="rgba(255,255,255,0.35)"
        textAnchor="start">hard diet, makes it anyway</text>
      <text x={X(x1) - 2} y={Y(y0) - 4} fontSize="8.5" fill="rgba(255,255,255,0.35)"
        textAnchor="end">feasting</text>
      <text x={X(x0) + 2} y={Y(y0) - 4} fontSize="8.5" fill="rgba(255,255,255,0.35)"
        textAnchor="start">tough gig</text>
      {pool.filter((p) => p.id !== highlight).map((p) => (
        <circle key={p.id} cx={X(p.x)} cy={Y(p.y)}
          r={1.6 + 2.6 * Math.sqrt(p.n / nMax)}
          fill="rgba(255,255,255,0.28)" />
      ))}
      {me && (
        <g>
          <circle cx={X(me.x)} cy={Y(me.y)} r={4.2 + 3.2 * Math.sqrt(me.n / nMax)}
            fill="var(--color-usf-gold)" stroke="rgba(0,0,0,0.5)" strokeWidth="0.8" />
          <text x={X(me.x)} y={Y(me.y) - 9} fontSize="9.5" fill="var(--color-usf-gold)"
            textAnchor="middle">{me.name}</text>
        </g>
      )}
      {/* axes */}
      <line x1={X(x0)} y1={Y(y0)} x2={X(x1)} y2={Y(y0)} stroke="rgba(255,255,255,0.3)" />
      <line x1={X(x0)} y1={Y(y0)} x2={X(x0)} y2={Y(y1)} stroke="rgba(255,255,255,0.3)" />
      <text x={W / 2} y={H - 8} fontSize="9" fill="rgba(255,255,255,0.45)"
        textAnchor="middle">shot diet — league eFG of the zones he takes</text>
      <text x={11} y={H / 2} fontSize="9" fill="rgba(255,255,255,0.45)"
        textAnchor="middle" transform={`rotate(-90 11 ${H / 2})`}>making — actual eFG minus diet</text>
    </svg>
  );
}
