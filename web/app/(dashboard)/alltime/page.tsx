import Link from "next/link";
import { getHoopsHistory, type HoopsHistoryLeaderRow } from "@/lib/data-hoops";

export const dynamic = "force-dynamic";

const seasonLabelOf = (s: number) => `${s - 1}-${String(s).slice(2)}`;

const CAREER_CARDS: { key: string; label: string; fmt: (v: number) => string }[] = [
  { key: "pts", label: "Points", fmt: (v) => v.toLocaleString() },
  { key: "reb", label: "Rebounds", fmt: (v) => v.toLocaleString() },
  { key: "ast", label: "Assists", fmt: (v) => v.toLocaleString() },
  { key: "stl", label: "Steals", fmt: (v) => v.toLocaleString() },
  { key: "blk", label: "Blocks", fmt: (v) => v.toLocaleString() },
  { key: "ts", label: "TS%", fmt: (v) => `${(v * 100).toFixed(1)}%` },
];

function LeaderRow({ r, fmt }: { r: HoopsHistoryLeaderRow; fmt: (v: number) => string }) {
  const name = r.eid ? (
    <Link href={`/players/${r.eid}`} className="hover:underline">{r.name}</Link>
  ) : (
    <span>{r.name}</span>
  );
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-text-secondary truncate">
        {name}
        <span className="text-text-dim/70 ml-1.5 text-[10px] tabular-nums">
          {r.span ? `${r.span}` : r.s ? seasonLabelOf(r.s) : ""} · {r.gp}g
        </span>
      </span>
      <span className="tabular-nums text-text-primary font-medium shrink-0">{fmt(r.v)}</span>
    </div>
  );
}

function Card({ title, rows, fmt }: { title: string; rows: HoopsHistoryLeaderRow[]; fmt: (v: number) => string }) {
  return (
    <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs min-w-0">
      <h3 className="text-sm font-medium text-text-primary mb-1.5">{title}</h3>
      <div className="space-y-0.5">
        {rows.map((r, i) => (
          <div key={`${r.name}-${r.span ?? r.s}-${i}`} className="flex items-baseline gap-1.5">
            <span className="w-4 text-right text-[10px] text-text-dim/70 tabular-nums">{i + 1}</span>
            <span className="min-w-0 flex-1"><LeaderRow r={r} fmt={fmt} /></span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** All-time leaderboards across the baked span (§0e floors; totals = Σ per-game × gp). */
export default async function HoopsAllTimePage() {
  const doc = await getHoopsHistory();
  if (!doc) {
    return <p className="text-sm text-text-dim">History doc not baked yet.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">All-time</h1>
        <p className="text-xs text-text-dim max-w-3xl">
          Leaderboards across the baked span {seasonLabelOf(doc.span.first)} →{" "}
          {seasonLabelOf(doc.span.last)}. Career totals are Σ(per-game × gp) over the
          span — players whose careers predate {seasonLabelOf(doc.span.first)} show
          span-only totals (LeBron reads 39.6k, not the official 40k+). Rate floors and
          table floors are fixed in §0e; names link only where the player is bridged to
          a site page (active players).
        </p>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-text-primary">
          Career <span className="text-text-dim font-normal text-[10px]">· top 20 of 40 shown · gp ≥ 50 in span; TS% needs 6,000+ span minutes</span>
        </h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {CAREER_CARDS.map((c) => (
            <Card key={c.key} title={c.label}
              rows={(doc.leaders_career[c.key] ?? []).slice(0, 20)} fmt={c.fmt} />
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-text-primary">
          Single seasons <span className="text-text-dim font-normal text-[10px]">· per-game, gp ≥ 40; TS% also needs 1,200+ minutes</span>
        </h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {CAREER_CARDS.map((c) => (
            <Card key={c.key} title={c.label}
              rows={(doc.leaders_season[c.key] ?? []).slice(0, 20)} fmt={c.fmt} />
          ))}
        </div>
      </section>

      <p className="text-[10px] text-text-dim/70 max-w-3xl">
        Source: balldontlie season-average pulls (§0e gate: the league env cross-checks
        against the §0d team-grain derivation). Descriptive leaderboards only — no
        all-time rankings are graded or claimed.
      </p>
    </div>
  );
}
