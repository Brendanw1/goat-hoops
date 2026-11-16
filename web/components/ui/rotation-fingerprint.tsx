import type { HoopsRotation } from "@/lib/data-hoops";

/**
 * Rotation fingerprint (§22 / §22-b): one row per player (top 13 by floor
 * time), one cell per regulation minute, shaded by the share of the team's
 * games he was on the floor in that minute. Quarter rules every 12 minutes;
 * the closing five (most-used five in the last 5:00 of games within 5) is
 * marked. Pure SVG; scrolls inside its own box on phones.
 */
const lastName = (n: string) => {
  const parts = n.split(" ").filter((p) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(p));
  return parts.slice(-1)[0] ?? n;
};

export function RotationFingerprint({ rot, abbr }: { rot: HoopsRotation; abbr: string }) {
  const closers = new Set(rot.close?.ids ?? []);
  // three OKC Williamses: a last name shared within the team gets its first name back
  const dup = new Set(rot.players.map((p) => lastName(p.name))
    .filter((n, i, a) => a.indexOf(n) !== i));
  const label = (n: string) => (dup.has(lastName(n)) ? n.replace(/\s+(jr\.?|sr\.?|ii|iii|iv)$/i, "") : lastName(n));
  const nameW = 104, cell = 9, gap = 1, statW = 92, padT = 16, rowH = 14;
  const W = nameW + 48 * cell + statW, H = padT + rot.players.length * rowH + 18;
  const X = (m: number) => nameW + m * cell;
  return (
    <div className="space-y-1.5">
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[620px]" role="img"
          aria-label={`${abbr} rotation: share of games each player was on the floor, minute by minute`}>
          {[0, 1, 2, 3].map((q) => (
            <text key={q} x={X(q * 12 + 6)} y={10} fontSize="8.5" textAnchor="middle"
              fill="rgba(255,255,255,0.4)">Q{q + 1}</text>
          ))}
          <text x={W - statW + 8} y={10} fontSize="8" fill="rgba(255,255,255,0.4)">min/g · stint · stints</text>
          {rot.players.map((p, i) => {
            const y = padT + i * rowH;
            return (
              <g key={p.id}>
                <a href={`/players/${p.id}`}>
                  <text x={nameW - 8} y={y + 9.5} fontSize="9" textAnchor="end"
                    fill={closers.has(p.id) ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.68)"}
                    fontWeight={closers.has(p.id) ? 600 : 400}>
                    {closers.has(p.id) ? "● " : ""}{label(p.name)}
                  </text>
                </a>
                {p.sh.map((v, m) => (
                  <rect key={m} x={X(m)} y={y + 1} width={cell - gap} height={rowH - 3} rx="1"
                    fill="var(--color-elite)" fillOpacity={v === 0 ? 0.04 : 0.08 + 0.92 * (v / 100)}>
                    <title>{`${p.name} — on the floor in minute ${m + 1} of ${v}% of ${abbr} games`}</title>
                  </rect>
                ))}
                <text x={W - statW + 8} y={y + 9.5} fontSize="8.5" fill="rgba(255,255,255,0.6)"
                  style={{ fontVariantNumeric: "tabular-nums" }}>
                  {`${p.mpg.toFixed(1)} · ${p.stint.toFixed(1)}m · ${p.spg.toFixed(1)}`}
                </text>
              </g>
            );
          })}
          {[12, 24, 36].map((m) => (
            <line key={m} x1={X(m) - gap / 2} x2={X(m) - gap / 2} y1={padT - 2} y2={H - 16}
              stroke="rgba(255,255,255,0.35)" strokeWidth="1" />
          ))}
          {[0, 6, 12, 18, 24, 30, 36, 42, 48].map((m) => (
            <text key={m} x={X(m)} y={H - 4} fontSize="7.5" textAnchor="middle" fill="rgba(255,255,255,0.3)">
              {m}
            </text>
          ))}
        </svg>
      </div>
      <p className="text-[10.5px] text-text-dim max-w-3xl">
        Brighter = on the floor in that minute in more of the team&apos;s {rot.games} games (minutes of game
        time, regulation only). Stint = average unbroken spell; stints = spells per game played.
        {rot.close && (
          <> ● Closing five: {rot.close.names.map(label).join(", ")}, on the floor for{" "}
            {Math.round(rot.close.share * 100)}% of the last five minutes of {rot.close.games} games within
            5 points.</>
        )}
      </p>
    </div>
  );
}
