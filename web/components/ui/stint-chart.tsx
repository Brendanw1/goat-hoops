import type { HoopsGameStints } from "@/lib/data-hoops";

/**
 * Stint chart (§22 / §22-b): every player's spells on the floor across the
 * game, one row each, bars colored by the team's plus-minus during the spell.
 * Quarter rules; overtime extends the axis. Pure SVG; scrolls inside its own
 * box on phones.
 */
const clockOf = (g: number) => {
  const reg = g < 2880;
  const p = reg ? Math.floor(g / 720) + 1 : 5 + Math.floor((g - 2880) / 300);
  const left = reg ? 720 - (g - (p - 1) * 720) : 300 - (g - 2880 - (p - 5) * 300);
  const q = p <= 4 ? `Q${p}` : `OT${p - 4}`;
  return `${q} ${Math.floor(left / 60)}:${String(Math.round(left % 60)).padStart(2, "0")}`;
};

export function StintChart({ stints, order }: { stints: HoopsGameStints; order: string[] }) {
  const teams = order.filter((a) => stints[a]);
  if (!teams.length) return null;
  const end = Math.max(2880, ...teams.flatMap((a) => stints[a].flatMap(([, s]) => s.map((x) => x[1]))));
  const nameW = 112, minW = 34, W = 760, rowH = 13, headH = 16, gapH = 10;
  const plotW = W - nameW - minW;
  const X = (g: number) => nameW + (g / end) * plotW;
  const periodStarts = [0, 720, 1440, 2160, ...Array.from({ length: Math.max(0, Math.round((end - 2880) / 300)) },
    (_, k) => 2880 + k * 300)];
  let y = 0;
  const blocks = teams.map((a) => {
    const top = y;
    y += headH + stints[a].length * rowH + gapH;
    return { a, top };
  });
  const H = y + 10;
  return (
    <div className="space-y-1.5">
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[620px]" role="img"
          aria-label="each player's stints on the floor, colored by plus-minus during the stint">
          {blocks.map(({ a, top }) => (
            <g key={a}>
              <text x={4} y={top + 11} fontSize="9.5" fontWeight={600} fill="rgba(255,255,255,0.8)">{a}</text>
              {periodStarts.map((g, k) => (
                <g key={g}>
                  <line x1={X(g)} x2={X(g)} y1={top + headH - 3} y2={top + headH + stints[a].length * rowH}
                    stroke="rgba(255,255,255,0.18)" />
                  <text x={X(g) + 3} y={top + 11} fontSize="7.5" fill="rgba(255,255,255,0.35)">
                    {k < 4 ? `Q${k + 1}` : `OT${k - 3}`}
                  </text>
                </g>
              ))}
              <text x={W - 2} y={top + 11} fontSize="7.5" textAnchor="end" fill="rgba(255,255,255,0.35)">min</text>
              {stints[a].map(([name, spans], i) => {
                const ry = top + headH + i * rowH;
                const mins = spans.reduce((t, [g0, g1]) => t + g1 - g0, 0) / 60;
                return (
                  <g key={name}>
                    <text x={nameW - 6} y={ry + 9} fontSize="8.5" textAnchor="end" fill="rgba(255,255,255,0.68)">
                      {name}
                    </text>
                    <line x1={nameW} x2={nameW + plotW} y1={ry + 6} y2={ry + 6} stroke="rgba(255,255,255,0.05)" />
                    {spans.map(([g0, g1, pm]) => (
                      <rect key={g0} x={X(g0)} y={ry + 1.5} width={Math.max(X(g1) - X(g0) - 0.6, 0.8)} height={rowH - 4}
                        rx="1.5" fill={pm > 0 ? "var(--color-pos)" : pm < 0 ? "var(--color-neg)" : "rgba(255,255,255,0.45)"}
                        fillOpacity={pm === 0 ? 0.5 : Math.min(0.4 + Math.abs(pm) / 12, 0.95)}>
                        <title>{`${name} · ${clockOf(g0)} to ${clockOf(g1)} · ${Math.round((g1 - g0) / 6) / 10} min · ${pm > 0 ? "+" : ""}${pm} while on`}</title>
                      </rect>
                    ))}
                    <text x={W - 2} y={ry + 9} fontSize="8.5" textAnchor="end" fill="rgba(255,255,255,0.55)"
                      style={{ fontVariantNumeric: "tabular-nums" }}>{mins.toFixed(0)}</text>
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
      </div>
      <p className="text-[10.5px] text-text-dim max-w-3xl">
        Each bar is an unbroken spell on the floor, from our substitution walk of the play-by-play (§22-b:
        within a minute of the box score in 98% of player-games). Green: the team outscored its opponent
        during the spell; red: was outscored; deeper = bigger margin. Hover a bar for the clock and the score.
      </p>
    </div>
  );
}
