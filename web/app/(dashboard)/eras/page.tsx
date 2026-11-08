import { getHoopsHistory } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const seasonLabelOf = (s: number) => `${s - 1}-${String(s).slice(2)}`;

const COLS: { key: "pace" | "ortg" | "efg" | "ts" | "fg3ar" | "ftr" | "tov_pct" | "orb_pct"; label: string; fmt: (v: number) => string }[] = [
  { key: "pace", label: "Pace", fmt: (v) => v.toFixed(1) },
  { key: "ortg", label: "ORtg", fmt: (v) => v.toFixed(1) },
  { key: "efg", label: "eFG%", fmt: (v) => `${(v * 100).toFixed(1)}` },
  { key: "ts", label: "TS%", fmt: (v) => `${(v * 100).toFixed(1)}` },
  { key: "fg3ar", label: "3PA share", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "ftr", label: "FT rate", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "tov_pct", label: "TOV%", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "orb_pct", label: "ORB%", fmt: (v) => `${(v * 100).toFixed(1)}%` },
];

/** The league environment per season — the era context every other surface reads against. */
export default async function HoopsErasPage() {
  const doc = await getHoopsHistory();
  if (!doc) {
    return <p className="text-sm text-text-dim">History doc not baked yet.</p>;
  }
  const seasons = Object.keys(doc.env).map(Number).sort((a, b) => a - b);
  const first = doc.env[String(seasons[0])];
  const last = doc.env[String(seasons[seasons.length - 1])];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Eras</h1>
        <p className="text-xs text-text-dim max-w-3xl">
          The league environment, {seasonLabelOf(seasons[0])} → {seasonLabelOf(seasons[seasons.length - 1])}
          {" "}— pace, efficiency and shot diet per season, derived with one formula set
          across all 21 seasons (§0d/§0e; the 2025/2026 values cross-check against the
          team-grain derivation to the gate's tolerances).
        </p>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-text-secondary tabular-nums">
        <span>pace {first.pace.toFixed(1)} → <span className="text-text-primary">{last.pace.toFixed(1)}</span></span>
        <span>ORtg {first.ortg?.toFixed(1)} → <span className="text-text-primary">{last.ortg?.toFixed(1)}</span></span>
        <span>eFG {(first.efg * 100).toFixed(1)}% → <span className="text-text-primary">{(last.efg * 100).toFixed(1)}%</span></span>
        <span>3PA share {(first.fg3ar * 100).toFixed(1)}% → <span className="text-text-primary">{(last.fg3ar * 100).toFixed(1)}%</span></span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full max-w-3xl text-xs tabular-nums">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-text-dim border-b border-border-subtle">
              <th className="text-left py-1.5 pr-3 font-medium">Season</th>
              {COLS.map((c) => (
                <th key={c.key} className="text-right py-1.5 px-2 font-medium">{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {seasons.map((s) => {
              const e = doc.env[String(s)];
              return (
                <tr key={s} className="border-b border-border-subtle/40">
                  <td className="py-1 pr-3 text-text-secondary">{seasonLabelOf(s)}</td>
                  {COLS.map((c) => (
                    <td key={c.key} className="py-1 px-2 text-right text-text-secondary">
                      {c.fmt(e[c.key] as number)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-text-dim/70 max-w-3xl">
        Derived from balldontlie season-average pulls (gp-weighted sums, possessions =
        FGA − OREB + TOV + 0.44·FTA, minutes normalized to 48 — OT share not modeled
        pre-2019, worth ≲ 0.5 pace points). Team-games are the schedule constants
        (990 in 2011-12, 1,056 in 2019-20, 1,080 in 2020-21). Descriptive throughout —
        no era is graded.
      </p>
    </div>
  );
}
