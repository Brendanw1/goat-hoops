import type { ReactNode } from "react";

/**
 * Minimal markdown renderer for the baked canon docs (methods.json.gz =
 * docs/METRICS.md at bake). Handles exactly what the doc uses: `### / ####`
 * sub-headings, pipe tables, `-` bullet lists, paragraphs, **bold**, `code`.
 * React elements throughout — no dangerouslySetInnerHTML.
 */
function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${keyBase}-b${k++}`} className="text-text-secondary font-medium">{tok.slice(2, -2)}</strong>);
    else out.push(<code key={`${keyBase}-c${k++}`} className="bg-white/[0.06] rounded px-1 text-[11px]">{tok.slice(1, -1)}</code>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Md({ body }: { body: string }) {
  const lines = body.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0, key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^#{1,6}\s/.test(line)) {
      const depth = line.match(/^#+/)[0].length;
      const txt = line.replace(/^#+\s*/, "");
      blocks.push(depth <= 2
        ? <h3 key={key++} className="text-[13px] font-semibold text-text-primary mt-4 mb-1">{inline(txt, `h${key}`)}</h3>
        : depth === 3
          ? <h4 key={key++} className="text-[13px] font-medium text-text-primary mt-4 mb-1">{inline(txt, `h${key}`)}</h4>
          : <h5 key={key++} className="text-xs font-medium text-text-primary mt-3 mb-1">{inline(txt, `h${key}`)}</h5>);
      i++; continue;
    }
    if (line.trimStart().startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        const cells = lines[i].trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
        rows.push(cells);
        i++;
      }
      const [head, sep, ...rest] = rows;
      const isSep = sep && sep.every((c) => /^:?-{2,}:?$/.test(c));
      const header = isSep ? head : null;
      const bodyRows = isSep ? rest : rows.slice(1);
      const cols = header ?? rows[0];
      blocks.push(
        <div key={key++} className="overflow-x-auto my-2">
          <table className="w-full text-[11px] tabular-nums border-collapse">
            <thead>
              <tr className="text-text-dim text-left">
                {cols.map((c, ci) => <th key={ci} className="font-normal pr-3 pb-1 border-b border-border-subtle">{inline(c, `th${ci}`)}</th>)}
              </tr>
            </thead>
            <tbody>
              {(isSep ? bodyRows : rows).map((r, ri) => (
                <tr key={ri} className="border-b border-border-subtle/40">
                  {r.map((c, ci) => <td key={ci} className="pr-3 py-1">{inline(c, `td${ri}-${ci}`)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (line.trimStart().startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("- ")) {
        items.push(lines[i].trim().slice(2));
        i++;
      }
      blocks.push(
        <ul key={key++} className="list-disc pl-5 my-1.5 space-y-0.5 text-xs text-text-secondary">
          {items.map((it, ii) => <li key={ii}>{inline(it, `li${ii}`)}</li>)}
        </ul>,
      );
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !lines[i].trimStart().startsWith("|")
           && !lines[i].trimStart().startsWith("- ") && !/^#{1,6}\s/.test(lines[i])) {
      para.push(lines[i].trim());
      i++;
    }
    if (!para.length) { i++; continue; }  // never stall on an unclassified line
    blocks.push(
      <p key={key++} className="text-xs text-text-secondary leading-relaxed my-1.5">
        {inline(para.join(" "), `p${key}`)}
      </p>,
    );
  }
  return <div>{blocks}</div>;
}
