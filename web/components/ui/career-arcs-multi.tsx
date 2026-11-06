/**
 * Two players' career arcs on one axis, aligned by career year (each player's
 * first baked season = year 1) so different eras compare honestly — a 2005
 * rookie and a 2018 rookie both start at x=1. PPG solid in the top band, TS%
 * dashed in the bottom; green = player A, gold = player B (the site's brand
 * pair — the judgment colors pos/neg/flag stay out of identity). Hovers carry
 * the real season, age, and line. Server-renderable: hover is <title>, no hooks.
 */
const seasonLabel = (s: number) => `${s - 1}-${String(s).slice(2)}`;

const fnum = (v: number | null | undefined, dp = 1) =>
  typeof v === "number" ? v.toFixed(dp) : "—";

export function MultiCareerArc({ a, b, aName, bName }: {
  a?: number[][]; b?: number[][]; aName: string; bName: string;
}) {
  if (!a?.length && !b?.length) return null;
  const W = 560, padL = 26, padR = 12, gapT = 8;
  const hPpg = 78, hTs = 62, hAxis = 18, padT = 6;
  const H = padT + hPpg + gapT + hTs + hAxis;
  const n = Math.max(a?.length ?? 0, b?.length ?? 0);
  const step = (W - padL - padR) / n;
  const maxP = Math.max(
    ...(a ?? []).map((r) => r[4] ?? 0), ...(b ?? []).map((r) => r[4] ?? 0), 10);
  const yPpg = (v: number) => padT + hPpg * (1 - v / maxP);
  const tsLo = 0.42, tsHi = 0.75;
  const yTs = (v: number) => padT + hPpg + gapT + hTs * (1 - (v - tsLo) / (tsHi - tsLo));
  const xc = (i: number) => padL + step * (i + 0.5);
  const poly = (rows: number[][], y: (v: number) => number, pick: (r: number[]) => number | null) =>
    rows.map((r, i) => (pick(r) != null ? `${xc(i)},${y(pick(r)!)}` : null))
      .filter((s): s is string => s !== null).join(" ");
  const line = (rows: number[][] | undefined, color: string, dashed: boolean, pick: (r: number[]) => number | null, y: (v: number) => number, tip: (r: number[]) => string) => (
    <>
      {rows && rows.length > 1 && (
        <polyline points={poly(rows, y, pick)} fill="none" strokeWidth="1.5"
          strokeDasharray={dashed ? "3 2.4" : undefined}
          className={`stroke-current ${color}`} />
      )}
      {rows?.map((r, i) => pick(r) != null ? (
        <circle key={i} cx={xc(i)} cy={y(pick(r)!)} r={2.2}
          className={`fill-current ${color}`}>
          <title>{tip(r)}</title>
        </circle>
      ) : null)}
    </>
  );

  const ppgTip = (r: number[]) =>
    `${seasonLabel(r[0])} (age ${r[1] ?? "—"}) · ${r[2]} gp · ${fnum(r[4])} ppg · ${fnum(r[5])} rpg · ${fnum(r[6])} apg`;
  const tsTip = (r: number[]) =>
    `${seasonLabel(r[0])} (age ${r[1] ?? "—"}) · TS ${r[7] != null ? (r[7] * 100).toFixed(1) : "—"}% · USG ${r[8] != null ? (r[8] * 100).toFixed(1) : "—"}%`;

  return (
    <div>
      <div className="flex gap-3 text-[10px] text-text-dim mb-1">
        <span><span className="inline-block w-2 h-2 rounded-full bg-current text-usf-green align-middle" /> {aName}</span>
        <span><span className="inline-block w-2 h-2 rounded-full bg-current text-usf-gold align-middle" /> {bName}</span>
        <span className="text-text-dim/60">solid = ppg · dashed = TS%</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Career ppg and true-shooting arcs for ${aName} and ${bName}, aligned by career year`}>
        <text x={2} y={padT + 10} className="fill-current text-text-dim" fontSize="9">ppg</text>
        <line x1={padL} x2={W - padR} y1={yPpg(0)} y2={yPpg(0)}
          className="stroke-current text-white/10" strokeWidth="1" />
        {line(a, "text-usf-green", false, (r) => r[4], yPpg, ppgTip)}
        {line(b, "text-usf-gold", false, (r) => r[4], yPpg, ppgTip)}
        <text x={2} y={padT + hPpg + gapT + 10} className="fill-current text-text-dim" fontSize="9">TS%</text>
        {line(a, "text-usf-green", true, (r) => r[7], yTs, tsTip)}
        {line(b, "text-usf-gold", true, (r) => r[7], yTs, tsTip)}
        <line x1={padL} x2={W - padR} y1={padT + hPpg + gapT + hTs + 6} y2={padT + hPpg + gapT + hTs + 6}
          className="stroke-current text-white/10" strokeWidth="1" />
        <text x={padL} y={H - 2} fontSize="9" className="fill-current text-text-dim">1st season</text>
        <text x={W - padR} y={H - 2} fontSize="9" textAnchor="end" className="fill-current text-text-dim">
          {`${n}th`}
        </text>
      </svg>
    </div>
  );
}
