import Link from "next/link";
import { getHoopsTicker } from "@/lib/data-hoops";
import { TeamDot } from "@/lib/team-dot";

/**
 * The news/injury ticker — a CSS marquee strip under the nav. Items come from
 * the baked ticker.json (ESPN public APIs, fetched once per ingest run — the
 * site never calls ESPN). Status colors carry the judgment scale: Out red,
 * Day-To-Day/Questionable violet; headlines neutral. Pauses on hover;
 * respects prefers-reduced-motion.
 */

const STATUS_CLS: Record<string, string> = {
  Out: "text-neg", "Out For Season": "text-neg", "Out Indefinitely": "text-neg",
  Doubtful: "text-neg",
  "Day-To-Day": "text-flag", Questionable: "text-flag", GTD: "text-flag",
  Suspended: "text-neg",
};

export async function Ticker() {
  const doc = await getHoopsTicker();
  if (!doc || (!doc.injuries.length && !doc.news.length)) return null;
  const injItems = doc.injuries.map((i, k) => (
    <span key={`i${k}`} className="inline-flex items-center gap-1.5 px-3 whitespace-nowrap">
      {i.team && <TeamDot abbr={i.team} size={14} />}
      <span className="text-text-secondary">{i.player}</span>
      <span className={`text-[10px] font-semibold ${STATUS_CLS[i.status] ?? "text-text-dim"}`}>
        {i.status}
      </span>
      {i.comment && <span className="text-text-dim/80">{i.comment}</span>}
      <span className="text-border-default">|</span>
    </span>
  ));
  const newsItems = doc.news.map((n, k) => (
    <span key={`n${k}`} className="inline-flex items-center px-3 whitespace-nowrap">
      <Link href={n.link || "#"} target="_blank" rel="noopener noreferrer"
        className="text-text-secondary hover:text-text-primary hover:underline">
        {n.headline}
      </Link>
      <span className="text-border-default ml-3">|</span>
    </span>
  ));
  const run = [...injItems, ...newsItems];
  return (
    <div className="ticker relative overflow-hidden border-b border-border-subtle bg-surface-1 text-[11px] leading-6"
      title="injury report + headlines — hover to pause">
      <div className="ticker-track flex w-max py-1">
        <div className="flex">{run}</div>
        <div className="flex" aria-hidden>{run}</div>
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-surface-0 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-surface-0 to-transparent" />
    </div>
  );
}
