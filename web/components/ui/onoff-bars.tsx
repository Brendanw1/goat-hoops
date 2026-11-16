import type { HoopsOnOffRow } from "@/lib/data-hoops";

/**
 * On/off diverging bars — each player's net-rating swing (on-court net minus
 * off-court net) as a horizontal bar from zero: green right, red left (the
 * sign is a fact; the magnitude is small-sample honest — floors applied
 * upstream). Pure SVG, zero client JS; hover for the full line.
 */
export function OnOffBars({ rows, abbr, early = false }: {
  rows: HoopsOnOffRow[]; abbr: string; early?: boolean;
}) {
  // early season: the 12 players with the most on-court possessions, in that
  // order, so the chart doesn't rank noise; later: top and bottom six by swing
  const take = [...rows].sort((a, b) => b.diff - a.diff);
  const shown = early ? [...rows].sort((a, b) => b.on_poss - a.on_poss).slice(0, 12)
    : [...take.slice(0, 6), ...take.slice(-6).reverse()].filter(
      (r, i, arr) => arr.findIndex((x) => x.pid === r.pid) === i);
  if (!shown.length) return null;
  const rng = (r: HoopsOnOffRow) => (early && r.diff_se != null ? 1.645 * r.diff_se : 0);
  const lim = Math.min(Math.max(...shown.map((r) => Math.abs(r.diff) + rng(r)), 8) * 1.08, 40);

  const W = 760, rowH = 26, padT = 6, padB = 18;
  const H = padT + padB + shown.length * rowH;
  // 132px name column: the longest qualified names ("Shai Gilgeous-Alexander")
  // must not clip — the chart's whole left edge is the name column
  const nameW = 132, valW = 46, midX = nameW + (W - nameW - valW) / 2;
  const half = (W - nameW - valW) / 2 - 8;
  const X = (d: number) => midX + (d / lim) * half;

  return (
    // the chart scrolls inside its own box under ~600 px so names stay legible on phones
    <div className="overflow-x-auto">
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[600px]" role="img"
      aria-label={`on/off net differential, ${abbr}`}>
      <line x1={midX} y1={padT - 2} x2={midX} y2={H - padB + 2} stroke="rgba(255,255,255,0.22)" />
      {shown.map((r, k) => {
        const y = padT + k * rowH + rowH / 2;
        const w = Math.max(Math.abs((r.diff / lim) * half), 1.2);
        const lo = Math.max(r.diff - rng(r), -lim), hi = Math.min(r.diff + rng(r), lim);
        const sub = `on ${r.on_net > 0 ? "+" : ""}${r.on_net.toFixed(1)} / off ${r.off_net > 0 ? "+" : ""}${r.off_net.toFixed(1)} net rtg`;
        return (
          <g key={r.pid}>
            {/* native SVG link (HTML <Link> is out-of-namespace inside <svg>) */}
            <a href={`/players/${r.pid}`}>
              <text x={nameW - 8} y={y + 3} fontSize="10" fill="rgba(255,255,255,0.82)"
                textAnchor="end" fontWeight="600" className="hover:underline">{r.name}</text>
            </a>
            <text x={nameW - 8} y={y + 12.5} fontSize="7.5" fill="rgba(255,255,255,0.3)"
              textAnchor="end">{sub}</text>
            <rect x={r.diff >= 0 ? midX : midX - w} y={y - 5} width={w} height={10}
              rx="1.5" fill={r.diff >= 0 ? "var(--color-pos)" : "var(--color-neg)"} opacity="0.75">
              <title>{`${r.name} — ${sub} · diff ${r.diff > 0 ? "+" : ""}${r.diff.toFixed(1)}${rng(r) ? ` (90% range ${(r.diff - rng(r)).toFixed(0)} to ${(r.diff + rng(r)).toFixed(0)})` : ""} over ${r.on_poss.toLocaleString()} on-court possessions (est min ${r.on_min.toLocaleString()})`}</title>
            </rect>
            {rng(r) > 0 && (
              <g stroke="rgba(255,255,255,0.45)" strokeWidth="1">
                <line x1={X(lo)} x2={X(hi)} y1={y} y2={y} />
                <line x1={X(lo)} x2={X(lo)} y1={y - 3.5} y2={y + 3.5} />
                <line x1={X(hi)} x2={X(hi)} y1={y - 3.5} y2={y + 3.5} />
              </g>
            )}
            <text x={early ? W - 2 : r.diff >= 0 ? X(r.diff) + 6 : X(r.diff) - 6} y={y + 3.5} fontSize="9.5"
              fill={r.diff >= 0 ? "var(--color-pos)" : "var(--color-neg)"}
              textAnchor={early ? "end" : r.diff >= 0 ? "start" : "end"} fontWeight="700" style={{ fontVariantNumeric: "tabular-nums" }}>
              {`${r.diff > 0 ? "+" : ""}${r.diff.toFixed(1)}`}
            </text>
          </g>
        );
      })}
      <text x={midX + half} y={H - 5} fontSize="8.5" fill="rgba(255,255,255,0.3)"
        textAnchor="end">team better with him on</text>
      <text x={midX - half} y={H - 5} fontSize="8.5" fill="rgba(255,255,255,0.3)"
        textAnchor="start">better with him off</text>
    </svg>
    </div>
  );
}
