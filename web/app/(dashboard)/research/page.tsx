import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsReads } from "@/lib/data-hoops";
import type { HoopsRead } from "@/lib/data-hoops";

export const metadata = { title: "Hoops research" };
export const dynamic = "force-dynamic";

const seasonDate = (d: string) => d;

/** Verdict chip: the semantic tokens do the talking — PASS green, FAIL red,
 *  TIE/PARTIAL violet. One system, everywhere. */
const Verdict = ({ v }: { v: string | null }) => {
  const cls = v === "PASS" ? "text-pos border-pos/40"
    : v === "FAIL" ? "text-neg border-neg/40"
    : v === "TIE" || v === "PARTIAL" ? "text-flag border-flag/40"
    : "text-text-dim border-border-subtle";
  return (
    <span className={`rounded px-1.5 py-0.5 border text-[10px] font-medium tabular-nums ${cls}`}>
      {v ?? "—"}
    </span>
  );
};

const Ladder = ({ ladder }: { ladder: [string, number][] }) => {
  const bar = 0.70;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[11px] tabular-nums">
      {ladder.map(([n, v], i) => (
        <span key={n} className="flex items-center gap-1">
          {i > 0 && <span className="text-text-dim/60">→</span>}
          <span title={`${n} benchmark ${v.toFixed(3)} vs the ${bar} bar`}
            className={`rounded px-1.5 py-0.5 border ${v >= bar ? "text-pos border-pos/40" : "text-neg border-neg/40"}`}>
            {n} {v.toFixed(3)}
          </span>
        </span>
      ))}
      <span className="text-text-dim ml-1">· gate {bar} · stability gate 0.60</span>
    </div>
  );
};

const ReadRow = ({ r }: { r: HoopsRead }) => (
  <details className="border-t border-border-subtle/50 group">
    <summary className="flex items-center gap-2 py-1.5 cursor-pointer list-none [&::-webkit-details-marker]:hidden">
      <span className="text-text-dim tabular-nums w-9 shrink-0">{r.n}</span>
      <span className="text-text-primary flex-1 min-w-0 truncate" title={r.title}>{r.title}</span>
      <span className="text-text-dim tabular-nums text-[10px] hidden sm:inline">{seasonDate(r.date)}</span>
      <Verdict v={r.verdict} />
    </summary>
    <div className="pb-2.5 pl-11 pr-2 space-y-1">
      {r.why && <p className="text-[11px] text-text-secondary leading-relaxed">{r.why}</p>}
      {r.line && (
        <p className={`text-[11px] leading-relaxed ${r.verdict === "PASS" ? "text-pos" : r.verdict === "FAIL" ? "text-neg" : "text-flag"}`}>
          Verdict: {r.line}
        </p>
      )}
      {!r.line && <p className="text-[11px] text-text-dim">No explicit verdict line recorded in the log.</p>}
    </div>
  </details>
);

export default async function ResearchPage() {
  const reads = await getHoopsReads();
  return (
    <div className="space-y-4 max-w-3xl">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <h1 className="text-lg font-semibold text-text-primary">
        Research <span className="text-text-dim font-normal">· the reads index</span>
      </h1>
      <p className="text-xs text-text-dim max-w-2xl leading-relaxed">
        Every model question this program has asked was pre-registered before any
        fit, judged on fixed gates, and recorded with its verdict — including the
        failures. Nothing ships without passing its gate; a FAIL stays visible
        here with its diagnosis. This page is parsed from the research log at
        bake, so it cannot drift from the record.
      </p>

      {reads ? (
        <>
          <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
            <h2 className="text-sm font-medium text-text-primary mb-1.5">The RAPM campaign, closed</h2>
            <Ladder ladder={reads.ladder} />
            <p className="text-[11px] text-text-dim mt-1.5 leading-relaxed">
              Eight pre-registered reads on identical gates. The two best designs
              correlate 0.97 — estimation is exhausted — and the gap to the bar is
              <span className="text-text-secondary"> information, not math</span>: the
              benchmark surface carries per-shot defender context that public feeds
              don&apos;t. Ratings stay internal-descriptive; the gate re-opens only
              with a new data tier.
            </p>
          </div>

          <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
            <h2 className="text-sm font-medium text-text-primary mb-1">Data gates</h2>
            {reads.gates.map((g) => (
              <div key={g.n} className="flex items-start gap-2 py-1.5 border-t border-border-subtle/50 first:border-t-0">
                <span className="text-text-dim tabular-nums w-9 shrink-0 pt-0.5">{g.n}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-text-primary">{g.title}</div>
                  <div className="text-[11px] text-text-dim mt-0.5">{g.line}</div>
                </div>
                <Verdict v={g.verdict} />
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs">
            <h2 className="text-sm font-medium text-text-primary mb-1">
              The reads <span className="text-text-dim font-normal text-[10px]">· {reads.sections.length} sections, newest last · expand for the verdict</span>
            </h2>
            {[...reads.sections].reverse().map((r) => <ReadRow key={r.n} r={r} />)}
          </div>

          <p className="text-[10px] text-text-dim/70 max-w-2xl">{reads.note}</p>
        </>
      ) : (
        <p className="text-xs text-text-dim">reads.json.gz not baked yet — run pipeline/hoops_export.py.</p>
      )}
    </div>
  );
}
