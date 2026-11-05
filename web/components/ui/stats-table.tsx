"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

export type StatsRow = {
  id: string; name: string; team: string | null; gp: number; gs: number | null;
  min: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number;
  fgp: number | null; tpp: number | null; ftp: number | null;
  ts: number | null; usg: number | null; ortg: number | null; drtg: number | null;
  net: number | null; pie: number | null;
};

type Col = {
  key: string; label: string; pct?: boolean; dp?: number;
  /** the value is judged against the season's league bands (and flips for allowance stats) */
  judged?: boolean; lower?: boolean;
};

const COLS: Col[] = [
  { key: "name", label: "Player" },
  { key: "team", label: "Team" },
  { key: "gp", label: "GP" },
  { key: "min", label: "MPG" },
  { key: "pts", label: "PTS" },
  { key: "reb", label: "REB" },
  { key: "ast", label: "AST" },
  { key: "stl", label: "STL" },
  { key: "blk", label: "BLK" },
  { key: "tov", label: "TOV" },
  { key: "fgp", label: "FG%", pct: true, judged: true },
  { key: "tpp", label: "3P%", pct: true, judged: true },
  { key: "ftp", label: "FT%", pct: true, judged: true },
  { key: "ts", label: "TS%", pct: true, judged: true },
  { key: "usg", label: "USG%", pct: true },
  { key: "ortg", label: "ORtg", judged: true },
  { key: "drtg", label: "DRtg", judged: true, lower: true },
  { key: "net", label: "NET", judged: true },
  { key: "pie", label: "PIE", pct: true, judged: true },
];

type Dist = Record<string, number | undefined>;
const distOf = (league: Record<string, unknown>, key: string): Dist | undefined =>
  (league[`${key}|dist`] as Dist | undefined) ?? undefined;

/** Same judgment rule as the player page: top decile green (medium),
 *  bottom decile red, quartile bands tinted, middle neutral. */
const tier = (v: number | null, d: Dist | undefined, lower = false): string => {
  if (typeof v !== "number" || !d || d.p25 == null || d.p75 == null) return "text-text-primary";
  if (d.p10 != null && d.p90 != null) {
    if (lower ? v <= d.p10 : v >= d.p90) return "text-pos font-medium";
    if (lower ? v >= d.p90 : v <= d.p10) return "text-neg font-medium";
  }
  if (lower ? v <= d.p25 : v >= d.p75) return "text-pos";
  if (lower ? v >= d.p75 : v <= d.p25) return "text-neg";
  return "text-text-primary";
};

/** Sortable player-season table; judgment colors ride the league bands. */
export function StatsTable({ rows, league, lower }: {
  rows: StatsRow[]; league: Record<string, unknown>; lower: string[];
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "pts", dir: -1 });
  const lowerSet = useMemo(() => new Set(lower), [lower]);
  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sort.key];
      const bv = (b as unknown as Record<string, unknown>)[sort.key];
      if (typeof av !== "number" && typeof bv !== "number") return 0;
      if (typeof av !== "number") return 1;
      if (typeof bv !== "number") return -1;
      return (av - bv) * sort.dir;
    });
  }, [rows, sort]);
  const flip = (key: string) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: -1 }));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px] tabular-nums min-w-[1040px]">
        <thead>
          <tr className="text-text-dim text-left">
            <th className="font-normal pr-2">#</th>
            {COLS.map((c) => (
              <th key={c.key} className={`font-normal ${c.key === "name" ? "pr-3" : ""}`}>
                <button type="button" onClick={() => flip(c.key)}
                  className={`hover:text-text-secondary ${sort.key === c.key ? "text-text-primary" : ""}`}>
                  {c.label}{sort.key === c.key ? (sort.dir === -1 ? " ↓" : " ↑") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={r.id} className="border-t border-border-subtle/50 hover:bg-white/[0.03]">
              <td className="pr-2 text-text-dim">{i + 1}</td>
              {COLS.map((c) => {
                if (c.key === "name") return (
                  <td key={c.key} className="pr-3">
                    <Link href={`/players/${r.id}`} className="text-text-primary hover:underline">{r.name}</Link>
                  </td>
                );
                if (c.key === "team") return (
                  <td key={c.key}>
                    {r.team
                      ? <Link href={`/teams/${r.team.toLowerCase()}`} className="hover:underline">{r.team}</Link>
                      : "—"}
                  </td>
                );
                const v = (r as unknown as Record<string, unknown>)[c.key];
                const num = typeof v === "number" ? v : null;
                const cls = c.judged ? tier(num, distOf(league, c.key), c.lower ?? lowerSet.has(c.key)) : "text-text-primary";
                return (
                  <td key={c.key} className={cls}>
                    {num == null ? "—"
                      : c.pct ? `${(num * 100).toFixed(1)}%`
                      : c.dp != null ? num.toFixed(c.dp)
                      : c.key === "ortg" || c.key === "drtg" || c.key === "net" ? num.toFixed(1)
                      : String(num)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
