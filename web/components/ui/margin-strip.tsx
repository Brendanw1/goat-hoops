/**
 * Season margin strip — every game's scoring margin as a bar around the zero
 * line (green won, red lost, height = margin), the season mean dashed gold.
 * The season's shape — streaks, blowouts, heartbreaks — in one strip.
 * Judgment colors here are correct: W/L is a fact. Pure SVG, zero client JS.
 */
export function MarginStrip({ games }: {
  games: { pts: number; opp_pts: number; res: string }[];
}) {
  if (!games.length) return null;
  const W = 720, H = 96, pad = 6;
  const margins = games.map((g) => g.pts - g.opp_pts);
  const mMax = Math.max(28, ...margins.map((m) => Math.abs(m)));
  const mean = margins.reduce((a, b) => a + b, 0) / margins.length;
  const bw = (W - 2 * pad) / games.length;
  const Y = (m: number) => H / 2 - (m / mMax) * (H / 2 - 8);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
      aria-label="season margin strip">
      <line x1={pad} y1={H / 2} x2={W - pad} y2={H / 2} stroke="rgba(255,255,255,0.25)" />
      <line x1={pad} y1={Y(mean)} x2={W - pad} y2={Y(mean)}
        stroke="var(--color-usf-gold)" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.75" />
      <text x={W - pad - 2} y={Y(mean) - 3} fontSize="8.5" fill="var(--color-usf-gold)"
        textAnchor="end" opacity="0.9">mean {mean > 0 ? "+" : ""}{mean.toFixed(1)}</text>
      {margins.map((m, i) => {
        const win = m > 0;
        const top = m >= 0 ? Y(m) : H / 2;
        return (
          <rect key={i} x={pad + i * bw + 0.6} y={top}
            width={Math.max(bw - 1.2, 1.4)} height={Math.max(Math.abs(H / 2 - Y(m)), 1)}
            fill={win ? "var(--color-pos)" : "var(--color-neg)"}
            opacity={0.62 + 0.3 * (Math.abs(m) / mMax)} rx="1" />
        );
      })}
      <text x={pad} y={10} fontSize="8.5" fill="rgba(255,255,255,0.4)">
        margin by game, first → latest · green won, red lost
      </text>
    </svg>
  );
}
