/**
 * Dean Oliver's four factors as diverging bars: each bar is the team's gap to
 * the league in percentage points, drawn toward the favorable side (right =
 * helps the team, whichever direction the raw stat runs). Server rendered, no
 * client JS; each row prints the value and the gap.
 */
type Row = { label: string; v: number | null | undefined; lg: number | null | undefined; dir: 1 | -1 };

export function FourFactors({ offense, defense }: { offense: Row[]; defense: Row[] }) {
  const all = [...offense, ...defense].filter((r) => r.v != null && r.lg != null);
  const max = Math.max(...all.map((r) => Math.abs((r.v! - r.lg!) * 100)), 2);
  const bar = (r: Row) => {
    if (r.v == null || r.lg == null) return null;
    const d = (r.v - r.lg) * 100;
    const good = d * r.dir;
    const w = `${(Math.abs(good) / max) * 50}%`;
    return (
      <div key={r.label} className="flex items-center gap-2 text-[11px]">
        <span className="w-24 shrink-0 text-text-dim">{r.label}</span>
        <div className="relative h-2.5 flex-1 rounded-sm bg-white/[0.04]"
          title={`${r.label} ${(r.v * 100).toFixed(1)}% vs league ${(r.lg * 100).toFixed(1)}%`}>
          <div className="absolute inset-y-0 left-1/2 w-px bg-white/25" />
          <div className={`absolute inset-y-0 rounded-sm ${good >= 0 ? "bg-pos/70 left-1/2" : "bg-neg/70 right-1/2"}`}
            style={{ width: w }} />
        </div>
        <span className="w-12 text-right tabular-nums text-text-primary">{(r.v * 100).toFixed(1)}%</span>
        <span className={`w-12 text-right tabular-nums ${good >= 0 ? "text-pos" : "text-neg"}`}>
          {d > 0 ? "+" : ""}{d.toFixed(1)}
        </span>
      </div>
    );
  };
  return (
    <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
      <div className="space-y-1">
        <p className="text-[10px] text-text-dim/70 uppercase tracking-wide">Offense</p>
        {offense.map(bar)}
      </div>
      <div className="space-y-1">
        <p className="text-[10px] text-text-dim/70 uppercase tracking-wide">Defense</p>
        {defense.map(bar)}
      </div>
    </div>
  );
}
