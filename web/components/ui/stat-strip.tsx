/**
 * One stat's league distribution as a strip: every qualified player is a dot
 * at their value, colored on the shared percentile scale (lib/tone.ts), the
 * rows shown in the table below drawn full-strength. Pure SVG, zero client
 * JS; hover any dot for its line. The table is the accessible view.
 */
export type StripPoint = { id: string; name: string; v: number; pct: number | null };

const fillTone = (p: number | null) =>
  p == null ? "fill-white/40" : p >= 0.9 ? "fill-elite" : p >= 0.75 ? "fill-pos"
    : p <= 0.25 ? "fill-neg" : "fill-white/60";

export function StatStrip({ points, shown, fmt, label, lower = false }: {
  points: StripPoint[]; shown: Set<string>; fmt: (v: number) => string; label: string;
  lower?: boolean;
}) {
  if (points.length < 10) return null;
  const W = 760, H = 120, padX = 20, base = 78;
  const vs = points.map((p) => p.v);
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const sorted = [...vs].sort((a, b) => a - b);
  const med = sorted[Math.floor(sorted.length / 2)];
  const X = (v: number) => padX + (hi === lo ? 0.5 : (v - lo) / (hi - lo)) * (W - 2 * padX);
  // deterministic vertical spread so dense middles stay readable
  const jit = (id: string) => {
    let h = 0;
    for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return ((h % 1000) / 1000 - 0.5) * 44;
  };
  const best = [...points].sort((a, b) => (lower ? a.v - b.v : b.v - a.v)).slice(0, 3);
  const last = (n: string) => n.split(" ").filter((w) => !/^(Jr\.?|Sr\.?|II|III|IV)$/i.test(w)).pop();
  // background dots first, the table's rows on top
  const ordered = [...points].sort((a, b) => Number(shown.has(a.id)) - Number(shown.has(b.id)));

  return (
    <figure className="space-y-1">
      <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[560px]" role="img"
        aria-label={`${label} distribution across ${points.length} qualified players`}>
        <line x1={X(med)} y1={base - 34} x2={X(med)} y2={base + 26}
          stroke="rgba(255,255,255,0.18)" strokeDasharray="3 4" />
        <line x1={padX} y1={base + 26} x2={W - padX} y2={base + 26} stroke="rgba(255,255,255,0.25)" />
        {ordered.map((p) => {
          const on = shown.has(p.id);
          return (
            <circle key={p.id} cx={X(p.v)} cy={base + jit(p.id) * 0.5} r={on ? 4.5 : 3.2}
              className={fillTone(p.pct)} opacity={on ? 0.95 : 0.3}
              stroke={on ? "rgba(0,0,0,0.6)" : "none"} strokeWidth="1.5">
              <title>{`${p.name} — ${fmt(p.v)}${p.pct != null ? ` · ${Math.round(p.pct * 100)}th pct` : ""}`}</title>
            </circle>
          );
        })}
        {best.map((p, k) => (
          <text key={p.id} x={X(p.v)} y={base - 40 + (k % 2) * 10} fontSize="9.5" fontWeight="600"
            fill="rgba(255,255,255,0.85)" textAnchor={X(p.v) > W - 70 ? "end" : X(p.v) < 70 ? "start" : "middle"}>
            {last(p.name)}
          </text>
        ))}
        {[lo, med, hi].map((v, k) => (
          <text key={k} x={X(v)} y={H - 4} fontSize="9" fill="rgba(255,255,255,0.4)"
            textAnchor={k === 0 ? "start" : k === 2 ? "end" : "middle"}>
            {k === 1 ? `median ${fmt(v)}` : fmt(v)}
          </text>
        ))}
      </svg>
      </div>
      <figcaption className="text-[10.5px] text-text-dim">
        {points.length} qualified players · each dot one player, colored by percentile
        (blue top 10%, green top 25%, red bottom 25%) · the table&apos;s rows are drawn solid ·
        hover any dot.
      </figcaption>
    </figure>
  );
}
