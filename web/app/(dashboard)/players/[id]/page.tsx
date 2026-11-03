import Link from "next/link";
import { notFound } from "next/navigation";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsContracts, getHoopsPlayer, getHoopsSeasAvgs } from "@/lib/data-hoops";
import type { HoopsContractDeal, HoopsSSCat } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const money = (v: number | null | undefined) => {
  if (v == null) return "—";
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${v}`;
};

const fnum = (v: number | string | null | undefined, dp = 1) => {
  if (typeof v === "number") return v.toFixed(dp);
  if (v == null) return "—";
  return v;
};
const rate = (v: number | string | null | undefined) =>
  typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—";

const dealSpan = (d: HoopsContractDeal) =>
  d.start != null && d.end != null ? `${d.start}-${String(d.end).slice(2)}` :
  d.start != null ? `${d.start}-` : "—";

const RateChip = ({ label, value }: { label: string; value: number | string | null | undefined }) => (
  <div className="bg-white/[0.03] rounded px-2 py-1">
    <div className="text-text-dim text-[10px]">{label}</div>
    <div className="text-text-primary font-medium tabular-nums">{fnum(value, 1)}</div>
  </div>
);

/** One player: contract, category panels, per-season lines, game log. */
export default async function HoopsPlayerPage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const doc = await getHoopsPlayer(id);
  if (!doc || !Object.keys(doc.seasons).length) notFound();
  const seasons = Object.keys(doc.seasons).sort((a, b) => Number(b) - Number(a));
  const latest = doc.seasons[seasons[0]];
  const [cdoc, ss25, ss24] = [await getHoopsContracts(), await getHoopsSeasAvgs(2025), await getHoopsSeasAvgs(2024)];
  const ssDoc = ss25 ?? ss24;
  const ss = ssDoc?.players[id];
  const pt = ss?.playtype ?? [];
  const adv = ss?.adv;
  const deals = cdoc?.deals[id] ?? [];
  const salary = cdoc?.salaries[id];
  const current = deals.find((d) => d.status === "CURRENT") ?? deals[0];
  const prior = current ? deals.filter((d) => d !== current) : deals;
  const ssLabel = ssDoc ? `${ssDoc.season - 1}-${String(ssDoc.season).slice(2)}` : "";

  return (
    <div className="space-y-5">
      <BackLink fallback="/players" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <div>
        <h1 className="text-lg font-semibold text-text-primary">{doc.name}</h1>
        <p className="text-xs text-text-dim">
          {[...new Set(seasons.map((s) => doc.seasons[s].team).filter(Boolean))].join(" · ")}
        </p>
      </div>

      {(current || salary) && (
        <div className="rounded-lg border border-border-subtle px-3 py-2.5 max-w-3xl text-xs space-y-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
            <h2 className="text-sm font-medium text-text-primary">Contract</h2>
            {salary && (
              <span className="text-text-secondary tabular-nums">
                {salary.season ? `${salary.season - 1}-${String(salary.season).slice(2)} · ` : ""}
                cap hit {money(salary.cap_hit)}
                {salary.base_salary != null && salary.base_salary !== salary.cap_hit &&
                  ` · base ${money(salary.base_salary)}`}
                {salary.team ? ` · ${salary.team}` : ""}
              </span>
            )}
          </div>
          {current && (
            <>
              <div className="text-text-secondary">
                <span className="text-text-primary font-medium">{current.type ?? "Deal"}</span>
                {current.team ? ` · ${current.team}` : ""}
                {current.years != null && <> · {dealSpan(current)} ({current.years} yr{current.years === 1 ? "" : "s"})</>}
                {current.total_value != null && <> · {money(current.total_value)}</>}
                {current.avg_salary != null && <> · {money(current.avg_salary)}/yr</>}
              </div>
              <div className="text-text-dim">
                {current.guaranteed != null && <>guaranteed {money(current.guaranteed)} · </>}
                {current.signed_using && <>signed using {current.signed_using} · </>}
                {current.fa_year != null &&
                  <>FA {current.fa_year}{current.fa_status ? ` (${current.fa_status})` : ""}</>}
              </div>
              {current.notes && <div className="text-text-dim">{current.notes}</div>}
            </>
          )}
          {prior.length > 0 && (
            <div className="text-text-dim tabular-nums pt-0.5 border-t border-border-subtle/50">
              {prior.map((d, i) => (
                <span key={i}>
                  {i > 0 && " · "}
                  {d.type ?? "Deal"} {dealSpan(d)}
                  {d.total_value != null ? ` (${money(d.total_value)})` : ""}
                </span>
              ))}
            </div>
          )}
          <div className="text-[10px] text-text-dim/70">balldontlie snapshot — internal research</div>
        </div>
      )}

      {ss && (
        <div className="max-w-3xl space-y-3">
          {adv && (
            <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
              <h2 className="text-sm font-medium text-text-primary mb-1.5">
                Advanced rates <span className="text-text-dim font-normal text-[10px]">· {ssLabel}</span>
              </h2>
              <div className="grid grid-cols-4 gap-1.5">
                <RateChip label="TS%" value={rate(adv.ts_pct)} />
                <RateChip label="eFG%" value={rate(adv.efg_pct)} />
                <RateChip label="USG%" value={rate(adv.usg_pct)} />
                <RateChip label="AST%" value={rate(adv.ast_pct)} />
                <RateChip label="ORtg" value={adv.off_rating} />
                <RateChip label="DRtg" value={adv.def_rating} />
                <RateChip label="Net" value={adv.net_rating} />
                <RateChip label="PIE" value={adv.pie} />
              </div>
              <div className="text-[10px] text-text-dim/70 mt-1">balldontlie snapshot — internal research</div>
            </div>
          )}
          {pt.length > 0 && (
            <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
              <h2 className="text-sm font-medium text-text-primary mb-1.5">
                Play type <span className="text-text-dim font-normal text-[10px]">· {ssLabel} · poss per game · bar = league percentile</span>
              </h2>
              <div className="space-y-1">
                {pt.filter((d) => Number(d.poss) > 0).map((d) => (
                  <div key={String(d.play_type)} className="flex items-center gap-2">
                    <span className="w-20 text-text-secondary shrink-0">{String(d.play_type).replace("nba_", "")}</span>
                    <div className="flex-1 h-2.5 bg-white/[0.04] rounded-sm overflow-hidden">
                      <div className="h-full bg-usf-green/70" style={{ width: `${Math.round(Number(d.percentile ?? 0) * 100)}%` }} />
                    </div>
                    <span className="w-16 text-right text-text-primary tabular-nums">{fnum(d.ppp, 2)} ppp</span>
                    <span className="w-16 text-right text-text-dim tabular-nums">{fnum(d.poss)} poss</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {(() => {
            const rows: [string, string, number | string | null | undefined][] = [];
            if (ss.speed) rows.push(["Speed", "mph", ss.speed.avg_speed], ["Distance", "mi/g", ss.speed.dist_miles]);
            if (ss.drives) rows.push(["Drives", "/g", ss.drives.drives], ["Drive pts", "/g", ss.drives.drive_pts], ["Drive FG%", "%", ss.drives.drive_fg_pct]);
            if (ss.passing) rows.push(["Passes", "/g", ss.passing.passes_made], ["AST pts created", "/g", ss.passing.ast_points_created]);
            if (ss.paint) rows.push(["Paint touches", "/g", ss.paint.paint_touches], ["Paint pts", "/g", ss.paint.paint_touch_pts]);
            if (ss.catch_shoot) rows.push(["C&S FGA", "/g", ss.catch_shoot.catch_shoot_fga], ["C&S FG%", "%", ss.catch_shoot.catch_shoot_fg_pct]);
            if (ss.pullup) rows.push(["Pull-up FGA", "/g", ss.pullup.pull_up_fga], ["Pull-up FG%", "%", ss.pullup.pull_up_fg_pct]);
            if (ss.hustle) rows.push(["Deflections", "/g", ss.hustle.deflections], ["Charges", "/g", ss.hustle.charges_drawn], ["Screen asts", "/g", ss.hustle.screen_assists]);
            if (ss.defense) rows.push(["Contested FG%", "%", ss.defense.d_fg_pct]);
            return rows.length > 0 ? (
              <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
                <h2 className="text-sm font-medium text-text-primary mb-1.5">
                  Tracking <span className="text-text-dim font-normal text-[10px]">· {ssLabel}</span>
                </h2>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
                  {rows.map(([l, unit, v]) => (
                    <div key={l} className="bg-white/[0.03] rounded px-2 py-1">
                      <div className="text-text-dim text-[10px]">{l}</div>
                      <div className="text-text-primary font-medium tabular-nums">
                        {unit === "%" ? rate(v) : fnum(v)} <span className="text-text-dim text-[10px]">{unit === "%" ? "" : typeof v === "number" ? unit : ""}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null;
          })()}
          {ss.zones && (
            <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs max-w-3xl">
              <h2 className="text-sm font-medium text-text-primary mb-1.5">Shot zones</h2>
              <table className="w-full text-[11px] tabular-nums">
                <thead>
                  <tr className="text-text-dim text-left">
                    <th className="font-normal pr-2">Zone</th><th className="font-normal">FGA</th><th className="font-normal">FG%</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(ss.zones).filter(([, z]) => Number(z.fga) > 0).map(([z, v]) => (
                    <tr key={z} className="border-t border-border-subtle/50">
                      <td className="pr-2 text-text-secondary">{z.replace(/_/g, " ")}</td>
                      <td className="text-text-primary">{fnum(v.fga, 0)}</td>
                      <td>{rate(Number(v.fg_pct))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="text-[10px] text-text-dim/70 mt-1">balldontlie snapshot — internal research</div>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 max-w-3xl">
        {seasons.map((s) => {
          const r = doc.seasons[s];
          return (
            <div key={s} className="rounded-lg border border-border-subtle px-3 py-2 text-xs">
              <div className="text-text-primary font-medium mb-1">
                {Number(s) - 1}-{String(s).slice(2)} · {r.team ?? "—"} · {r.gp} GP ({r.gs} GS)
              </div>
              <div className="text-text-secondary tabular-nums">
                {r.per_game.pts} pts · {r.per_game.reb} reb · {r.per_game.ast} ast ·
                {" "}{r.per_game.stl} stl · {r.per_game.blk} blk · {r.per_game.tov} tov ·
                {" "}{r.per_game.min} min
              </div>
              <div className="text-text-dim tabular-nums mt-0.5">
                per 36: {r.per36.pts ?? "—"} / {r.per36.reb ?? "—"} / {r.per36.ast ?? "—"}
              </div>
            </div>
          );
        })}
      </div>

      {seasons.map((s) => {
        const r = doc.seasons[s];
        return (
          <div key={s} className="space-y-1">
            <h2 className="text-sm font-medium text-text-primary">
              {Number(s) - 1}-{String(s).slice(2)} game log
            </h2>
            <table className="w-full text-[11px] tabular-nums">
              <thead>
                <tr className="text-text-dim text-left">
                  <th className="font-normal pr-2">Date</th><th className="font-normal">Opp</th>
                  <th className="font-normal">Res</th><th className="font-normal">MIN</th>
                  <th className="font-normal">PTS</th><th className="font-normal">REB</th>
                  <th className="font-normal">AST</th><th className="font-normal">STL</th>
                  <th className="font-normal">BLK</th><th className="font-normal">TO</th>
                  <th className="font-normal">PF</th><th className="font-normal">FG</th>
                  <th className="font-normal">3PT</th><th className="font-normal">FT</th>
                  <th className="font-normal">+/-</th>
                </tr>
              </thead>
              <tbody>
                {[...r.games].reverse().map((g) => (
                  <tr key={g.id} className="border-t border-border-subtle/50 hover:bg-white/[0.03]">
                    <td className="pr-2">
                      <Link href={`/games/${g.id}`} className="text-text-primary hover:underline tabular-nums">
                        {g.date}
                      </Link>
                    </td>
                    <td>{g.home ? "vs" : "@"} {g.opp}</td>
                    <td className={g.res === "W" ? "text-usf-green" : "text-[#e0654f]"}>{g.res}</td>
                    <td>{g.min ?? "—"}</td><td className="font-medium">{g.pts}</td>
                    <td>{g.reb}</td><td>{g.ast}</td><td>{g.stl}</td><td>{g.blk}</td>
                    <td>{g.tov}</td><td>{g.pf}</td>
                    <td>{g.fg}</td><td>{g.tp}</td><td>{g.ft}</td>
                    <td className={g.pm != null && g.pm > 0 ? "text-usf-green" : g.pm != null && g.pm < 0 ? "text-[#e0654f]" : ""}>
                      {g.pm ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
