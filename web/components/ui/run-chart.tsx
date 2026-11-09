import { teamColor } from "@/lib/team-colors";

/**
 * The run of play — score margin (home-positive) over game time, built from
 * the baked play feed. Pure SVG, zero client JS; hover detail via native
 * <title> on the milestone dots. Identity colors: the area above zero is the
 * HOME team's lead, below zero the AWAY team's (team colors only — margin
 * sign is a fact, not a judgment).
 */

type Play = { p: number; t: number | null; hs: number | null; as: number | null; a?: string | null };
type Pt = { x: number; m: number; hs: number; as: number; p: number; t: number | null; scored: boolean };

const periodOffset = (p: number) => (p <= 4 ? (p - 1) * 720 : 2880 + (p - 5) * 300);
const periodLen = (p: number) => (p <= 4 ? 720 : 300);
const periodName = (p: number) => (p <= 4 ? `Q${p}` : `${p - 4}OT`);
const clock = (sec: number | null) =>
  sec == null ? "" : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`;

function marginPoints(plays: Play[]): Pt[] {
  /** plays → game-time (sec) + margin series. Scores forward-fill (the feed
   *  nulls them on non-scoring rows); t forward-fills per period; x is forced
   *  monotonic — feed order is truth, the clock is decoration. */
  const out: Pt[] = [];
  let lastX = -1;
  for (const pl of plays) {
    const prev = out[out.length - 1];
    const hs = pl.hs ?? prev?.hs ?? 0;
    const as = pl.as ?? prev?.as ?? 0;
    let x = periodOffset(pl.p) + (pl.t ?? prev?.t ?? 0);
    if (x <= lastX) x = lastX + 1;
    lastX = x;
    out.push({
      x, m: hs - as, hs, as, p: pl.p, t: pl.t ?? prev?.t ?? null,
      scored: prev != null && (hs !== prev.hs || as !== prev.as),
    });
  }
  return out;
}

export function runChartStats(plays: Play[]) {
  /** the arena-stats trio from the feed: lead changes (a tie then the SAME
   *  leader resuming is NOT a change), ties, largest lead, longest run. */
  const pts = marginPoints(plays);
  const events = pts.filter((d) => d.scored);
  let lead = 0, changes = 0, ties = 0, maxLead = 0, maxLeadSide = "";
  for (const d of events) {
    if (d.m !== 0) {
      const s = Math.sign(d.m);
      if (lead !== 0 && s !== lead) changes += 1;
      lead = s;
    } else ties += 1;
    if (Math.abs(d.m) > maxLead) { maxLead = Math.abs(d.m); maxLeadSide = d.m > 0 ? "home" : "away"; }
  }
  // longest run: consecutive scoring plays by one side (opponent scoreless)
  let best = { pts: 0, side: "", from: pts[0], to: pts[0] };
  let cur = { pts: 0, side: "", from: pts[0], to: pts[0] };
  for (let k = 0; k < events.length; k++) {
    const d = events[k], pm = k > 0 ? events[k - 1].m : 0;
    const side = d.m > pm ? "home" : "away";
    const add = Math.abs(d.m - pm);
    if (side === cur.side) cur = { ...cur, pts: cur.pts + add, to: d };
    else cur = { pts: add, side, from: k > 0 ? events[k - 1] : d, to: d };
    if (cur.pts > best.pts) best = cur;
  }
  return { changes, ties, maxLead, maxLeadSide, best, events };
}

export function RunChart({ plays, home, away }: {
  plays: Play[]; home: string | null; away: string | null;
}) {
  const hc = teamColor(home) ?? "#7c9cff";
  const ac = teamColor(away) ?? "#ff9c7c";
  const pts = marginPoints(plays);
  if (pts.length < 2) return null;
  const { changes, ties, maxLead, maxLeadSide, best, events } = runChartStats(plays);
  const last = pts[pts.length - 1];

  const W = 760, H = 210, padL = 40, padR = 14, padT = 16, padB = 24;
  const gameLen = periodOffset(last.p) + periodLen(last.p);
  const yMax = Math.max(8, Math.max(...pts.map((d) => Math.abs(d.m)), 1) * 1.15);
  const X = (x: number) => padL + (x / gameLen) * (W - padL - padR);
  const Y = (m: number) => H - padB - ((m + yMax) / (2 * yMax)) * (H - padT - padB);
  const zeroY = Y(0);
  const line = pts.map((d) => `${X(d.x).toFixed(1)},${Y(d.m).toFixed(1)}`);
  const area = `M${X(pts[0].x).toFixed(1)},${zeroY.toFixed(1)} L${line.join(" L")} L${X(last.x).toFixed(1)},${zeroY.toFixed(1)} Z`;

  // lead-change dots: same tie rule as the stat (last non-zero sign must flip)
  const crossings: Pt[] = [];
  let lastSign = 0;
  for (const d of events) {
    if (d.m === 0) continue;
    const s = Math.sign(d.m);
    if (lastSign !== 0 && s !== lastSign) crossings.push(d);
    lastSign = s;
  }
  const peak = pts.reduce((b, d) => (Math.abs(d.m) > Math.abs(b.m) ? d : b), pts[0]);
  const nPeriods = Math.max(...plays.map((p) => p.p));

  return (
    <figure className="space-y-1.5">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label="score margin over game time">
        <defs>
          <clipPath id="rc-above"><rect x="0" y="0" width={W} height={zeroY} /></clipPath>
          <clipPath id="rc-below"><rect x="0" y={zeroY} width={W} height={H - zeroY} /></clipPath>
        </defs>
        {Array.from({ length: nPeriods }, (_, k) => k + 1).map((p) => (
          <g key={p}>
            <line x1={X(periodOffset(p))} y1={padT - 6} x2={X(periodOffset(p))} y2={H - padB}
              stroke="rgba(255,255,255,0.06)" />
            <text x={X(periodOffset(p) + periodLen(p) / 2)} y={H - padB + 12} fontSize="8.5"
              fill="rgba(255,255,255,0.35)" textAnchor="middle">{periodName(p)}</text>
          </g>
        ))}
        {[-1, -0.5, 0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={padL} y1={Y(yMax * f)} x2={W - padR} y2={Y(yMax * f)}
              stroke={f === 0 ? "rgba(255,255,255,0.22)" : "rgba(255,255,255,0.05)"} />
            <text x={padL - 5} y={Y(yMax * f) + 3} fontSize="8.5"
              fill="rgba(255,255,255,0.35)" textAnchor="end">
              {f === 0 ? "0" : Math.round(yMax * f) > 0 ? `+${Math.round(yMax * f)}` : Math.round(yMax * f)}
            </text>
          </g>
        ))}
        <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY} stroke="rgba(255,255,255,0.22)" />
        <path d={area} fill={hc} opacity="0.16" clipPath="url(#rc-above)" />
        <path d={area} fill={ac} opacity="0.16" clipPath="url(#rc-below)" />
        {best.pts >= 8 && (
          <rect x={X(best.from.x)} y={padT - 6} width={Math.max(X(best.to.x) - X(best.from.x), 1.5)}
            height={H - padT - padB + 6} fill={best.side === "home" ? hc : ac} opacity="0.10" />
        )}
        <polyline points={line.join(" ")} fill="none" stroke="rgba(255,255,255,0.72)" strokeWidth="1.4" />
        {crossings.map((d, k) => (
          <circle key={`c${k}`} cx={X(d.x)} cy={Y(d.m)} r="2.4" fill="#0b0e14"
            stroke="rgba(255,255,255,0.85)" strokeWidth="1">
            <title>{`${d.m > 0 ? home : away} takes the lead — ${periodName(d.p)} ${clock(d.t)} (${d.hs}-${d.as})`}</title>
          </circle>
        ))}
        <circle cx={X(peak.x)} cy={Y(peak.m)} r="2.8" fill={peak.m > 0 ? hc : ac}
          stroke="rgba(255,255,255,0.7)" strokeWidth="0.8">
          <title>{`Largest lead: ${peak.m > 0 ? home : away} by ${Math.abs(peak.m)} — ${periodName(peak.p)} ${clock(peak.t)} (${peak.hs}-${peak.as})`}</title>
        </circle>
        <circle cx={X(last.x)} cy={Y(last.m)} r="3"
          fill={last.m > 0 ? hc : last.m < 0 ? ac : "rgba(255,255,255,0.6)"}>
          <title>{`Final: ${away} ${last.as} @ ${home} ${last.hs}`}</title>
        </circle>
        <text x={padL} y={padT - 5} fontSize="9" fill={hc} fontWeight="700">▲ {home ?? "home"}</text>
        <text x={padL + 46} y={padT - 5} fontSize="9" fill={ac} fontWeight="700">{away ?? "away"} ▼</text>
      </svg>
      <figcaption className="text-[10.5px] text-text-dim tabular-nums">
        {changes} lead change{changes === 1 ? "" : "s"} · {ties} tie{ties === 1 ? "" : "s"} ·
        {" "}largest lead {maxLeadSide === "home" ? home : away} +{maxLead}
        {best.pts >= 6 && (
          <> · longest run {best.pts}-0 {best.side === "home" ? home : away}
            {" "}({periodName(best.from.p)} {clock(best.from.t)} → {periodName(best.to.p)} {clock(best.to.t)})</>
        )}
        {" "}— ringed dots are lead changes; hover them.
      </figcaption>
    </figure>
  );
}
