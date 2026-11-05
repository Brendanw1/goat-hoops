"use client";

import { useMemo, useState } from "react";
import { Court } from "./shot-chart";
import type { HoopsShotGrid } from "@/lib/data-hoops";

/**
 * Half-court FGA heat grid: the player's shots binned at 2.5 ft from the
 * mart's x/y (same space as ShotChart). Color walks a classic heat ramp with
 * density — none → violet → magenta → red → orange → yellow — quantile-binned
 * so one hot cell doesn't flatten the rest. Volume only: judgment colors
 * (pos/neg) stay out of the map, because "where he shoots" is a fact, not a
 * grade. Hover a cell for make/attempt counts.
 */

// multi-stop heat ramp (OKLCH for perceptual evenness on the dark surface)
const RAMP = [
  "oklch(0.25 0.05 300)", // cold end: deep violet, barely above the court
  "oklch(0.35 0.13 300)", // violet
  "oklch(0.45 0.19 335)", // magenta
  "oklch(0.55 0.21 25)",  // red
  "oklch(0.66 0.19 55)",  // orange
  "oklch(0.80 0.16 90)",  // yellow — the hot end
];

export function ShotHeatMap({ grid, label }: { grid: HoopsShotGrid; label: string }) {
  const [hover, setHover] = useState<{ ix: number; iy: number; fga: number; fgm: number } | null>(null);
  const B = 2.5;
  // quantile edges over cell volume, so the ramp distributes across the map
  const edges = useMemo(() => {
    const v = grid.cells.map((c) => c[2]).sort((a, b) => a - b);
    if (!v.length) return [1];
    return [0.35, 0.6, 0.78, 0.9, 1].map((p) => v[Math.floor(p * (v.length - 1))]);
  }, [grid]);
  const bin = (fga: number) => edges.findIndex((e) => fga <= e);
  const fgPct = grid.n > 0 ? Math.round((grid.fgm / grid.n) * 100) : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] text-text-dim">
        <span className="tabular-nums">{grid.n} FGA · {fgPct != null ? `${fgPct}% FG` : ""} · {label}</span>
        <span className="ml-auto">violet → yellow = attempt density</span>
      </div>
      <svg viewBox="-1 -6 52 54" className="w-full max-w-md mx-auto">
        <Court />
        {grid.cells.map(([ix, iy, fga, fgm], i) => (
          <rect key={i} x={ix * B} y={iy * B} width={B} height={B}
            fill={RAMP[Math.min(Math.max(bin(fga), 0), RAMP.length - 1)]}
            opacity={0.92}
            stroke="rgba(15,23,42,0.5)" strokeWidth={0.15}
            onMouseEnter={() => setHover({ ix, iy, fga, fgm })}
            onMouseLeave={() => setHover(null)} />
        ))}
      </svg>
      <div className="flex items-center justify-center gap-1" aria-hidden>
        {RAMP.map((c, i) => (
          <span key={i} className="inline-block w-8 h-2 rounded-sm" style={{ background: c }} />
        ))}
        <span className="text-[10px] text-text-dim ml-1.5">fewer → more</span>
      </div>
      <div className="h-4 text-[11px] text-text-dim text-center truncate">
        {hover
          ? `${hover.fga} FGA · ${hover.fgm} made · ${Math.round((hover.fgm / hover.fga) * 100)}% · ${(hover.ix * B).toFixed(0)}ft × ${(hover.iy * B).toFixed(0)}ft`
          : "hover a cell for attempts / makes"}
      </div>
    </div>
  );
}
