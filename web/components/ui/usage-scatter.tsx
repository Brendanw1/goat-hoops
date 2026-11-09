import { teamColor } from "@/lib/team-colors";

/**
 * Usage vs efficiency — the offensive-role map. x = usage rate (share of
 * possessions used while on), y = true shooting, dot area ∝ estimated total
 * minutes, dot color = TEAM (identity channel). Pure SVG, zero client JS;
 * hover any dot for its line. Quadrant splits at the pool's own medians —
 * the labels are names for regions, not grades.
 */
export type ScatterRow = {
  id: string; name: string; team: string | null;
  usg: number; ts: number; gp: number; min: number;
};

const med = (v: number[]) => {
  const s = [...v].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
};

export function UsageScatter({ pool, seasonLabel }: {
  pool: ScatterRow[]; seasonLabel: string;
}) {
  if (pool.length < 20) {
    return (
      <p className="text-xs text-text-dim">
        Not enough qualified players with usage/TS data yet — the map appears as the
        season&apos;s sample grows.
      </p>
    );
  }
  const W = 760, H = 420, padL = 44, padR = 16, padT = 18, padB = 40;
  const xs = pool.map((p) => p.usg), ys = pool.map((p) => p.ts);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const xm = med(xs), ym = med(ys);
  const X = (v: number) => padL + ((v - x0) / (x1 - x0)) * (W - padL - padR);
  const Y = (v: number) => H - padB - ((v - y0) / (y1 - y0)) * (H - padT - padB);
  const mMax = Math.max(...pool.map((p) => p.gp * p.min), 1);

  // labeled outliers: extreme usage or efficiency on real minutes (max 7,
  // staggered above/below the dot; the X guard is wide — last names run long)
  const usgHi = med(xs.filter((v) => v > xm)), tsHi = med(ys.filter((v) => v > ym));
  const lastName = (n: string) => {
    const t = n.split(" ").filter((w) => !/^(Jr\.?|Sr\.?|II|III|IV|V)$/i.test(w));
    return t[t.length - 1];
  };
  const ranked = [...pool].sort(
    (a, b) => (b.usg > usgHi ? b.usg * 100 : 0) + (b.ts > tsHi ? b.ts * 100 : 0)
            - ((a.usg > usgHi ? a.usg * 100 : 0) + (a.ts > tsHi ? a.ts * 100 : 0)));
  const labeled: ScatterRow[] = [];
  for (const r of ranked) {
    if (labeled.length >= 7) break;
    const near = labeled.some((l) =>
      Math.abs(X(l.usg) - X(r.usg)) < 76 && Math.abs(Y(l.ts) - Y(r.ts)) < 18);
    if (!near) labeled.push(r);
  }

  return (
    <figure className="space-y-1.5">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label="usage vs true shooting">
        {/* median splits + quadrant names */}
        <line x1={X(xm)} y1={padT - 4} x2={X(xm)} y2={H - padB}
          stroke="rgba(255,255,255,0.14)" strokeDasharray="3 4" />
        <line x1={padL} y1={Y(ym)} x2={W - padR} y2={Y(ym)}
          stroke="rgba(255,255,255,0.14)" strokeDasharray="3 4" />
        {[
          { x: X(x1) - 2, y: Y(y1) + 12, t: "engines — load and efficiency", a: "end" },
          { x: X(x0) + 2, y: Y(y1) + 12, t: "finishers — efficiency off the ball", a: "start" },
          { x: X(x1) - 2, y: Y(y0) - 10, t: "carrying it anyway", a: "end" },
          { x: X(x0) + 2, y: Y(y0) - 10, t: "role minutes", a: "start" },
        ].map((q) => (
          <text key={q.t} x={q.x} y={q.y} fontSize="9" fill="rgba(255,255,255,0.4)"
            textAnchor={q.a as "end" | "start"}>{q.t}</text>
        ))}
        {/* dots */}
        {pool.map((p) => (
          <circle key={p.id} cx={X(p.usg)} cy={Y(p.ts)}
            r={2 + 4.4 * Math.sqrt((p.gp * p.min) / mMax)}
            fill={teamColor(p.team) ?? "rgba(255,255,255,0.4)"} opacity="0.72"
            stroke="rgba(0,0,0,0.35)" strokeWidth="0.5">
            <title>{`${p.name} · ${p.team ?? "?"} — ${Math.round(p.usg * 1000) / 10}% usage · ${Math.round(p.ts * 1000) / 10}% TS · ${p.gp} gp · ${p.min} mpg`}</title>
          </circle>
        ))}
        {/* outlier labels */}
        {labeled.map((p, k) => (
          <text key={p.id} x={X(p.usg)} y={Y(p.ts) + (k % 2 ? -9 : 15)} fontSize="9"
            fill="rgba(255,255,255,0.85)" textAnchor="middle" fontWeight="600">
            {lastName(p.name)}
          </text>
        ))}
        {/* axes */}
        <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="rgba(255,255,255,0.3)" />
        <line x1={padL} y1={padT - 4} x2={padL} y2={H - padB} stroke="rgba(255,255,255,0.3)" />
        {[x0, xm, x1].map((v) => (
          <text key={`x${v}`} x={X(v)} y={H - padB + 13} fontSize="8.5"
            fill="rgba(255,255,255,0.35)" textAnchor="middle">{`${Math.round(v * 1000) / 10}%`}</text>
        ))}
        {[y0, ym, y1].map((v) => (
          <text key={`y${v}`} x={padL - 6} y={Y(v) + 3} fontSize="8.5"
            fill="rgba(255,255,255,0.35)" textAnchor="end">{`${Math.round(v * 1000) / 10}%`}</text>
        ))}
        <text x={(padL + W - padR) / 2} y={H - 6} fontSize="9" fill="rgba(255,255,255,0.45)"
          textAnchor="middle">usage rate — share of team possessions used while on court</text>
        <text x={13} y={(padT + H - padB) / 2} fontSize="9" fill="rgba(255,255,255,0.45)"
          textAnchor="middle" transform={`rotate(-90 13 ${(padT + H - padB) / 2})`}>true shooting</text>
      </svg>
      <figcaption className="text-[10.5px] text-text-dim">
        {pool.length} qualified players, {seasonLabel} · dashed lines are the pool&apos;s medians ·
        {" "}dot size ∝ minutes · dot color = team · hover any dot for its line.
      </figcaption>
    </figure>
  );
}
