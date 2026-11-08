import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { Md } from "@/components/ui/md";
import { getHoopsMethods } from "@/lib/data-hoops";

export const metadata = { title: "Hoops methods" };
export const revalidate = 300; // prod: 5-min route cache; dev renders per request

export default async function MethodsPage() {
  const doc = await getHoopsMethods();
  return (
    <div className="space-y-4 max-w-3xl">
      <BackLink fallback="/" className="text-[11px] text-text-dim hover:text-text-secondary" />
      <h1 className="text-lg font-semibold text-text-primary">
        Methods <span className="text-text-dim font-normal">· the metrics canon</span>
      </h1>
      <p className="text-xs text-text-dim max-w-2xl leading-relaxed">
        What every number on this site is, where it comes from, and what we
        deliberately do not render. One definition per metric, enforced at the
        bake — this page is generated from the canon doc, so it cannot drift.
        See also <Link href="/research" className="text-text-secondary underline underline-offset-2">the reads index</Link> for
        how model claims are judged.
      </p>

      {doc ? (
        <>
          <Md body={doc.intro} />
          {doc.sections.map((s) => (
            <div key={s.title} className="rounded-lg border border-border-subtle px-3 py-2.5">
              <h2 className="text-sm font-medium text-text-primary mb-1">{s.title}</h2>
              <Md body={s.body} />
            </div>
          ))}
          <p className="text-[10px] text-text-dim/70">{doc.note}</p>
        </>
      ) : (
        <p className="text-xs text-text-dim">methods.json.gz not baked yet — run pipeline/hoops_export.py.</p>
      )}
    </div>
  );
}
