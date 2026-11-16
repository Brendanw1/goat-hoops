/**
 * Shot creation (RESULTS-HOOPS §0i): per zone, makes split into assisted vs
 * self-created, bar length = attempts, plus the ESPN shot-type diet. Server
 * rendered, no client JS; the numbers in each row are the accessible view.
 */
const ZONE_LABEL: Record<string, string> = {
  rim: "Rim (< 4 ft)", paint: "Paint", mid: "Mid-range", c3: "Corner 3", ab3: "Above-break 3",
};
const TYPE_LABEL: Record<string, string> = {
  pullup: "Pull-up", stepback: "Step-back", driving: "Driving", cutting: "Cutting",
  putback: "Putback / tip", alleyoop: "Alley-oop", other: "Other (catch, post, float…)",
};
const pct = (n: number, d: number) => (d > 0 ? `${((n / d) * 100).toFixed(1)}%` : "—");

export function ShotCreation({ zones, types }: {
  zones: Record<string, number[]>; types: Record<string, number[]>;
}) {
  const max = Math.max(...Object.values(zones).map((z) => z[0]), 1);
  const fga = Object.values(types).reduce((s, t) => s + t[0], 0);
  const tRows = Object.entries(types).filter(([, t]) => t[0] > 0).sort((a, b) => b[1][0] - a[1][0]);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div>
        <div className="flex items-center gap-3 text-[10px] text-text-dim mb-1.5">
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-3 rounded-sm bg-elite/80" />self-created make</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-3 rounded-sm bg-white/35" />assisted make</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-3 rounded-sm bg-white/[0.07]" />miss</span>
        </div>
        <div className="space-y-1.5">
          {Object.entries(ZONE_LABEL).map(([z, label]) => {
            const [a, m, ast] = zones[z] ?? [0, 0, 0];
            const w = (n: number) => `${(n / max) * 100}%`;
            return (
              <div key={z} className="text-[11px]">
                <div className="flex justify-between text-text-secondary tabular-nums">
                  <span>{label}</span>
                  <span className="text-text-dim">
                    {m}/{a} · {pct(m, a)} · {m ? `${Math.round(((m - ast) / m) * 100)}% self-created` : "—"}
                  </span>
                </div>
                <div className="flex h-2 rounded-sm overflow-hidden" title={`${label}: ${m - ast} self-created, ${ast} assisted, ${a - m} missed`}>
                  <div className="bg-elite/80" style={{ width: w(m - ast) }} />
                  <div className="bg-white/35" style={{ width: w(ast) }} />
                  <div className="bg-white/[0.07]" style={{ width: w(a - m) }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <table className="w-full text-[11px] tabular-nums self-start">
        <thead>
          <tr className="text-text-dim text-left">
            <th className="font-normal pr-2">Shot type</th>
            <th className="font-normal text-right">FGA</th>
            <th className="font-normal text-right">Share</th>
            <th className="font-normal text-right">eFG</th>
          </tr>
        </thead>
        <tbody>
          {tRows.map(([t, [a, m, tp]]) => (
            <tr key={t} className="border-t border-border-subtle/50">
              <td className="pr-2 text-text-secondary">{TYPE_LABEL[t] ?? t}</td>
              <td className="text-right text-text-primary">{a}</td>
              <td className="text-right text-text-dim">{pct(a, fga)}</td>
              <td className="text-right">{pct(m + 0.5 * tp, a)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
