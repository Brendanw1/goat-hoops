"use client";

import { useMemo, useState } from "react";
import { Court } from "./shot-chart";
import type { HoopsShotGrid } from "@/lib/data-hoops";

/**
 * Half-court FGA heat field: the player's shots binned at 2.5 ft from the
 * mart's x/y, then kernel-smoothed (σ = 2.2 ft) onto a 1-ft field and colored
 * by that field's own quantiles — no strokes, soft opacity fade at the cold
 * edge, so the map reads as a density surface instead of a blocky grid.
 * Color walks a classic heat ramp with density — none → violet → magenta →
 * red → orange → yellow. Volume only: judgment colors (pos/neg) stay out of
 * the map, because "where he shoots" is a fact, not a grade. Smoothing is
 * VISUAL ONLY: hover hits the exact 2.5-ft cell for make/attempt counts.
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

const B = 2.5;   // source bin (data)
const F = 0.75;  // render field resolution (ft)
const SIGMA = 2.6; // kernel σ (ft) — wide enough to fuse adjacent hotspots
const W = 50, H = 47;

export function ShotHeatMap({ grid, label }: { grid: HoopsShotGrid; label: string }) {
  const [hover, setHover] = useState<{ ix: number; iy: number; fga: number; fgm: number } | null>(null);
  const fgPct = grid.n > 0 ? Math.round((grid.fgm / grid.n) * 100) : null;

  // kernel-smoothed density field + per-cell ramp index / opacity
  const field = useMemo(() => {
    const nw = Math.floor(W / F), nh = Math.floor(H / F);
    const dens = new Float32Array(nw * nh);
    const s2 = 2 * SIGMA * SIGMA;
    for (const [ix, iy, fga] of grid.cells) {
      if (!fga) continue;
      const cx = ix * B + B / 2, cy = iy * B + B / 2;
      for (let fy = 0; fy < nh; fy++) {
        const dy = fy * F + F / 2 - cy;
        for (let fx = 0; fx < nw; fx++) {
          const dx = fx * F + F / 2 - cx;
          dens[fy * nw + fx] += fga * Math.exp(-(dx * dx + dy * dy) / s2);
        }
      }
    }
    const nz = Array.from(dens).filter((v) => v > 0).sort((a, b) => a - b);
    const q = (p: number) => nz[Math.floor(p * (nz.length - 1))] ?? 1;
    const edges = [0.35, 0.6, 0.78, 0.9, 1].map(q);
    const dmax = nz[nz.length - 1] ?? 1;
    // continuous position in [0, RAMP.length-1]: band b plus the fraction
    // toward band b+1 — colored via color-mix so the field has no terraces
    const pos = new Float32Array(nw * nh);
    const opa = new Float32Array(nw * nh);
    for (let i = 0; i < dens.length; i++) {
      const v = dens[i];
      if (v <= 0) { pos[i] = -1; continue; }
      let b = edges.findIndex((e) => v <= e);
      if (b < 0) b = RAMP.length - 1;
      const lo = b === 0 ? 0 : edges[b - 1];
      const hi = edges[Math.min(b, edges.length - 1)];
      const frac = hi > lo ? Math.min(1, Math.max(0, (v - lo) / (hi - lo))) : 1;
      pos[i] = Math.min(b + frac, RAMP.length - 1);
      const t = pos[i] / (RAMP.length - 1);
      // opacity rides the field's own intensity: the cold fringe fades out
      opa[i] = 0.14 + 0.78 * Math.min(1, v / (0.22 * dmax)) * (0.35 + 0.65 * t);
    }
    return { nw, nh, pos, opa };
  }, [grid]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] text-text-dim">
        <span className="tabular-nums">{grid.n} FGA · {fgPct != null ? `${fgPct}% FG` : ""} · {label}</span>
        <span className="ml-auto">violet → yellow = attempt density (smoothed)</span>
      </div>
      <svg viewBox="-1 -6 52 54" className="w-full max-w-md mx-auto">
        <Court />
        {Array.from({ length: field.nh }, (_, fy) =>
          Array.from({ length: field.nw }, (_, fx) => {
            const i = fy * field.nw + fx;
            const t = field.pos[i];
            if (t < 0) return null;
            const b = Math.min(Math.floor(t), RAMP.length - 2);
            const mix = Math.round((t - b) * 100);
            const fill = mix > 0 && b < RAMP.length - 1
              ? `color-mix(in oklab, ${RAMP[b + 1]} ${mix}%, ${RAMP[b]})`
              : RAMP[b];
            return (
              <rect key={i} x={fx * F} y={fy * F} width={F + 0.03} height={F + 0.03}
                fill={RAMP[b]} style={mix > 0 && b < RAMP.length - 1 ? { fill } : undefined}
                opacity={field.opa[i]} />
            );
          }))}
        {/* exact-count hit layer: the smoothing is visual only */}
        {grid.cells.map(([ix, iy, fga, fgm], i) => (
          <rect key={`h${i}`} x={ix * B} y={iy * B} width={B} height={B}
            fill="transparent"
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
          : "hover a cell for exact attempts / makes"}
      </div>
    </div>
  );
}
