import Link from "next/link";
import { BackLink } from "@/components/ui/back-link";
import { Md } from "@/components/ui/md";
import { getHoopsMethods, getHoopsSources } from "@/lib/data-hoops";

export const metadata = { title: "Hoops methods" };
export const revalidate = 300; // prod: 5-min route cache; dev renders per request

export default async function MethodsPage() {
  const [doc, src] = [await getHoopsMethods(), await getHoopsSources()];
  return (
    <div className="space-y-4 max-w-5xl">
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
      ) : null}
      {src && (
        <section id="sources" className="space-y-3 scroll-mt-4">
          <h2 className="text-sm font-medium text-text-primary">Sources</h2>
          <p className="text-xs text-text-dim max-w-2xl leading-relaxed">
            Every stat traced to the feed call it is computed from, the method, the code that computes it, the
            pre-registered gate that cleared it and the published reference it follows. Reference sites are cited
            for definitions only; LUMA Basketball Research numbers are a validation reference and never shown as ours.
          </p>
          <div className="rounded-lg border border-border-subtle px-3 py-2.5 space-y-1.5 text-[11px]">
            <div className="text-text-secondary font-medium">Feeds</div>
            {Object.entries(src.feeds).map(([k, f]) => (
              <div key={k} className="text-text-dim leading-relaxed">
                <span className="text-text-primary">{f.name}</span> · <code className="text-[10.5px] break-all">{f.call}</code>
                {" "}— {f.gives}. <span className="text-text-dim/80">Terms: {f.terms}.</span>
                {f.caveat && <span className="block text-flag/90">Caveat: {f.caveat}</span>}
              </div>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] align-top">
              <thead className="text-text-dim text-[10.5px] text-left">
                <tr className="border-b border-border-subtle">
                  <th className="py-1.5 pr-3">Stats</th><th className="pr-3">Method</th><th className="pr-3">Feed · code</th>
                  <th className="pr-3">Gate</th><th>Reference</th>
                </tr>
              </thead>
              <tbody>
                {src.families.map((f) => (
                  <tr key={f.family} className="border-b border-white/[0.04] align-top">
                    <td className="py-1.5 pr-3 min-w-36">
                      <div className="text-text-primary">{f.family}</div>
                      <div className="text-text-dim text-[10px]">{f.keys.join(", ")}</div>
                    </td>
                    <td className="pr-3 py-1.5 text-text-secondary min-w-56">{f.method}</td>
                    <td className="pr-3 py-1.5 text-text-dim">
                      {f.feeds.map((x) => src.feeds[x]?.name ?? x).join(" + ")}
                      <div><code className="text-[10px]">{f.code}</code></div>
                    </td>
                    <td className="pr-3 py-1.5 text-text-dim min-w-28">
                      {f.gate ?? <span className="text-flag">descriptive</span>}
                      {Object.entries(f.gates).map(([g, v]) => (
                        <div key={g} className="text-[10px]">{g}: {v.credit}{v.ran ? `, ${v.ran}` : ""}</div>
                      ))}
                      {f.descriptive?.length ? (
                        <div className="text-[10px] text-flag">still descriptive: {f.descriptive.join(", ")}</div>
                      ) : null}
                    </td>
                    <td className="py-1.5 text-text-dim">
                      {f.refs.map((r) => (
                        <div key={r.url}><a href={r.url} className="underline underline-offset-2" rel="noreferrer">{r.title}</a></div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {!doc && (
        <p className="text-xs text-text-dim">methods.json.gz not baked yet — run pipeline/hoops_export.py.</p>
      )}
    </div>
  );
}
