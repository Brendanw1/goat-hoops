/**
 * Game-by-game sparkline: faint dots per game, a trailing-mean line (window
 * `w`, shorter at the season's start) and a dashed season-average rule.
 * Neutral color by rule (splits are context, not grades). Pure SVG, no client
 * JS; the label and the last value carry the numbers.
 */
export function Sparkline({ label, values, w = 10 }: { label: string; values: number[]; w?: number }) {
  const n = values.length;
  if (n < 3) return null;
  const W = 160, H = 36, pad = 3;
  const roll = values.map((_, i) => {
    const s = values.slice(Math.max(0, i - w + 1), i + 1);
    return s.reduce((a, b) => a + b, 0) / s.length;
  });
  const avg = values.reduce((a, b) => a + b, 0) / n;
  const max = Math.max(...values, 1);
  const X = (i: number) => pad + (i / (n - 1)) * (W - 2 * pad);
  const Y = (v: number) => H - pad - (v / max) * (H - 2 * pad);
  const last = roll[n - 1];
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-9 text-text-dim">{label}</span>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-9 w-40" role="img"
        aria-label={`${label}: last-${w} average ${last.toFixed(1)}, season ${avg.toFixed(1)}`}>
        <line x1={pad} x2={W - pad} y1={Y(avg)} y2={Y(avg)} stroke="rgba(255,255,255,0.25)" strokeDasharray="2 2" />
        {values.map((v, i) => <circle key={i} cx={X(i)} cy={Y(v)} r={1.1} fill="rgba(255,255,255,0.22)" />)}
        <polyline points={roll.map((v, i) => `${X(i)},${Y(v)}`).join(" ")} fill="none"
          stroke="currentColor" strokeWidth={1.4} className="text-text-secondary" />
      </svg>
      <span className="tabular-nums text-text-primary">{last.toFixed(1)}</span>
      <span className="tabular-nums text-text-dim">season {avg.toFixed(1)}</span>
    </div>
  );
}
