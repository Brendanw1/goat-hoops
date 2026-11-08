/**
 * Percentile radar — the player's identity profile as a polygon on the
 * league scale. Rings at .25/.50/.75/.90 carry the judgment thresholds of
 * tone.ts (blue elite ring outermost); the league polygon fills blue, the
 * position-pool polygon overlays dashed gold. Pure SVG, zero client JS.
 */
const SIZE = 190;
const CX = SIZE / 2, CY = SIZE / 2 + 2, R = 63;

function pt(i: number, n: number, v: number): [number, number] {
  const a = (Math.PI * 2 * i) / n - Math.PI / 2;
  return [CX + Math.cos(a) * R * v, CY + Math.sin(a) * R * v];
}

export function PercentileRadar({ axes }: {
  axes: { label: string; v: number; pos?: number }[];
}) {
  const n = Math.max(axes.length, 3);
  const poly = (key: "v" | "pos") =>
    axes.map((d, i) => pt(i, n, Math.min(Math.max(d[key] ?? 0, 0.04), 1)).join(",")).join(" ");
  const hasPos = axes.some((d) => typeof d.pos === "number");
  return (
    <svg viewBox={`-6 -2 ${SIZE + 12} ${SIZE + 6}`} className="w-full max-w-[210px] mx-auto" role="img"
      aria-label="percentile radar">
      {[0.25, 0.5, 0.75, 0.9, 1].map((r) => (
        <polygon key={r}
          points={axes.map((_, i) => pt(i, n, r).join(",")).join(" ")}
          fill={r === 0.9 ? "rgba(56,130,246,0.05)" : "none"}
          stroke={r === 0.9 ? "rgba(56,130,246,0.35)" : "rgba(255,255,255,0.08)"}
          strokeWidth="0.6" />
      ))}
      {axes.map((_, i) => {
        const [x, y] = pt(i, n, 1);
        return <line key={i} x1={CX} y1={CY} x2={x} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" />;
      })}
      {hasPos && (
        <polygon points={poly("pos")} fill="none" stroke="var(--color-usf-gold)"
          strokeWidth="1.1" strokeDasharray="3 3" opacity="0.85" />
      )}
      <polygon points={poly("v")} fill="rgba(56,130,246,0.22)"
        stroke="rgba(56,130,246,0.9)" strokeWidth="1.4" />
      {axes.map((d, i) => {
        const [x, y] = pt(i, n, 1.3);
        return (
          <text key={i} x={x} y={y} fontSize="7.5"
            fill={d.v >= 0.9 ? "var(--color-elite)" : d.v >= 0.75 ? "var(--color-pos)"
              : d.v <= 0.25 ? "var(--color-neg)" : "rgba(255,255,255,0.55)"}
            textAnchor={x > CX + 6 ? "start" : x < CX - 6 ? "end" : "middle"}
            dominantBaseline="middle">
            {d.label}
          </text>
        );
      })}
    </svg>
  );
}
