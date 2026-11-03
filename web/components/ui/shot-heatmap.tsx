"use client";

import { useMemo, useState } from "react";
import { Court } from "./shot-chart";
import type { HoopsShotGrid } from "@/lib/data-hoops";

/**
 * Half-court FGA heat grid: the player's shots binned at 2.5 ft from the
 * mart's x/y (same space as ShotChart). Amber alpha scales with attempts in
 * the cell — density, nothing modeled. Hover a cell for make/attempt counts.
 */
export function ShotHeatMap({ grid, label }: { grid: HoopsShotGrid; label: string }) {
  const [hover, setHover] = useState<{ ix: number; iy: number; fga: number; fgm: number } | null>(null);
  const B = 2.5;
  const maxFga = useMemo(
    () => grid.cells.reduce((m, c) => Math.max(m, c[2]), 1), [grid]);
  const fgPct = grid.n > 0 ? Math.round((grid.fgm / grid.n) * 100) : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] text-text-dim">
        <span className="tabular-nums">{grid.n} FGA · {fgPct != null ? `${fgPct}% FG` : ""} · {label}</span>
        <span className="ml-auto">amber = attempt density</span>
      </div>
      <svg viewBox="-1 -6 52 54" className="w-full max-w-md mx-auto">
        <Court />
        {grid.cells.map(([ix, iy, fga, fgm], i) => (
          <rect key={i} x={ix * B} y={iy * B} width={B} height={B}
            fill={`rgba(245,158,11,${0.12 + 0.68 * (fga / maxFga)})`}
            stroke="rgba(15,23,42,0.5)" strokeWidth={0.15}
            onMouseEnter={() => setHover({ ix, iy, fga, fgm })}
            onMouseLeave={() => setHover(null)} />
        ))}
      </svg>
      <div className="h-4 text-[11px] text-text-dim text-center truncate">
        {hover
          ? `${hover.fga} FGA · ${hover.fgm} made · ${Math.round((hover.fgm / hover.fga) * 100)}% · ${(hover.ix * B).toFixed(0)}ft × ${(hover.iy * B).toFixed(0)}ft`
          : "hover a cell for attempts / makes"}
      </div>
    </div>
  );
}
