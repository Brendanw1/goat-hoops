import { getHoopsMarket } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const seasonLabelOf = (s: number) => `${s - 1}-${String(s).slice(2)}`;
const sgn = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;

/** implied → actual calibration: decile dots against the diagonal */
function CalibrationChart({ deciles }: {
  deciles: { p_lo: number; p_hi: number; n: number; actual: number }[];
}) {
  const W = 320, H = 320, pad = 34;
  const x = (v: number) => pad + v * (W - 2 * pad);
  const y = (v: number) => H - pad - v * (H - 2 * pad);
  const mid = (d: { p_lo: number; p_hi: number }) => (d.p_lo + d.p_hi) / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-sm">
      {/* diagonal = perfect calibration */}
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)}
        stroke="rgba(255,255,255,0.18)" strokeDasharray="3 4" />
      <text x={x(0.52)} y={y(0.42)} fill="rgba(255,255,255,0.35)" fontSize="9"
        textAnchor="middle">perfect</text>
      {deciles.map((d, i) => (
        <g key={i}>
          <circle cx={x(mid(d))} cy={y(d.actual)} r={3.4}
            fill="var(--color-usf-gold)" opacity={0.9} />
          <line x1={x(mid(d))} y1={y(d.actual)}
            x2={x(mid(d))} y2={y(mid(d))}
            stroke="rgba(255,255,255,0.22)" strokeWidth={1} />
        </g>
      ))}
      {/* axes */}
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(0)} stroke="rgba(255,255,255,0.3)" />
      <line x1={x(0)} y1={y(0)} x2={x(0)} y2={y(1)} stroke="rgba(255,255,255,0.3)" />
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <text x={x(v)} y={H - pad + 12} fill="rgba(255,255,255,0.4)" fontSize="9"
            textAnchor="middle">{v}</text>
          <text x={pad - 8} y={y(v) + 3} fill="rgba(255,255,255,0.4)" fontSize="9"
            textAnchor="end">{v}</text>
        </g>
      ))}
      <text x={W / 2} y={H - 6} fill="rgba(255,255,255,0.45)" fontSize="9"
        textAnchor="middle">market implied home win%</text>
      <text x={10} y={H / 2} fill="rgba(255,255,255,0.45)" fontSize="9"
        textAnchor="middle" transform={`rotate(-90 10 ${H / 2})`}>actual home win rate</text>
    </svg>
  );
}

/** The odds layer: season calibration + the live board (§0g). */
export default async function HoopsMarketPage() {
  const doc = await getHoopsMarket();
  if (!doc) {
    return <p className="text-sm text-text-dim">Market doc not baked yet.</p>;
  }
  const c = doc.calibration;
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = doc.live.games.filter((g) => g.date >= today);
  const recent = doc.live.games.filter((g) => g.date < today).slice(0, 8);
  const board = [...upcoming, ...recent].slice(0, 34);
  const n_up = upcoming.length;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Market</h1>
        <p className="text-xs text-text-dim max-w-3xl">
          What the betting market said before each game, and what happened —
          {seasonLabelOf(c.season)} opening lines (consensus median across up to
          13 vendors, vig removed) against every final score, plus the live
          board for {seasonLabelOf(doc.live.season)}. Descriptive: this is the
          market measured, not a model of ours.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 max-w-5xl items-start">
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
          <h2 className="text-sm font-medium text-text-primary mb-1">
            Does the market know?
            <span className="text-text-dim font-normal text-[10px]"> · {c.n} games, {seasonLabelOf(c.season)}</span>
          </h2>
          <div className="tabular-nums text-text-secondary space-y-0.5 mb-2">
            <p>Brier score <span className="text-text-primary font-medium">{c.brier?.toFixed(3)}</span>
              {" "}· home favorites covered{" "}
              <span className="text-text-primary font-medium">
                {c.home_fav_cover != null ? `${(c.home_fav_cover * 100).toFixed(1)}%` : "—"}
              </span> of spreads</p>
            <p className="text-[10px] text-text-dim/70">
              the cover rate is the point: a fair spread wins half the time
            </p>
          </div>
          <CalibrationChart deciles={c.deciles} />
          <p className="text-[10px] text-text-dim/70 mt-1">
            implied win% deciles vs actual — monotone through all ten buckets;
            the diagonal is perfection
          </p>
        </div>

        <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
          <h2 className="text-sm font-medium text-text-primary mb-1.5">
            Live board
            <span className="text-text-dim font-normal text-[10px]">
              {" "}· {doc.live.n} priced games · {doc.live.with_movement} moved in the
              snapshot window{doc.live.snap_span ? ` (${doc.live.snap_span[0]} → ${doc.live.snap_span[1].slice(5)})` : ""}
            </span>
          </h2>
          {n_up > 0 && (
            <p className="text-[10px] text-text-dim/70 mb-1.5">
              {n_up} upcoming · showing the next {Math.min(n_up, board.length)}
            </p>
          )}
          <div className="space-y-0.5 max-h-[420px] overflow-y-auto pr-1">
            {board.map((g) => (
              <div key={g.gid}
                className="flex items-center justify-between gap-2 py-1 border-b border-border-subtle/40">
                <span className="text-text-secondary w-20 shrink-0 text-[10px] tabular-nums">{g.date.slice(5)}</span>
                <span className="text-text-primary min-w-0 flex-1 truncate">
                  {g.away} @ {g.home}
                </span>
                <span className="tabular-nums text-text-secondary w-24 text-right shrink-0">
                  {g.open_spread != null && g.open_spread !== g.spread ? (
                    <span className="text-text-dim">{g.open_spread > 0 ? "+" : ""}{g.open_spread}</span>
                  ) : null}
                  {" → "}
                  <span className="text-text-primary font-medium">{g.spread}</span>
                  {g.move != null && g.move !== 0 && (
                    <span className="ml-1 text-[10px] text-flag">{sgn(g.move)}</span>
                  )}
                </span>
                <span className="tabular-nums text-text-dim w-14 text-right shrink-0">
                  {g.total ?? "—"}
                </span>
                <span className="tabular-nums text-text-dim w-12 text-right shrink-0 hidden sm:block">
                  {g.p_home != null ? `${Math.round(g.p_home * 100)}%` : "—"}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-text-dim/70 mt-1.5">
            home spread (− = home favored) · total · implied home win%. Movement
            is current consensus vs the game&apos;s opening line (violet = moved).
          </p>
        </div>
      </div>

      <p className="text-[10px] text-text-dim/70 max-w-3xl">
        §0g-gated odds layer (coverage 1.0, vig normalized per two-way pair,
        movements sanity-banded). Consensus = per-game vendor median; implied
        probabilities sum to 1 by construction. The market&apos;s Brier is a
        descriptive benchmark for whatever we forecast later — not a model of
        ours. Sources: balldontlie odds (GOAT-trial snapshot 2026-11); the live
        stream ended with the trial window.
      </p>
    </div>
  );
}
