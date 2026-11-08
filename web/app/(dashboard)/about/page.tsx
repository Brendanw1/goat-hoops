import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { getHoopsMeta } from "@/lib/data-hoops";

export const metadata = { title: "About" };
export const revalidate = 300; // prod: 5-min route cache; dev renders per request

export default async function AboutPage() {
  const meta = await getHoopsMeta();
  const generated = (meta as Record<string, unknown> | null)?.generated;
  return (
    <div className="space-y-4 max-w-5xl">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <h1 className="text-lg font-semibold text-text-primary">
        About <span className="text-text-dim font-normal">· sources, validation, colophon</span>
      </h1>

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs space-y-2">
        <h2 className="text-sm font-medium text-text-primary">What this is</h2>
        <p className="text-text-secondary leading-relaxed">
          A basketball analytics research log. Every surface is descriptive and
          labeled; every model claim was pre-registered and judged on fixed gates —
          the failures are on <Link href="/research" className="text-text-secondary underline underline-offset-2">the reads index</Link> next
          to the passes. Metric definitions live in <Link href="/methods" className="text-text-secondary underline underline-offset-2">the canon</Link>.
        </p>
      </div>

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs space-y-2">
        <h2 className="text-sm font-medium text-text-primary">Sources & credit</h2>
        <ul className="list-disc pl-5 space-y-1 text-text-secondary leading-relaxed">
          <li><span className="text-text-primary">ESPN</span> — the box-score spine: game scores, player boxes, shot locations.</li>
          <li><span className="text-text-primary">balldontlie</span> — the second source: advanced tracking tiers (matchups, contested shots, box outs, rebound chances, touches/passes), contracts, standings, play-by-play. <span className="text-flag">Public surfaces carry balldontlie numbers only while a subscription is active.</span></li>
          <li><span className="text-text-primary">LUMA Basketball Research (ARC v3.1, LOKI v3.3)</span> — external benchmark credit for every model read; never republished.</li>
        </ul>
      </div>

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs space-y-2">
        <h2 className="text-sm font-medium text-text-primary">Validation</h2>
        <p className="text-text-secondary leading-relaxed">
          Nothing from a new source renders until it agrees with the spine exactly.
          The gate: game scores and player boxes on the overlapping season must
          match to the point — {meta?.validation
            ? `${meta.validation.games_2024_25} game scores 2024-25 and ${meta.validation.boxes} boxes matched ${meta.validation.credit} exactly`
            : "game scores and boxes matched the credit source exactly"}
          . Field note from the build: balldontlie season keys are starting years
          and ESPN&apos;s are ending years — every merge in the pipeline pins
          site-season = source-season + 1, after a one-year mislabel was caught
          and fixed.
        </p>
      </div>

      <div className="rounded-lg border border-border-subtle px-3 py-2.5 text-xs space-y-2">
        <h2 className="text-sm font-medium text-text-primary">Colophon</h2>
        <p className="text-text-secondary leading-relaxed">
          Python pipeline (bake + gates + R2 sync) → Next.js server components.
          Zero client JavaScript except the nav and the player finder. Colors are
          semantic: green/red/violet are judgment (good/bad/small-sample), the
          violet→yellow heat ramp is volume only, and player identity in charts
          uses the brand pair. Baked {typeof generated === "string" ? generated : "recently"};{" "}
          <Link href="/methods" className="text-text-secondary underline underline-offset-2">methods</Link> carry the formulas.
        </p>
      </div>
    </div>
  );
}
